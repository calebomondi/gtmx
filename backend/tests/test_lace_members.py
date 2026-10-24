"""A Lace shared by its founding team: everyone on it sees it whole; admins
and the owner manage it; only the owner archives or deletes it; an invite not
yet accepted, and anyone else, sees nothing."""

import uuid

import psycopg
import pytest

from backend.tests.helpers import make_user, stub_accounts
from backend.tests.test_lace_jobs import lace  # noqa: F401 -- fixture
from backend.tests.test_laces_api import API, lace_runtime  # noqa: F401 -- fixture
from config import settings


def _join(lace_id, user, role="member", status="active"):
    with psycopg.connect(settings.database_url, autocommit=True) as conn:
        conn.execute("INSERT INTO lace_members (id, lace_id, user_id, role, status) VALUES (%s, %s, %s, %s, %s)",
                     (uuid.uuid4(), lace_id, user.id, role, status))


def test_the_creator_is_its_owner(client, lace):  # noqa: F811
    assert client.get(f"{API}/laces/{lace}").json()["role"] == "owner"
    with psycopg.connect(settings.database_url) as conn:
        assert conn.execute("SELECT role, status FROM lace_members WHERE lace_id = %s", (lace,)).fetchall() == [
            ("owner", "active")]


def test_a_cofounder_on_it_sees_the_same_lace(client, user, lace):  # noqa: F811
    cofounder = make_user("Wanjiru")
    _join(lace, cofounder)
    client.sign_in(cofounder)
    seen = client.get(f"{API}/laces/{lace}").json()
    assert (seen["role"], seen["name"]) == ("member", "Ada")
    assert [item["id"] for item in client.get(f"{API}/laces").json()] == [lace]
    assert client.get(f"{API}/laces/{lace}/messages").status_code == 200
    assert client.get(f"{API}/laces/search", params={"q": "Ada"}).json()[0]["lace_id"] == lace


@pytest.mark.parametrize("status", ["invited", "declined"])
def test_an_invite_not_accepted_sees_nothing(client, lace, status):  # noqa: F811
    guest = make_user("Guest")
    _join(lace, guest, status=status)
    client.sign_in(guest)
    assert client.get(f"{API}/laces/{lace}").status_code == 404
    assert client.get(f"{API}/laces").json() == []


@pytest.mark.parametrize("role, admin_ok, owner_ok", [("member", False, False), ("admin", True, False)])
def test_what_each_role_may_change(client, lace, role, admin_ok, owner_ok, monkeypatch):  # noqa: F811
    stub_accounts(monkeypatch, {"slack"})
    person = make_user(role.title())
    _join(lace, person, role=role)
    client.sign_in(person)
    brief = client.patch(f"{API}/laces/{lace}/brief", json={"frequency": "weekly"})
    app = client.put(f"{API}/laces/{lace}/apps/slack", json={"enabled": False})
    assert (brief.status_code == 200, app.status_code == 200) == (admin_ok, admin_ok)
    if not admin_ok:
        assert brief.status_code == 403 and "Only an admin" in brief.json()["detail"]
    archive = client.post(f"{API}/laces/{lace}/archive")
    assert archive.status_code == 403 and "Only the owner" in archive.json()["detail"]
    assert client.delete(f"{API}/laces/{lace}").status_code == 403


def test_pins_are_each_persons_own(client, user, lace):  # noqa: F811
    cofounder = make_user("Wanjiru")
    _join(lace, cofounder)
    client.sign_in(cofounder)
    assert client.patch(f"{API}/laces/{lace}", json={"pinned": True}).json()["pinned"] is True
    client.sign_in(user)
    assert client.get(f"{API}/laces/{lace}").json()["pinned"] is False


def test_everyone_on_it_sees_its_runs(client, user, lace):  # noqa: F811
    with psycopg.connect(settings.database_url) as conn:
        run = conn.execute("SELECT id FROM runs WHERE lace_id = %s", (lace,)).fetchone()[0]
    cofounder = make_user("Wanjiru")
    _join(lace, cofounder)
    client.sign_in(cofounder)
    assert client.get(f"{API}/runs/{run}").status_code == 200
    client.sign_in(make_user("Stranger"))
    assert client.get(f"{API}/runs/{run}").status_code == 404


def test_a_message_is_signed_for_the_lace_only_in_a_team():
    from langchain_core.messages import HumanMessage

    from backend.app.runs import lace as lace_runs
    author = {"id": "u1", "name": "Wanjiru", "avatar_url": None}
    alone = lace_runs.signed(HumanMessage(content="Who replied?"), author, None)
    team = lace_runs.signed(HumanMessage(content="Who replied?"), author, "Wanjiru")
    assert (alone.content, team.content) == ("Who replied?", "[From Wanjiru] Who replied?")
    shown = lace_runs.visible_messages([team])
    assert shown == [{"role": "founder", "content": "Who replied?", "author": author}]


def test_each_message_shows_who_sent_it(client, user, lace, lace_runtime):  # noqa: F811
    from langchain_core.messages import AIMessage

    from backend.tests.test_lace_jobs import _wait_for_turns
    cofounder = make_user("Wanjiru")
    _join(lace, cofounder)
    client.sign_in(cofounder)
    lace_runtime.append(AIMessage(content="Hi Wanjiru."))
    client.post(f"{API}/laces/{lace}/messages", json={"text": "Hello from me"})
    client.portal.call(_wait_for_turns, lace, 1)
    mine = [m for m in client.get(f"{API}/laces/{lace}/messages").json() if m["content"] == "Hello from me"]
    assert mine[0]["author"]["id"] == str(cofounder.id) and mine[0]["author"]["name"] == "Wanjiru"
