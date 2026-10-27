"""A search's results are never silently lost: a failed turn of updates
queues them again, and a job a restart cut short is reported."""

import uuid

import psycopg
import pytest

from backend.app.database import models
from backend.app.database.connect import AsyncSessionLocal
from backend.app.runs import manager
from backend.app.services import lace_events
from backend.tests.helpers import make_user
from config import settings


def _lace(user) -> uuid.UUID:
    with psycopg.connect(settings.database_url, autocommit=True) as conn:
        return conn.execute("INSERT INTO laces (id, user_id, name, website) VALUES (%s, %s, 'Ada', 'https://acme.test')"
                            " RETURNING id", (uuid.uuid4(), user.id)).fetchone()[0]


async def test_a_failed_turn_of_updates_queues_them_again():
    lace_id = _lace(make_user("Owner"))
    async with AsyncSessionLocal() as db, db.begin():
        await lace_events.add(db, lace_id, "Found 3 accounts.")
    async with AsyncSessionLocal() as db, db.begin():
        pending = await lace_events.take_pending(db, lace_id)
    assert pending.texts == ["Found 3 accounts."]

    async def fails():
        raise RuntimeError("model down")
    with pytest.raises(RuntimeError):
        await manager._putting_back(fails(), pending.ids)
    async with AsyncSessionLocal() as db, db.begin():
        assert (await lace_events.take_pending(db, lace_id)).texts == ["Found 3 accounts."]


async def test_a_job_a_restart_cut_short_is_reported(monkeypatch):
    owner = make_user("Owner")
    lace_id = _lace(owner)
    woken = []

    async def wake(user_id, lace, owner_id=None):
        woken.append((user_id, lace, owner_id))
    monkeypatch.setattr(manager, "wake_lace", wake)
    async with AsyncSessionLocal() as db, db.begin():
        job = models.Run(user_id=owner.id, lace_id=lace_id, kind="lace_accounts", status="running")
        turn = models.Run(user_id=owner.id, lace_id=lace_id, kind="lace_turn", status="running")
        db.add_all([job, turn])
    await manager.recover_after_restart()
    async with AsyncSessionLocal() as db, db.begin():
        assert (await db.get(models.Run, job.id)).status == "failed"
        [update] = (await lace_events.take_pending(db, lace_id)).texts
    # Only the job is reported, and its chat is woken to pass it on.
    assert "search for target accounts was cut short" in update
    assert woken == [(owner.id, lace_id, None)]
