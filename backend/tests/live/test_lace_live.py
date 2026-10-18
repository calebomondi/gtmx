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
