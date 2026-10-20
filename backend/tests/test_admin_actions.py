"""Admin writes: role changes (never self-revoke, never the last admin),
suspension (blocks access and stops runs), run cancel and quota overrides.
Every write leaves an audit row."""

import uuid

import psycopg
import pytest

from backend.app import supabase_admin
from backend.app.api import deps
from backend.app.services import limits
from backend.tests.helpers import FakeSupabase, make_user, supabase_user
from config import settings

API = "/api/v1/admin"


@pytest.fixture
def boss():
    return make_user("Boss", is_admin=True)


@pytest.fixture
def fake(client, user, boss, monkeypatch):
    fake = FakeSupabase([
        supabase_user(boss.id, boss.email, {"role": "admin"}),
        supabase_user(user.id, user.email),
    ])

    async def get_client():
        return fake
    monkeypatch.setattr(supabase_admin, "get_client", get_client)
    client.sign_in(boss)
    return fake


def _audit_actions():
    with psycopg.connect(settings.database_url) as conn:
        return [r[0] for r in conn.execute("SELECT action FROM admin_audit_log ORDER BY created_at")]


def test_grant_then_revoke_admin_with_guards(client, user, boss, fake):
    assert client.delete(f"{API}/users/{boss.id}/admin").status_code == 409  # self
    assert client.post(f"{API}/users/{user.id}/admin").json()["is_admin"] is True
    assert client.delete(f"{API}/users/{user.id}/admin").json()["is_admin"] is False
    assert _audit_actions() == ["admin.grant", "admin.revoke"]
    assert client.post(f"{API}/users/{uuid.uuid4()}/admin").status_code == 404


def test_last_admin_cannot_be_removed(client, user, boss, fake):
    fake.users[str(user.id)].app_metadata = {"role": "admin"}
    client.sign_in(make_user("Other", is_admin=True))
    assert client.delete(f"{API}/users/{boss.id}/admin").status_code == 200  # two admins -> one
    assert client.delete(f"{API}/users/{user.id}/admin").status_code == 409  # the last one stays


def test_suspend_stops_runs_and_blocks_tokens(client, user, boss, owned_runs, fake):
    with psycopg.connect(settings.database_url, autocommit=True) as conn:
        conn.execute("UPDATE runs SET status = 'running' WHERE id = %s", (owned_runs["competitor_run"],))
    assert client.post(f"{API}/users/{boss.id}/suspend", json={"reason": "test"}).status_code == 409
    suspended = client.post(f"{API}/users/{user.id}/suspend", json={"reason": "abuse"}).json()
    assert suspended["suspended"] is True
    run = client.get(f"{API}/runs/{owned_runs['competitor_run']}").json()
    assert run["status"] == "cancelled"
    assert supabase_admin.is_suspended(fake.users[str(user.id)].banned_until)

    assert client.post(f"{API}/users/{user.id}/reactivate").json()["suspended"] is False
    assert _audit_actions() == ["user.suspend", "user.reactivate"]


async def test_banned_token_is_refused(monkeypatch, user):
    banned = supabase_user(user.id, user.email)
    banned.banned_until = "2999-01-01T00:00:00Z"

    class Auth:
        async def get_user(self, token):
            return type("R", (), {"user": banned})()

    async def get_client():
        return type("C", (), {"auth": Auth()})()
    monkeypatch.setattr(supabase_admin, "get_client", get_client)
    assert await deps.user_from_token("token") is None


def test_cancel_run_is_audited_and_terminal_runs_conflict(client, owned_runs, fake):
    with psycopg.connect(settings.database_url, autocommit=True) as conn:
        conn.execute("UPDATE runs SET status = 'running' WHERE id = %s", (owned_runs["account_run"],))
    assert client.post(f"{API}/runs/{owned_runs['account_run']}/cancel").json()["status"] == "cancelled"
    assert client.post(f"{API}/runs/{owned_runs['account_run']}/cancel").status_code == 409
    audit = client.get(f"{API}/audit-log", params={"action": "run.cancel"}).json()
    assert audit["total"] == 1 and audit["items"][0]["before"] == {"status": "running"}


async def _cap(user_id, kind):
    from backend.app.database.connect import AsyncSessionLocal
    async with AsyncSessionLocal() as db:
        return await limits.daily_cap(db, user_id, kind)


def test_quota_override_changes_the_cap(client, user, fake):
    path = f"{API}/users/{user.id}/quotas"
    rows = client.put(path, json={"kind": "discovery", "daily_cap": 1}).json()
    assert next(r for r in rows if r["kind"] == "discovery")["override"] == 1
    assert client.portal.call(_cap, user.id, "discovery") == 1
    client.put(path, json={"kind": "discovery", "daily_cap": None})
    assert client.portal.call(_cap, user.id, "discovery") == settings.max_discovery_runs_per_day
    assert client.put(path, json={"kind": "nope", "daily_cap": 3}).status_code == 422
    assert _audit_actions() == ["quota.set", "quota.set"]


def test_every_run_kind_has_a_default_cap():
    from backend.app.runs.kinds import RUN_KINDS
    assert all(limits.default_daily_cap(k) > 0 for k in RUN_KINDS)


def test_actions_need_admin(client, user):
    client.sign_in(make_user("Pleb"))
    assert client.post(f"{API}/users/{user.id}/admin").status_code == 403
    assert client.get(f"{API}/audit-log").status_code == 403
