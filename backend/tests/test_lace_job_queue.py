"""A Lace's background jobs of one kind run one at a time: another of the
kind waits its turn and starts on its own, the same one asked again is
refused, and the Lace is told which are running and which wait."""

import asyncio
import threading
import uuid

import psycopg
import pytest
from langchain_core.messages import AIMessage

from agents.lace.store import JobRefused
from sqlalchemy import select

from backend.app.database import models
from backend.app.database.connect import AsyncSessionLocal
from backend.app.runs import lace_jobs, manager
from backend.app.services.runs import TERMINAL_STATUSES
from backend.tests.test_lace_accounts import _with_icp
from backend.tests.test_lace_jobs import lace  # noqa: F401 -- fixture
from backend.tests.test_laces_api import lace_runtime  # noqa: F401 -- fixture
from backend.tests.test_runs import _wait_for_status
from config import settings


async def _idle(lace_id: str, timeout: float = 20.0) -> None:
    """Until every job and every turn they woke has ended, so none is cut
    short by the next test's cleanup."""
    async with asyncio.timeout(timeout):
        while True:
            async with AsyncSessionLocal() as db:
                busy = (await db.scalars(select(models.Run.id).where(
                    models.Run.lace_id == uuid.UUID(lace_id), models.Run.status.not_in(TERMINAL_STATUSES)))).all()
            if not busy:
                return
            await asyncio.sleep(0.05)


@pytest.fixture
def searches(client, lace, lace_runtime, monkeypatch):  # noqa: F811
    """Lead searches that record the countries asked for; one for Kenya holds
    until `gate` is set, so the others have something to wait behind. Each
    test ends with the Lace idle."""
    _with_icp(lace)
    gate, asked = threading.Event(), []

    def fake(profile, facts, icp, exclude, countries):
        asked.append(countries)
        if countries == ["Kenya"]:
            gate.wait(10)
        return []

    monkeypatch.setattr(lace_jobs, "find_accounts", fake)
    lace_runtime.extend(AIMessage(content="Noted.") for _ in range(8))  # the wake after each search
    yield gate, asked
    gate.set()
    client.portal.call(_idle, lace)


def _ask(client, user, lace_id, countries, actor_id=None):
    return client.portal.call(manager.request_lace_job, "lace_accounts", user.id, uuid.UUID(lace_id),
                              {"countries": countries, "actor_id": str(actor_id or user.id)})


def test_a_second_search_waits_its_turn_then_runs(client, lace, user, searches):  # noqa: F811
    gate, asked = searches
    first = _ask(client, user, lace, ["Kenya"])
    second = _ask(client, user, lace, ["Uganda"])
    assert (first.ahead, first.run.status) == (0, "running")
    assert (second.ahead, second.run.status) == (1, "queued")

    jobs = manager._LaceJobs(user.id, uuid.UUID(lace), user.id, None)
    assert [(j.what, j.queued) for j in client.portal.call(jobs.running)] == [
        ("search for leads", False), ("search for leads", True)]

    gate.set()
    client.portal.call(_wait_for_status, second.run.id, {"completed"})
    assert asked == [["Kenya"], ["Uganda"]]


def test_the_same_search_asked_again_is_refused(client, lace, user, searches):  # noqa: F811
    gate, asked = searches
    _ask(client, user, lace, ["Kenya"])
    _ask(client, user, lace, ["Uganda"])
    with pytest.raises(JobRefused, match="That same search for leads is already under way"):
        _ask(client, user, lace, ["Kenya"], actor_id=uuid.uuid4())  # whoever on the team asks
    with pytest.raises(JobRefused, match="That same search for leads is already waiting its turn"):
        _ask(client, user, lace, ["Uganda"])


def test_only_so_many_wait(client, lace, user, searches):  # noqa: F811
    gate, _ = searches
    _ask(client, user, lace, ["Kenya"])
    for place in ["Uganda", "Rwanda", "Ghana"][:manager.MAX_QUEUED_JOBS]:
        assert _ask(client, user, lace, [place]).run.status == "queued"
    with pytest.raises(JobRefused, match="3 more of this kind .search for leads. are already waiting their turn"):
        _ask(client, user, lace, ["Nigeria"])


def test_cancelling_the_running_one_starts_the_next(client, lace, user, searches):  # noqa: F811
    gate, asked = searches
    first = _ask(client, user, lace, ["Kenya"])
    second = _ask(client, user, lace, ["Uganda"])
    client.portal.call(manager.cancel, user.id, first.run.id)
    client.portal.call(_wait_for_status, second.run.id, {"completed"})
    assert asked[-1] == ["Uganda"]


def test_a_scheduled_job_is_not_queued_behind_one(client, lace, user, searches):  # noqa: F811
    gate, _ = searches
    _ask(client, user, lace, ["Kenya"])
    with pytest.raises(JobRefused, match="The search for leads is already under way"):
        client.portal.call(manager.start_lace_job, "lace_accounts", user.id, uuid.UUID(lace), {"scheduled": True})


def test_a_job_waiting_behind_one_a_restart_cut_short_starts(client, lace, user, searches):  # noqa: F811
    _, asked = searches
    stranded, waiting = uuid.uuid4(), uuid.uuid4()
    with psycopg.connect(settings.database_url, autocommit=True) as conn:
        for run_id, status, place in ((stranded, "running", "Kenya"), (waiting, "queued", "Uganda")):
            conn.execute("INSERT INTO runs (id, user_id, lace_id, kind, status, input, created_at)"
                         " VALUES (%s, %s, %s, 'lace_accounts', %s, %s, now())",
                         (run_id, user.id, lace, status, psycopg.types.json.Jsonb({"countries": [place]})))
    client.portal.call(manager.recover_after_restart)
    assert client.portal.call(_wait_for_status, stranded, {"failed"}).status == "failed"
    client.portal.call(_wait_for_status, waiting, {"completed"})
    assert asked == [["Uganda"]]
