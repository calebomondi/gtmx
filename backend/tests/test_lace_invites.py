"""Bringing cofounders onto a Lace: invites by email to people who signed up,
answered by them; roles and removal by those who manage it."""

import pytest

from backend.app import supabase_admin
from backend.tests.helpers import FakeSupabase, make_user, supabase_user
from backend.tests.test_lace_jobs import lace  # noqa: F401 -- fixture
from backend.tests.test_laces_api import API, lace_runtime  # noqa: F401 -- fixture

WANJIRU = make_user("Wanjiru")
OTIENO = make_user("Otieno")


@pytest.fixture
def people(monkeypatch, user):
    """Everyone signed up: the founder, Wanjiru and Otieno."""
    users = [supabase_user(u.id, u.email) for u in (user, WANJIRU, OTIENO)]
    users[1].user_metadata = {"full_name": "Wanjiru Kamau", "avatar_url": "https://img.test/w.png"}
    fake = FakeSupabase(users)

    async def client():
        return fake
    monkeypatch.setattr(supabase_admin, "get_client", client)
    return fake


def _invite(client, lace_id, who, role="member"):
    return client.post(f"{API}/laces/{lace_id}/members", json={"email": who.email.upper(), "role": role})


def test_an_invite_is_answered_by_the_invitee(client, user, lace, people):  # noqa: F811
    invited = _invite(client, lace, WANJIRU)
    assert invited.status_code == 201 and invited.json()["status"] == "invited"
    client.sign_in(WANJIRU)
    assert client.get(f"{API}/laces/{lace}").status_code == 404  # nothing until accepted
    [invite] = client.get(f"{API}/laces/invites").json()
    assert (invite["lace_id"], invite["lace_name"], invite["role"], invite["invited_by"]) == (
        lace, "Ada", "member", user.email)
    assert client.post(f"{API}/laces/invites/{lace}/accept").status_code == 204
    assert client.get(f"{API}/laces/{lace}").json()["role"] == "member"
    assert client.get(f"{API}/laces/invites").json() == []
    team = client.get(f"{API}/laces/{lace}/members").json()
    assert [(p["email"], p["role"], p["status"]) for p in team] == [
        (user.email, "owner", "active"), (WANJIRU.email, "member", "active")]
    assert team[1]["name"] == "Wanjiru Kamau" and team[1]["avatar_url"] == "https://img.test/w.png"


def test_a_declined_invite_can_be_sent_again(client, user, lace, people):  # noqa: F811
    _invite(client, lace, WANJIRU)
    client.sign_in(WANJIRU)
    assert client.post(f"{API}/laces/invites/{lace}/decline").status_code == 204
    assert client.post(f"{API}/laces/invites/{lace}/accept").status_code == 404
    assert client.get(f"{API}/laces").json() == []
    client.sign_in(user)
    assert _invite(client, lace, WANJIRU).status_code == 201


def test_only_people_who_signed_up_can_be_invited(client, lace, people):  # noqa: F811
    refused = client.post(f"{API}/laces/{lace}/members", json={"email": "nobody@acme.test"})
    assert refused.status_code == 422 and "sign up first" in refused.json()["detail"]
    _invite(client, lace, WANJIRU)
    assert _invite(client, lace, WANJIRU).status_code == 409


def test_what_admins_and_members_may_do_with_people(client, user, lace, people):  # noqa: F811
    _invite(client, lace, WANJIRU, role="admin")
    _invite(client, lace, OTIENO)
    for who in (WANJIRU, OTIENO):
        client.sign_in(who)
        client.post(f"{API}/laces/invites/{lace}/accept")

    client.sign_in(OTIENO)  # a member manages no one
    assert _invite(client, lace, make_user("Zed")).status_code == 403
    assert client.delete(f"{API}/laces/{lace}/members/{WANJIRU.id}").status_code == 403

    client.sign_in(WANJIRU)  # an admin removes members, not admins or the owner, and invites no admins
    assert _invite(client, lace, OTIENO, role="admin").status_code in (403, 409)
    assert client.delete(f"{API}/laces/{lace}/members/{user.id}").status_code == 422
    assert client.patch(f"{API}/laces/{lace}/members/{OTIENO.id}", json={"role": "admin"}).status_code == 403
    assert client.delete(f"{API}/laces/{lace}/members/{OTIENO.id}").status_code == 204

    client.sign_in(user)  # the owner changes roles and removes admins, but can't leave
    assert client.patch(f"{API}/laces/{lace}/members/{WANJIRU.id}", json={"role": "member"}).status_code == 204
    assert client.post(f"{API}/laces/{lace}/leave").status_code == 422
    client.sign_in(WANJIRU)
    assert client.post(f"{API}/laces/{lace}/leave").status_code == 204
    assert client.get(f"{API}/laces/{lace}").status_code == 404
