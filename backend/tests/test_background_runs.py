"""Competitor/account runs and manual-competitor research run through the run
manager: counts land on the run and in the API, failures are recorded."""

import json
import uuid

import psycopg
import pytest

from backend.app.runs import background
from backend.tests.test_runs import _wait_for_status
from config import settings

API = "/api/v1"


@pytest.fixture
def discovered(owned):
    """`owned`'s workspace after a finished discovery (profile + ICP)."""
    insights = {"ideal_competitor_profile": {"confidence": "medium", "archetypes": [{}, {}, {}]}, "icp": {"industries": ["x"]}}
    with psycopg.connect(settings.database_url, autocommit=True) as conn:
        conn.execute(
            "INSERT INTO product_profiles (id, workspace_id, target_geo, insights) VALUES (%s, %s, '[]', %s)",
            (uuid.uuid4(), owned["workspace"], json.dumps(insights)),
        )
    return owned


def test_competitor_run_records_counts(client, discovered, monkeypatch):
    async def fake(workspace_id, run_id):
        return {"candidates_seen": 40, "found": 3, "dropped": 37, "dropped_reasons": {"no public website": 30}}
    monkeypatch.setattr(background, "run_competitor_discovery", fake)

    started = client.post(f"{API}/workspaces/{discovered['workspace']}/competitors/runs")
    assert started.status_code == 202
    run = started.json()["run"]
    assert run["profile_confidence"] == "medium" and run["archetypes_targeted"] == 3

    client.portal.call(_wait_for_status, uuid.UUID(run["id"]), {"completed"})
    polled = client.get(f"{API}/workspaces/{discovered['workspace']}/competitors/runs/{run['id']}").json()
    assert polled["status"] == "completed"
    assert (polled["candidates_seen"], polled["found"], polled["dropped"]) == (40, 3, 37)
    assert polled["profile_confidence"] == "medium"  # start-time progress survives completion


def test_account_run_failure_is_recorded(client, discovered, monkeypatch):
    async def boom(workspace_id, run_id):
        raise RuntimeError("search provider exploded with internals")
    monkeypatch.setattr(background, "run_account_discovery_for_workspace", boom)

    run = client.post(f"{API}/workspaces/{discovered['workspace']}/accounts/runs").json()["run"]
    client.portal.call(_wait_for_status, uuid.UUID(run["id"]), {"failed"})
    polled = client.get(f"{API}/workspaces/{discovered['workspace']}/accounts/runs/{run['id']}").json()
    assert polled["status"] == "failed" and "internals" not in polled["error"]


def test_adding_a_competitor_starts_a_research_run(client, owned, monkeypatch):
    researched = []

    async def fake(workspace_id, competitor_id):
        researched.append(competitor_id)
        return True
    monkeypatch.setattr(background, "research_competitor_site", fake)

    competitor = client.post(
        f"{API}/workspaces/{owned['workspace']}/competitors", json={"website": "new-rival.example"},
    ).json()
    with psycopg.connect(settings.database_url) as conn:
        run_id = conn.execute("SELECT id FROM runs WHERE kind = 'competitor_research'").fetchone()[0]
    client.portal.call(_wait_for_status, run_id, {"completed"})
    assert [str(c) for c in researched] == [competitor["id"]]
