"""A member's private chat with a shared Lace: its own thread, running beside
the team's; only they see it, its runs and what its searches find; it
cannot change what the team's Lace knows; and it is only for a Lace with a
team."""

import uuid
from functools import partial

import psycopg
import pytest
from langchain_core.messages import AIMessage

from agents.lace.graph import build_lace_graph
from backend.app import supabase_admin
from backend.app.runs import lace as lace_runs
from backend.app.runs import lace_jobs
from backend.tests.helpers import FakeSupabase, make_user, supabase_user
from backend.tests.test_lace_jobs import RIVAL, _call, _runs, _wait_for_turns, lace  # noqa: F401 -- fixture
from backend.tests.test_lace_members import _join
from backend.tests.test_laces_api import API, lace_runtime  # noqa: F401 -- fixture
from backend.tests.test_runs import _wait_for_status
from config import settings

WANJIRU = make_user("Wanjiru")


@pytest.fixture
def team(monkeypatch, user, lace):  # noqa: F811
    """The founder's Lace, with Wanjiru on it as a member."""
    fake = FakeSupabase([supabase_user(u.id, u.email) for u in (user, WANJIRU)])

    async def get_client():
        return fake
    monkeypatch.setattr(supabase_admin, "get_client", get_client)
    _join(lace, WANJIRU)
    return lace


def _private(client, lace_id, text):
    return client.post(f"{API}/laces/{lace_id}/private/messages", json={"text": text})


def _said(client, lace_id, private=False):
    path = "private/messages" if private else "messages"
    return [m["content"] for m in client.get(f"{API}/laces/{lace_id}/{path}").json()]


def test_a_lace_of_one_has_no_private_chat(client, lace):  # noqa: F811
    assert _private(client, lace, "hi").status_code == 409
    assert client.get(f"{API}/laces/{lace}/private/messages").status_code == 409


def test_a_private_chat_is_its_own_and_runs_beside_the_team_s(client, user, team, lace_runtime):  # noqa: F811
    with psycopg.connect(settings.database_url, autocommit=True) as conn:
        conn.execute("INSERT INTO runs (id, user_id, lace_id, kind, status) VALUES (%s, %s, %s, 'lace_turn', 'running')",
                     (uuid.uuid4(), user.id, team))
    lace_runtime.append(AIMessage(content="Just between us: hello."))
    client.sign_in(WANJIRU)
    sent = _private(client, team, "hello in private")
    assert sent.status_code == 202 and sent.json()["queued"] is False
    client.portal.call(_wait_for_status, uuid.UUID(sent.json()["run_id"]), {"completed"})
    assert _said(client, team, private=True) == ["hello in private", "Just between us: hello."]
    assert "hello in private" not in _said(client, team)

    client.sign_in(user)
    assert _said(client, team, private=True) == []
    assert client.get(f"{API}/runs/{sent.json()['run_id']}/events").status_code == 404
    assert sent.json()["run_id"] not in {r["id"] for r in client.get(f"{API}/runs/active").json()}


def test_what_a_private_search_finds_stays_private(client, user, team, monkeypatch, lace_runtime):  # noqa: F811
    monkeypatch.setattr(lace_jobs, "find_competitors", lambda profile, facts, focus: [RIVAL])
    lace_runtime.extend([_call("find_competitors"), AIMessage(content="Searching."),
                         AIMessage(content="Found Rival, just for you.")])
    client.sign_in(WANJIRU)
    sent = _private(client, team, "who competes with us?")
    client.portal.call(_wait_for_status, uuid.UUID(sent.json()["run_id"]), {"completed"})
    [job] = client.portal.call(_runs, team, "lace_competitors")
    client.portal.call(_wait_for_status, job.id, {"completed"})
    # Her message's turn, then the one that brings her the search's update.
    turns = client.portal.call(_wait_for_turns, team, 2)
    assert {t.owner_id for t in turns} == {WANJIRU.id} and job.owner_id == WANJIRU.id
    assert _said(client, team, private=True)[-1] == "Found Rival, just for you."
    assert client.get(f"{API}/laces/{team}/competitors", params={"status": "suggested"}).json() == []
    assert client.get(f"{API}/laces/{team}/activity").json() == []
    with psycopg.connect(settings.database_url) as conn:
        assert conn.execute("SELECT name, owner_id FROM lace_competitors").fetchall() == [("Rival", WANJIRU.id)]
        rival = conn.execute("SELECT id FROM lace_competitors").fetchone()[0]

    # Its card works for her, and saving it keeps it private; the rest of the team can't touch it.
    assert client.patch(f"{API}/laces/{team}/competitors/{rival}", json={"status": "tracked"}).status_code == 200
    assert client.get(f"{API}/laces/{team}/activity").json() == []
    client.sign_in(user)
    assert client.patch(f"{API}/laces/{team}/competitors/{rival}", json={"status": "dismissed"}).status_code == 404


def test_a_private_chat_cannot_change_what_the_team_knows(client, team, monkeypatch, lace_runtime):  # noqa: F811
    offered: list[set[str]] = []

    def model_step(messages, tools, sink):
        offered.append({t.name for t in tools})
        return lace_runtime.pop(0)
    monkeypatch.setattr(lace_runs, "build_lace_graph", partial(build_lace_graph, model_step=model_step))
    lace_runtime.extend([AIMessage(content="Hi."), AIMessage(content="Hi again.")])
    client.sign_in(WANJIRU)
    sent = _private(client, team, "hi")
    client.portal.call(_wait_for_status, uuid.UUID(sent.json()["run_id"]), {"completed"})
    team_turn = client.post(f"{API}/laces/{team}/messages", json={"text": "hi"}).json()
    client.portal.call(_wait_for_status, uuid.UUID(team_turn["run_id"]), {"completed"})
    private_tools, team_tools = offered
    assert {"record_fact", "define_icp", "forget_facts"} <= team_tools
    assert not {"record_fact", "define_icp", "forget_facts"} & private_tools
    assert "find_competitors" in private_tools
