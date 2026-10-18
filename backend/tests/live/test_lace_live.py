"""A Lace end to end against real services: the API creates it, it onboards
from a real website, then answers a founder message that needs web research.
Real Firecrawl, Exa, LLM ladder and Postgres checkpointer.

    uv run pytest -m live backend/tests/live/test_lace_live.py -s
"""

import json
import uuid

import pytest

from backend.app import agents_runtime
from backend.tests.test_runs import _wait_for_status
from config import settings

pytestmark = pytest.mark.live

API = "/api/v1"
WEBSITE = "linear.app"
ONBOARDING_TIMEOUT_S = 600
TURN_TIMEOUT_S = 300


@pytest.fixture
def runtime(client):
    client.portal.call(agents_runtime.start_agent_runtime, settings.database_url)
    yield
    client.portal.call(agents_runtime.stop_agent_runtime)


def _frames(client, run_id: str) -> list[dict]:
    with client.stream("GET", f"{API}/runs/{run_id}/events") as response:
        return [json.loads(line) for line in response.iter_lines() if line]


def test_lace_onboards_and_researches(client, runtime):
    created = client.post(f"{API}/laces", json={"name": "Ada", "website": WEBSITE}).json()
    lace_id, run_id = created["lace"]["id"], created["run_id"]
    run = client.portal.call(_wait_for_status, uuid.UUID(run_id), {"completed", "failed"}, ONBOARDING_TIMEOUT_S)
    assert run.status == "completed", run.error

    lace = client.get(f"{API}/laces/{lace_id}").json()
    facts = client.get(f"{API}/laces/{lace_id}/facts").json()
    [opening] = client.get(f"{API}/laces/{lace_id}/messages").json()
    print(f"\n--- {lace['startup_name']}: {len(facts)} facts\n--- OPENING\n{opening['content']}")
    assert lace["status"] == "active" and len(facts) >= 5 and opening["role"] == "lace"

    sent = client.post(f"{API}/laces/{lace_id}/messages", json={
        "text": "Who are our three closest competitors? Look them up and note what you find."}).json()
    run = client.portal.call(_wait_for_status, uuid.UUID(sent["run_id"]), {"completed", "failed"}, TURN_TIMEOUT_S)
    assert run.status == "completed", run.error

    frames = _frames(client, sent["run_id"])
    steps = [f["text"] for f in frames if f["type"] == "step"]
    reply = client.get(f"{API}/laces/{lace_id}/messages").json()[-1]
    print("--- STEPS\n" + "\n".join(steps) + f"\n--- REPLY\n{reply['content']}")
    assert steps and reply["role"] == "lace" and reply["content"].strip()
    after = client.get(f"{API}/laces/{lace_id}/facts?topic=competition").json()
    print(f"--- competition facts recorded: {len(after)}")


HUNT_TIMEOUT_S = 1800


def test_lace_hunts_competitors_and_reports_back(client, runtime, user):
    import psycopg

    from backend.app.runs import manager

    created = client.post(f"{API}/laces", json={"name": "Ada", "website": WEBSITE}).json()
    lace_id = uuid.UUID(created["lace"]["id"])
    run = client.portal.call(_wait_for_status, uuid.UUID(created["run_id"]), {"completed", "failed"}, ONBOARDING_TIMEOUT_S)
    assert run.status == "completed", run.error

    job_id = client.portal.call(manager._LaceJobs(user.id, lace_id).start, "find_competitors", {"focus": None})
    job = client.portal.call(_wait_for_status, uuid.UUID(job_id), {"completed", "failed"}, HUNT_TIMEOUT_S)
    assert job.status == "completed", job.error
    # The wake turn starts just after the job marks itself completed.
    wake = client.portal.call(_first_turn, lace_id)
    with psycopg.connect(settings.database_url) as conn:
        rows = conn.execute("SELECT name, website, summary FROM lace_competitors WHERE lace_id = %s", (lace_id,)).fetchall()
    print(f"\n--- {len(rows)} competitors, job progress {job.progress}")
    for name, website, summary in rows:
        print(f"  {name} ({website}): {(summary or '')[:100]}")
    assert rows and wake, "no competitors saved, or the Lace was not woken"
    turn = client.portal.call(_wait_for_status, wake, {"completed", "failed"}, TURN_TIMEOUT_S)
    assert turn.status == "completed", turn.error
    print("--- THE LACE SAYS\n" + client.get(f"{API}/laces/{lace_id}/messages").json()[-1]["content"])


async def _first_turn(lace_id: uuid.UUID, timeout: float = 30.0) -> uuid.UUID:
    import asyncio

    from sqlalchemy import select

    from backend.app.database import models
    from backend.app.database.connect import AsyncSessionLocal
    async with asyncio.timeout(timeout):
        while True:
            async with AsyncSessionLocal() as db:
                run_id = await db.scalar(select(models.Run.id).where(
                    models.Run.lace_id == lace_id, models.Run.kind == "lace_turn"))
            if run_id:
                return run_id
            await asyncio.sleep(0.2)
