"""Runs emit feed signals; the feed is owner-scoped; read/pin/dismiss persist."""

import uuid

from backend.app.database import models
from backend.app.database.connect import AsyncSessionLocal
from backend.app.runs import background, manager
from backend.tests.helpers import make_user
from backend.tests.test_background_runs import discovered  # noqa: F401 -- fixture
from backend.tests.test_runs import REQUEST, FakeAgent, _wait_for_status
from config import settings

API = "/api/v1"


async def _drain():
    """Wait for run tasks to finish (signals are written just after completion)."""
    import asyncio
    if manager._tasks:
        await asyncio.gather(*manager._tasks.values(), return_exceptions=True)


async def _insert_competitor(workspace_id, run_id, name):
    async with AsyncSessionLocal() as db:
        db.add(models.Competitor(
            workspace_id=workspace_id, run_id=run_id, name=name,
            website=f"https://{name.lower()}.example", domain_key=f"{name.lower()}.example",
            positioning="Fast tracker", matched_archetype="Speed challenger",
        ))
        await db.commit()


def test_competitor_run_emits_one_signal_per_new_rival(client, discovered, monkeypatch):  # noqa: F811
    async def fake(workspace_id, run_id):
        await _insert_competitor(workspace_id, run_id, "Newcomer")
        return {"found": 1}
    monkeypatch.setattr(background, "run_competitor_discovery", fake)

    run = client.post(f"{API}/workspaces/{discovered['workspace']}/competitors/runs").json()["run"]
    client.portal.call(_wait_for_status, uuid.UUID(run["id"]), {"completed"})
    client.portal.call(_drain)

    feed = client.get(f"{API}/signals").json()
    rival = [s for s in feed if s["category"] == "competitor"]
    assert len(rival) == 1
    assert rival[0]["title"] == "New competitor: Newcomer"
    assert rival[0]["reason"] == "Matches the 'Speed challenger' archetype."
    assert rival[0]["workspace_name"] == "Owner Workspace"
    assert rival[0]["source_url"] == "https://newcomer.example"

    # Same feed, scoped to the workspace.
    assert [s["id"] for s in client.get(f"{API}/signals", params={"workspace_id": discovered["workspace"]}).json()] == [s["id"] for s in feed]


def test_read_pin_dismiss_and_ownership(client, user, discovered, monkeypatch):  # noqa: F811
    async def fake(workspace_id, run_id):
        await _insert_competitor(workspace_id, run_id, "Newcomer")
        return {}
    monkeypatch.setattr(background, "run_competitor_discovery", fake)
    run = client.post(f"{API}/workspaces/{discovered['workspace']}/competitors/runs").json()["run"]
    client.portal.call(_wait_for_status, uuid.UUID(run["id"]), {"completed"})
    client.portal.call(_drain)
    signal_id = client.get(f"{API}/signals").json()[0]["id"]

    updated = client.patch(f"{API}/signals/{signal_id}", json={"read": True, "pinned": True}).json()
    assert updated["read"] and updated["pinned"]

    client.sign_in(make_user("Intruder"))
    assert client.get(f"{API}/signals").json() == []
    assert client.patch(f"{API}/signals/{signal_id}", json={"dismissed": True}).status_code == 404
    assert client.get(f"{API}/signals", params={"workspace_id": discovered["workspace"]}).json() == []

    client.sign_in(user)
    client.patch(f"{API}/signals/{signal_id}", json={"dismissed": True})
    assert client.get(f"{API}/signals").json() == []


async def test_discovery_and_failures_emit_signals(monkeypatch):
    from sqlalchemy import select

    from backend.app.runs import discovery

    owner = make_user("Owner")
    good = FakeAgent()
    monkeypatch.setattr(discovery, "get_agent", lambda: good)
    run = await manager.start_discovery(owner.id, REQUEST)
    await _wait_for_status(run.id, {"awaiting_input"})
    await manager.answer(owner.id, run.id, "yes")
    await _wait_for_status(run.id, {"completed"})

    bad = FakeAgent(fail_on_resume=True)
    monkeypatch.setattr(discovery, "get_agent", lambda: bad)
    monkeypatch.setattr(settings, "max_active_discovery_runs", 5)
    second = await manager.start_discovery(owner.id, REQUEST)
    await _wait_for_status(second.id, {"awaiting_input"})
    await manager.answer(owner.id, second.id, "yes")
    await _wait_for_status(second.id, {"failed"})
    await _drain()

    async with AsyncSessionLocal() as db:
        rows = (await db.execute(select(models.Signal).where(models.Signal.user_id == owner.id))).scalars().all()
    titles = sorted(s.title for s in rows)
    # The failed run never created a workspace (it failed at the first resume
    # in this fake), so only the finished discovery yields a signal.
    assert titles == ["Discovery finished"]
