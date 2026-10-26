"""Two founders on one Lace, end to end: Wanjiru's message waits while the
team's chat is busy, her private chat runs meanwhile and its search finds a
competitor only she sees; she pushes it, the founder approves it, the team's
Lace hears who approved it once its chat is free; and when she leaves, her
private chat and her unpushed finds go with her."""

import asyncio
import uuid

import psycopg
import pytest
from langchain_core.messages import AIMessage

from backend.app import supabase_admin
from backend.app.runs import lace as lace_runs
from backend.app.runs import lace_jobs, manager
from backend.tests.helpers import FakeSupabase, make_user, supabase_user
from backend.tests.test_lace_jobs import RIVAL, _call, _runs, lace  # noqa: F401 -- fixture
from backend.tests.test_lace_members import _join
from backend.tests.test_lace_private_finds import _seed
from backend.tests.test_laces_api import API, lace_runtime  # noqa: F401 -- fixture
from config import settings

WANJIRU = make_user("Wanjiru")


@pytest.fixture
def team(monkeypatch, user, lace):  # noqa: F811
    users = [supabase_user(u.id, u.email) for u in (user, WANJIRU)]
    users[1].user_metadata = {"full_name": "Wanjiru Kamau"}
    fake = FakeSupabase(users)

    async def get_client():
        return fake
    monkeypatch.setattr(supabase_admin, "get_client", get_client)
    _join(lace, WANJIRU)
    return lace


async def _settle(lace_id, owner_id, count, timeout=10.0):
    """Until `count` turns in one chat (the team's: owner_id None) are over."""
    async with asyncio.timeout(timeout):
        while True:
            turns = [r for r in await _runs(lace_id, "lace_turn") if r.owner_id == owner_id]
            if len(turns) >= count and all(t.status in ("completed", "failed") for t in turns):
                return
            await asyncio.sleep(0.025)


def test_two_founders_on_one_lace(client, user, team, monkeypatch, lace_runtime):  # noqa: F811
    monkeypatch.setattr(lace_jobs, "find_competitors", lambda profile, facts, focus: [RIVAL])
    busy = uuid.uuid4()
    with psycopg.connect(settings.database_url, autocommit=True) as conn:
        conn.execute("INSERT INTO runs (id, user_id, lace_id, kind, status) VALUES (%s, %s, %s, 'lace_turn', 'running')",
                     (busy, user.id, team))

    # The founder's turn is running: Wanjiru's team message waits; her private one runs now.
    client.sign_in(WANJIRU)
    waiting = client.post(f"{API}/laces/{team}/messages", json={"text": "any news?"}).json()
    assert waiting["queued"] is True
    lace_runtime.extend([_call("find_competitors"), AIMessage(content="Searching."),
                         AIMessage(content="Found Rival, just for you.")])
    client.post(f"{API}/laces/{team}/private/messages", json={"text": "who competes with us?"})
    client.portal.call(_settle, team, WANJIRU.id, 2)
    assert client.get(f"{API}/laces/{team}/competitors", params={"status": "suggested"}).json() == []

    # She pushes it; the founder approves it for the team.
    [rival] = client.get(f"{API}/laces/{team}/my-finds").json()
    client.post(f"{API}/laces/{team}/my-finds/push", json={"items": [{"kind": "competitor", "id": rival["id"]}]})
    client.sign_in(user)
    assert client.post(f"{API}/laces/{team}/reviews/competitor/{rival['id']}/approve").status_code == 204
    assert [c["name"] for c in client.get(f"{API}/laces/{team}/competitors", params={"status": "tracked"}).json()] == [
        "Rival"]
    feed = [(i["kind"], (i["actor"] or {}).get("name")) for i in client.get(f"{API}/laces/{team}/activity").json()]
    assert feed[:2] == [("competitor_saved", "Wanjiru Kamau"), ("finds_proposed", "Wanjiru Kamau")]

    # The team's chat frees up: her message is answered, then the Lace passes on the approval.
    lace_runtime.extend([AIMessage(content="Nothing new yet."), AIMessage(content="Rival is on our file now.")])
    with psycopg.connect(settings.database_url, autocommit=True) as conn:
        conn.execute("UPDATE runs SET status = 'completed' WHERE id = %s", (busy,))
    client.portal.call(manager.start_next_queued, uuid.UUID(team))
    client.portal.call(_settle, team, None, 3)
    said = [m["content"] for m in client.get(f"{API}/laces/{team}/messages").json()]
    assert said[-3:] == ["any news?", "Nothing new yet.", "Rival is on our file now."]
    [update] = [r for r in client.portal.call(_runs, team, "lace_turn")
                if r.owner_id is None and (r.input or {}).get("updates")]
    assert "approved for the team by Owner" in update.input["updates"][0]

    # She leaves: her private chat and her unpushed finds go.
    client.portal.call(_seed, team, WANJIRU.id)
    client.sign_in(WANJIRU)
    assert client.post(f"{API}/laces/{team}/leave").status_code == 204
    assert client.portal.call(lace_runs._thread, lace_runs.LaceThread(uuid.UUID(team), WANJIRU.id)) == []
    with psycopg.connect(settings.database_url) as conn:
        assert conn.execute("SELECT count(*) FROM lace_accounts WHERE owner_id IS NOT NULL").fetchone()[0] == 0
