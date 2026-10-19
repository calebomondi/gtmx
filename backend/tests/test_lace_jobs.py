"""A Lace's background jobs: a tool starts the competitor hunt, the hunt saves
what it found and queues an update, and the Lace wakes to tell the founder,
even when the founder was mid-conversation or the hunt failed."""

import asyncio
import uuid

import psycopg
import pytest
from langchain_core.messages import AIMessage
from sqlalchemy import func, select

from agents.lace.store import JobBlocked
from agents.schemas.competition import CompetitorProfile
from backend.app.database import models
from backend.app.database.connect import AsyncSessionLocal
from backend.app.runs import lace_jobs
from backend.app.services import lace_competitors
from backend.tests.test_laces_api import API, _events, lace_runtime  # noqa: F401 -- fixture
from backend.tests.test_runs import _wait_for_status
from config import settings

RIVAL = CompetitorProfile(name="Rival", website="https://www.rival.test/", description="Payroll for vets.")


def _call(name, args=None, id="c1"):
    return AIMessage(content="", tool_calls=[{"name": name, "id": id, "args": args or {}}])


async def _runs(lace_id, kind) -> list[models.Run]:
    async with AsyncSessionLocal() as db:
        return list((await db.scalars(select(models.Run).where(
            models.Run.lace_id == uuid.UUID(lace_id), models.Run.kind == kind).order_by(models.Run.created_at))).all())


async def _wait_for_turns(lace_id, count, timeout=10.0):
    async with asyncio.timeout(timeout):
        while True:
            turns = await _runs(lace_id, "lace_turn")
            if len(turns) >= count and all(t.status == "completed" for t in turns):
                return turns
            await asyncio.sleep(0.05)


@pytest.fixture
def lace(client, lace_runtime):  # noqa: F811
    body = client.post(f"{API}/laces", json={"name": "Ada", "website": "acme.test"}).json()
    client.portal.call(_wait_for_status, uuid.UUID(body["run_id"]), {"completed"})
    return body["lace"]["id"]


def test_hunt_saves_competitors_and_the_lace_reports_back(client, lace, lace_runtime, monkeypatch):  # noqa: F811
    monkeypatch.setattr(lace_jobs, "find_competitors", lambda profile, facts, focus: [RIVAL])
    lace_runtime.extend([_call("find_competitors", {"focus": "local"}), AIMessage(content="On it."),
                         AIMessage(content="I found Rival, who sells payroll to vets.")])

    client.post(f"{API}/laces/{lace}/messages", json={"text": "who competes with us?"})
    client.portal.call(_wait_for_turns, lace, 2)

    [job] = client.portal.call(_runs, lace, "lace_competitors")
    assert job.status == "completed" and job.input == {"focus": "local"} and job.progress["new"] == 1
    with psycopg.connect(settings.database_url) as conn:
        assert conn.execute("SELECT name, domain_key, origin, status FROM lace_competitors").fetchall() == [
            ("Rival", "rival.test", "found", "suggested")]
        assert conn.execute("SELECT count(*) FROM lace_events WHERE consumed_at IS NULL").fetchone()[0] == 0
    messages = client.get(f"{API}/laces/{lace}/messages").json()
    # The update the Lace was handed is not shown as something the founder said.
    assert [m["role"] for m in messages] == ["lace", "founder", "lace", "lace"]
    assert messages[-1]["content"] == "I found Rival, who sells payroll to vets."


def test_a_failed_hunt_is_reported_too(client, lace, lace_runtime, monkeypatch):  # noqa: F811
    def boom(profile, facts, focus):
        raise JobBlocked("Not enough is known about what the startup sells to say what competes with it.")
    monkeypatch.setattr(lace_jobs, "find_competitors", boom)
    lace_runtime.extend([_call("find_competitors"), AIMessage(content="On it."),
                         AIMessage(content="I couldn't search yet: tell me more about what you sell.")])

    client.post(f"{API}/laces/{lace}/messages", json={"text": "find competitors"})
    turns = client.portal.call(_wait_for_turns, lace, 2)
    [job] = client.portal.call(_runs, lace, "lace_competitors")
    assert job.status == "failed"
    assert "competitor search failed: Not enough is known" in turns[-1].input["updates"][0]


