"""Team history: on a Lace with a team, each Feed item names who did it or
asked for it; what a person does there (joining, saving a find, sending a
message) is recorded too, already read. A Lace of one shows no names."""

import uuid

import pytest
from langchain_core.messages import AIMessage

from backend.app import supabase_admin
from backend.app.runs import lace_jobs, manager
from backend.tests.helpers import FakeSupabase, make_user, supabase_user
from backend.tests.test_lace_jobs import RIVAL, _call, _wait_for_turns, lace  # noqa: F401 -- fixture
from backend.tests.test_lace_members import _join
from backend.tests.test_lace_outreach import _message
from backend.tests.test_laces_api import API, lace_runtime  # noqa: F401 -- fixture
from backend.tests.test_runs import _wait_for_status

WANJIRU = make_user("Wanjiru")
AS_WANJIRU = {"id": str(WANJIRU.id), "name": "Wanjiru Kamau", "avatar_url": None}


@pytest.fixture
def team(monkeypatch, user, lace):  # noqa: F811
    """The founder's Lace, with Wanjiru on it as a member."""
    users = [supabase_user(u.id, u.email) for u in (user, WANJIRU)]
    users[1].user_metadata = {"full_name": "Wanjiru Kamau"}
    fake = FakeSupabase(users)

    async def get_client():
        return fake
    monkeypatch.setattr(supabase_admin, "get_client", get_client)
    _join(lace, WANJIRU)
    return lace


def _feed(client, lace_id):
    return client.get(f"{API}/laces/{lace_id}/activity").json()


def _hunt(client, user, lace_id, params):
    run = client.portal.call(manager.start_lace_job, "lace_competitors", user.id, uuid.UUID(lace_id), params)
    client.portal.call(_wait_for_status, run.id, {"completed"})
    client.portal.call(_wait_for_turns, lace_id, 1)


@pytest.fixture
def rival(monkeypatch, lace_runtime):  # noqa: F811
    monkeypatch.setattr(lace_jobs, "find_competitors", lambda profile, facts, focus: [RIVAL])
    lace_runtime.append(AIMessage(content="I found Rival."))


def test_a_search_names_who_asked_for_it(client, user, team, rival):
    _hunt(client, user, team, {"actor_id": str(WANJIRU.id)})
    [item] = _feed(client, team)
    assert (item["kind"], item["actor"]) == ("competitors_found", AS_WANJIRU)


def test_the_lace_s_own_work_names_nobody(client, user, team, rival):
    _hunt(client, user, team, {"scheduled": True})
    assert _feed(client, team)[0]["actor"] is None


def test_a_lace_of_one_names_nobody(client, user, lace, rival):  # noqa: F811
    _hunt(client, user, lace, {"actor_id": str(user.id)})
    assert _feed(client, lace)[0]["actor"] is None


def test_what_the_lace_does_for_someone_in_chat_is_theirs(client, team, monkeypatch, lace_runtime):  # noqa: F811
    monkeypatch.setattr(lace_jobs, "find_competitors", lambda profile, facts, focus: [RIVAL])
    lace_runtime.extend([_call("find_competitors"), AIMessage(content="On it."), AIMessage(content="Found Rival.")])
    client.sign_in(WANJIRU)
    client.post(f"{API}/laces/{team}/messages", json={"text": "who competes with us?"})
    client.portal.call(_wait_for_turns, team, 2)
    [item] = _feed(client, team)
    assert (item["kind"], item["actor"]) == ("competitors_found", AS_WANJIRU)

    [found] = client.get(f"{API}/laces/{team}/competitors", params={"status": "suggested"}).json()
    client.patch(f"{API}/laces/{team}/competitors/{found['id']}", json={"status": "tracked"})
    saved = _feed(client, team)[0]
    assert (saved["kind"], saved["title"], saved["actor"]) == ("competitor_saved", "Saved Rival as a competitor", AS_WANJIRU)
    assert saved["read_at"] is not None


def test_dismissing_a_find_is_not_history(client, user, team, rival):
    _hunt(client, user, team, {})
    [found] = client.get(f"{API}/laces/{team}/competitors", params={"status": "suggested"}).json()
    client.patch(f"{API}/laces/{team}/competitors/{found['id']}", json={"status": "dismissed"})
    assert [i["kind"] for i in _feed(client, team)] == ["competitors_found"]


def test_a_message_sent_by_hand_is_history(client, user, team):
    linkedin = _message(team, user.id, channel="linkedin", address="https://linkedin.com/in/jane")
    client.sign_in(WANJIRU)
    assert client.post(f"{API}/laces/{team}/outreach/{linkedin}/mark-sent").status_code == 200
    [item] = _feed(client, team)
    assert (item["kind"], item["title"], item["actor"]) == (
        "message_sent", "Sent a message to https://linkedin.com/in/jane", AS_WANJIRU)


def test_joining_is_history(client, user, lace, monkeypatch):  # noqa: F811
    users = [supabase_user(u.id, u.email) for u in (user, WANJIRU)]
    users[1].user_metadata = {"full_name": "Wanjiru Kamau"}
    fake = FakeSupabase(users)

    async def get_client():
        return fake
    monkeypatch.setattr(supabase_admin, "get_client", get_client)
    _join(lace, WANJIRU, status="invited")
    client.sign_in(WANJIRU)
    assert client.post(f"{API}/laces/invites/{lace}/accept").status_code == 204
    [item] = _feed(client, lace)
    assert (item["kind"], item["title"], item["actor"]) == ("member_joined", "Joined the team", AS_WANJIRU)
