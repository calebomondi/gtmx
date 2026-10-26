"""The closed pilot: with settings.pilot_invite_only_since set, only admins,
emails an admin let in, people invited onto a Lace and accounts made before
it closed may use the customer API; /users/me says whether you're in.
Admins keep the guest list (typed in or from the waitlist), audited."""

import dataclasses
import uuid
from datetime import UTC, datetime, timedelta

import psycopg
import pytest

from backend.app.services import admin_pilot, email
from backend.tests.helpers import make_user
from backend.tests.test_lace_members import _join
from config import settings

API = "/api/v1"
NEWCOMER = make_user("Newcomer")
BOSS = make_user("Boss", is_admin=True)


@pytest.fixture
def closed(monkeypatch):
    monkeypatch.setattr(settings, "pilot_invite_only_since", datetime.now(UTC))

    async def accounts():
        return {NEWCOMER.id: "Newcomer@Example.com"}
    monkeypatch.setattr(admin_pilot, "emails_by_id", accounts)


def _in(client, who) -> bool:
    client.sign_in(who)
    me = client.get(f"{API}/users/me").json()["in_pilot"]
    assert (client.get(f"{API}/laces").status_code == 200) is me
    return me


def _audit():
    with psycopg.connect(settings.database_url) as conn:
        return [r[0] for r in conn.execute("SELECT action FROM admin_audit_log ORDER BY created_at")]


def test_an_open_app_lets_everyone_in(client):
    assert client.get(f"{API}/pilot").json() == {"invite_only": False}
    assert _in(client, NEWCOMER)


def test_a_closed_pilot_keeps_out_whoever_was_not_let_in(client, closed):
    assert client.get(f"{API}/pilot").json() == {"invite_only": True}
    assert not _in(client, NEWCOMER)
    assert _in(client, BOSS)
    earlier = dataclasses.replace(make_user("Early"), created_at=datetime.now(UTC) - timedelta(days=30))
    assert _in(client, earlier)


def test_admins_let_emails_in_and_take_them_off(client, closed):
    client.sign_in(BOSS)
    added = client.post(f"{API}/admin/pilot-access", json={"emails": ["newcomer@example.com", "NEWCOMER@example.com",
                                                                     "cofounder@example.com"]})
    assert added.json() == {"added": 2}
    assert client.post(f"{API}/admin/pilot-access", json={"emails": ["newcomer@example.com"]}).json() == {"added": 0}
    assert client.post(f"{API}/admin/pilot-access", json={"emails": ["not an email"]}).status_code == 422
    rows = {r["email"]: r for r in client.get(f"{API}/admin/pilot-access").json()["items"]}
    assert {e: (r["source"], r["signed_up"], r["granted_by_email"]) for e, r in rows.items()} == {
        "newcomer@example.com": ("admin", True, BOSS.email), "cofounder@example.com": ("admin", False, BOSS.email)}
    assert _in(client, NEWCOMER)

    client.sign_in(BOSS)
    assert client.delete(f"{API}/admin/pilot-access/{rows['newcomer@example.com']['id']}").status_code == 204
    assert not _in(client, NEWCOMER)
    assert _audit() == ["pilot.let_in", "pilot.remove"]


def test_someone_invited_onto_a_lace_is_in(client, user, closed):
    lace_id = uuid.uuid4()
    with psycopg.connect(settings.database_url, autocommit=True) as conn:
        conn.execute("INSERT INTO laces (id, user_id, name, website, status) VALUES (%s, %s, 'Acme', 'https://acme.test',"
                     " 'active')", (lace_id, user.id))
    _join(lace_id, NEWCOMER, status="invited")
    assert _in(client, NEWCOMER)
    assert [i["lace_id"] for i in client.get(f"{API}/laces/invites").json()] == [str(lace_id)]


def test_a_waitlist_signup_is_approved_into_the_pilot(client, closed, monkeypatch):
    async def no_email(*_):
        return True
    monkeypatch.setattr(email, "send", no_email)
    client.post(f"{API}/waitlist", json={"email": "Newcomer@example.com", "consent": True},
                headers={"X-Real-IP": "10.2.0.1"})
    client.sign_in(BOSS)
    [signup] = client.get(f"{API}/admin/waitlist").json()["items"]
    approved = client.post(f"{API}/admin/waitlist/{signup['id']}/approve").json()
    assert approved["status"] == "invited"
    assert client.get(f"{API}/admin/pilot-access").json()["items"][0]["source"] == "waitlist"
    assert _in(client, NEWCOMER)
    assert _audit() == ["pilot.let_in", "waitlist.status"]


@pytest.mark.parametrize(("method", "path"), [("get", "/admin/pilot-access"), ("post", "/admin/pilot-access"),
                                              ("delete", f"/admin/pilot-access/{uuid.uuid4()}")])
def test_the_guest_list_is_admin_only(client, method, path):
    assert getattr(client, method)(f"{API}{path}").status_code == 403
