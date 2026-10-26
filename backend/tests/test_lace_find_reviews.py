"""Pushing private finds to the team and reviewing them: another member
approves (the find becomes the team's, saved, merged into the team's own
copy) or sends it back with a note; admins and the owner may approve their
own; a private account never takes a person from the team's."""

import uuid

import psycopg
import pytest

from agents.schemas.accounts import ContactRecord
from backend.app import supabase_admin
from backend.app.database.connect import AsyncSessionLocal
from backend.app.services import lace_contacts
from backend.tests.helpers import FakeSupabase, make_user, supabase_user
from backend.tests.test_lace_jobs import lace  # noqa: F401 -- fixture
from backend.tests.test_lace_members import _join
from backend.tests.test_lace_private_finds import _seed
from backend.tests.test_laces_api import API, lace_runtime  # noqa: F401 -- fixture
from config import settings

WANJIRU = make_user("Wanjiru")


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


def _mine(client, lace_id):
    return {f["name"]: f for f in client.get(f"{API}/laces/{lace_id}/my-finds").json()}


def _push(client, lace_id, *finds):
    return client.post(f"{API}/laces/{lace_id}/my-finds/push",
                       json={"items": [{"kind": f["kind"], "id": f["id"]} for f in finds]})


def _decide(client, lace_id, find, verdict, note=None):
    return client.post(f"{API}/laces/{lace_id}/reviews/{find['kind']}/{find['id']}/{verdict}",
                       json={"note": note} if verdict == "send-back" else None)


def test_a_push_waits_for_someone_else(client, user, team):
    client.portal.call(_seed, team, WANJIRU.id)
    assert _mine(client, team) == {}
    client.sign_in(WANJIRU)
    mine = _mine(client, team)
    assert set(mine) == {"Rival", "Acme", "Demo Day"}
    assert _push(client, team, mine["Rival"], mine["Acme"]).json() == {"pushed": 2}
    assert _push(client, team, mine["Rival"]).json() == {"pushed": 0}
    assert _mine(client, team)["Rival"]["proposed_at"]

    waiting = client.get(f"{API}/laces/{team}/reviews").json()
    assert {(f["name"], f["can_review"]) for f in waiting} == {("Rival", False), ("Acme", False)}
    assert _decide(client, team, mine["Rival"], "approve").status_code == 403

    client.sign_in(user)
    waiting = client.get(f"{API}/laces/{team}/reviews").json()
    assert {(f["name"], f["can_review"], f["owner"]["name"]) for f in waiting} == {
        ("Rival", True, "Wanjiru Kamau"), ("Acme", True, "Wanjiru Kamau")}
    [pushed] = client.get(f"{API}/laces/{team}/activity").json()
    assert (pushed["kind"], pushed["title"], pushed["read_at"]) == ("finds_proposed", "2 finds to review", None)


def test_approving_makes_it_the_team_s(client, user, team):
    client.portal.call(_seed, team, WANJIRU.id)
    client.sign_in(WANJIRU)
    rival = _mine(client, team)["Rival"]
    _push(client, team, rival)
    client.sign_in(user)
    assert _decide(client, team, rival, "approve").status_code == 204
    assert [c["name"] for c in client.get(f"{API}/laces/{team}/competitors", params={"status": "tracked"}).json()] == [
        "Rival"]
    assert client.get(f"{API}/laces/{team}/reviews").json() == []
    saved = client.get(f"{API}/laces/{team}/activity").json()[0]
    assert (saved["kind"], saved["title"], saved["actor"]["name"]) == (
        "competitor_saved", "Saved Rival as a competitor", "Wanjiru Kamau")
    with psycopg.connect(settings.database_url) as conn:
        [(update,)] = conn.execute("SELECT text FROM lace_events WHERE owner_id IS NULL").fetchall()
    assert "Rival (competitor)" in update and "approved for the team" in update
    client.sign_in(WANJIRU)
    assert "Rival" not in _mine(client, team)


def test_sending_back_returns_it_with_a_note(client, user, team):
    client.portal.call(_seed, team, WANJIRU.id)
    client.sign_in(WANJIRU)
    acme = _mine(client, team)["Acme"]
    _push(client, team, acme)
    client.sign_in(user)
    assert _decide(client, team, acme, "send-back", "We already sell to them.").status_code == 204
    returned = client.get(f"{API}/laces/{team}/activity").json()[0]
    assert (returned["kind"], returned["title"], returned["summary"]) == (
        "finds_returned", "Sent Acme back", "We already sell to them.")
    assert client.get(f"{API}/laces/{team}/accounts", params={"status": "target"}).json() == []
    client.sign_in(WANJIRU)
    back = _mine(client, team)["Acme"]
    assert (back["proposed_at"], back["review_note"]) == (None, "We already sell to them.")


def test_an_approved_account_merges_into_the_team_s_copy(client, user, team):
    client.portal.call(_seed, team, None)
    client.portal.call(_seed, team, WANJIRU.id)
    with psycopg.connect(settings.database_url) as conn:
        [(private_acme,)] = conn.execute("SELECT id FROM lace_accounts WHERE owner_id IS NOT NULL").fetchall()

    async def add_jane():
        async with AsyncSessionLocal() as db:
            await lace_contacts.sync(db, uuid.UUID(team), private_acme,
                                     [ContactRecord(name="Jane Doe", email="jane@acme.test")], "contact_search")
            await db.commit()
    client.portal.call(add_jane)
    client.sign_in(WANJIRU)
    acme = _mine(client, team)["Acme"]
    _push(client, team, acme)
    client.sign_in(user)
    _decide(client, team, acme, "approve")
    [team_acme] = client.get(f"{API}/laces/{team}/accounts", params={"status": "target"}).json()
    with psycopg.connect(settings.database_url) as conn:
        assert conn.execute("SELECT count(*) FROM lace_accounts").fetchone()[0] == 1
        assert conn.execute("SELECT account_id FROM lace_contacts").fetchone()[0] == uuid.UUID(team_acme["id"])


def test_the_owner_may_approve_their_own(client, user, team):
    client.portal.call(_seed, team, user.id)
    demo = _mine(client, team)["Demo Day"]
    _push(client, team, demo)
    assert client.get(f"{API}/laces/{team}/reviews").json()[0]["can_review"] is True
    assert _decide(client, team, demo, "approve").status_code == 204
    assert [o["title"] for o in client.get(f"{API}/laces/{team}/opportunities").json()] == ["Demo Day"]


def test_a_private_account_never_takes_a_team_contact(client, team):
    client.portal.call(_seed, team, None)
    client.portal.call(_seed, team, WANJIRU.id)
    with psycopg.connect(settings.database_url) as conn:
        accounts = dict(conn.execute("SELECT coalesce(owner_id::text, 'team'), id FROM lace_accounts").fetchall())
    jane = [ContactRecord(name="Jane Doe", email="jane@acme.test")]

    async def sight(account_id):
        async with AsyncSessionLocal() as db:
            await lace_contacts.sync(db, uuid.UUID(team), account_id, jane, "contact_search")
            await db.commit()
    client.portal.call(sight, accounts["team"])
    client.portal.call(sight, accounts[str(WANJIRU.id)])
    with psycopg.connect(settings.database_url) as conn:
        assert conn.execute("SELECT account_id FROM lace_contacts").fetchone()[0] == accounts["team"]