def test_only_one_hunt_at_a_time(client, lace, lace_runtime, user):  # noqa: F811
    with psycopg.connect(settings.database_url, autocommit=True) as conn:
        conn.execute("INSERT INTO runs (id, user_id, lace_id, kind, status) VALUES (%s, %s, %s, 'lace_competitors', 'running')",
                     (uuid.uuid4(), user.id, lace))
    lace_runtime.extend([_call("find_competitors"), AIMessage(content="Already on it.")])
    sent = client.post(f"{API}/laces/{lace}/messages", json={"text": "find competitors"}).json()
    client.portal.call(_wait_for_status, uuid.UUID(sent["run_id"]), {"completed"})
    [result] = [f for f in _events(client, sent["run_id"]) if f["type"] == "tool_result"]
    assert result["tool"] == "find_competitors" and not result["ok"] and "already running" in result["summary"]
    assert len(client.portal.call(_runs, lace, "lace_competitors")) == 1


def test_updates_queued_mid_turn_wait_for_it_to_end(client, lace, lace_runtime, user):  # noqa: F811
    from backend.app.runs import manager
    with psycopg.connect(settings.database_url, autocommit=True) as conn:
        busy = conn.execute("INSERT INTO runs (id, user_id, lace_id, kind, status) VALUES (%s, %s, %s, 'lace_turn', 'running')"
                            " RETURNING id", (uuid.uuid4(), user.id, lace)).fetchone()[0]
        conn.execute("INSERT INTO lace_events (id, lace_id, text) VALUES (%s, %s, 'A rival changed its pricing.')",
                     (uuid.uuid4(), lace))
    client.portal.call(manager.wake_lace, user.id, uuid.UUID(lace))
    with psycopg.connect(settings.database_url, autocommit=True) as conn:
        assert conn.execute("SELECT count(*) FROM lace_events WHERE consumed_at IS NULL").fetchone()[0] == 1
        conn.execute("UPDATE runs SET status = 'completed' WHERE id = %s", (busy,))
    lace_runtime.append(AIMessage(content="Heads up: a rival changed its pricing."))
    client.portal.call(manager.wake_lace, user.id, uuid.UUID(lace))
    turns = client.portal.call(_wait_for_turns, lace, 2)
    assert turns[-1].input == {"updates": ["A rival changed its pricing."]}


async def test_a_refound_firm_keeps_the_founders_dismissal(user):
    with psycopg.connect(settings.database_url, autocommit=True) as conn:
        lace_id = conn.execute("INSERT INTO laces (id, user_id, name, website) VALUES (%s, %s, 'Ada', 'https://acme.test')"
                               " RETURNING id", (uuid.uuid4(), user.id)).fetchone()[0]
        run_id = conn.execute("INSERT INTO runs (id, user_id, lace_id, kind, status) VALUES (%s, %s, %s, 'lace_competitors',"
                              " 'completed') RETURNING id", (uuid.uuid4(), user.id, lace_id)).fetchone()[0]
    async with AsyncSessionLocal() as db, db.begin():
        assert await lace_competitors.upsert_found(db, lace_id, run_id, [RIVAL]) == (1, 0)
    with psycopg.connect(settings.database_url, autocommit=True) as conn:
        conn.execute("UPDATE lace_competitors SET status = 'dismissed'")
    async with AsyncSessionLocal() as db, db.begin():
        assert await lace_competitors.upsert_found(db, lace_id, run_id, [RIVAL]) == (0, 1)
        assert await lace_competitors.list_tracked(db, lace_id, 10) == []
        assert await db.scalar(select(func.count()).select_from(models.LaceCompetitor)) == 1
