"""Admin gate and the startup admin bootstrap."""

import uuid
from types import SimpleNamespace

import psycopg
import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from backend.app import supabase_admin
from backend.app.services import admin as admin_service
from backend.tests.helpers import FakeSupabase, make_user
from config import settings

API = "/api/v1"


def test_non_admin_is_forbidden(client):
    assert client.get(f"{API}/admin/me").status_code == 403


def test_admin_is_allowed(client):
    admin = make_user("Boss", is_admin=True)
    client.sign_in(admin)
    response = client.get(f"{API}/admin/me")
    assert response.status_code == 200
    assert response.json()["email"] == "boss@example.com"


def _user(email, app_metadata):
    return SimpleNamespace(id=str(uuid.uuid4()), email=email, app_metadata=app_metadata)


@pytest.fixture
def db_sessions():
    engine = create_async_engine(settings.sqlalchemy_database_url, poolclass=NullPool)
    return async_sessionmaker(engine, expire_on_commit=False)


async def test_bootstrap_grants_listed_accounts_once(monkeypatch, db_sessions):
    owner = _user("Owner@Example.com", {"provider": "google"})
    already = _user("already@example.com", {"role": "admin"})
    stranger = _user("stranger@example.com", {})
    fake = FakeSupabase([owner, already, stranger])

    async def get_client():
        return fake
    monkeypatch.setattr(supabase_admin, "get_client", get_client)

    emails = ["owner@example.com", "already@example.com", "nobody-yet@example.com"]
    async with db_sessions() as db:
        assert await admin_service.bootstrap_admins(db, emails) == ["owner@example.com"]
    # Existing app_metadata is preserved; strangers are untouched.
    assert fake.users[owner.id].app_metadata == {"provider": "google", "role": "admin"}
    assert fake.users[stranger.id].app_metadata == {}

    async with db_sessions() as db:
        assert await admin_service.bootstrap_admins(db, emails) == []

    with psycopg.connect(settings.database_url) as conn:
        rows = conn.execute("SELECT action, target_id, actor_id, after FROM admin_audit_log").fetchall()
    assert len(rows) == 1
    action, target_id, actor_id, after = rows[0]
    assert (action, target_id, actor_id) == ("admin.grant", owner.id, None)
    assert after["role"] == "admin"
