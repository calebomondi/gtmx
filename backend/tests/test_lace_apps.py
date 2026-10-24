"""A Lace's connected apps: X lookups go through the owner's live X
connection; no connection means no lookup, and a refusal is an AppError."""

import uuid
from datetime import UTC, datetime

import psycopg
import pytest

from agents.lace.apps import AppError
from backend.app.database.connect import AsyncSessionLocal
from backend.app.services import lace_apps
from backend.app.services.connections import ConnectionInfo
from config import settings


def _lace() -> uuid.UUID:
    user_id = uuid.uuid4()
    with psycopg.connect(settings.database_url, autocommit=True) as conn:
        return conn.execute("INSERT INTO laces (id, user_id, name, website) VALUES (%s, %s, 'Ada', 'https://acme.test')"
                            " RETURNING id", (uuid.uuid4(), user_id)).fetchone()[0]


def _connections(monkeypatch, platforms):
    async def list_for_user(db, user_id):
        now = datetime.now(UTC)
        return [ConnectionInfo(f"ca_{p}", p, "live", None, now, now) for p in platforms]
    monkeypatch.setattr(lace_apps.connection_service, "list_for_user", list_for_user)


async def test_x_lookups_use_the_owners_live_x(monkeypatch):
    _connections(monkeypatch, ["gmail", "x"])
    calls = []

    def execute(user_id, tool, arguments, connection_id):
        calls.append((tool, arguments["username"], connection_id))
        return {"data": {"data": {"username": "acme"}}, "error": None, "log_id": "l1"}
    monkeypatch.setattr(lace_apps.connection_service, "execute_tool", execute)
    apps = lace_apps.DbLaceApps(AsyncSessionLocal, _lace())
    assert await apps.x("profile", "acme") == {"data": {"username": "acme"}}
    assert calls == [("TWITTER_USER_LOOKUP_BY_USERNAME", "acme", "ca_x")]


async def test_no_x_connection_means_no_lookup(monkeypatch):
    _connections(monkeypatch, ["gmail"])
    monkeypatch.setattr(lace_apps.connection_service, "execute_tool", lambda *a: pytest.fail("not connected"))
    assert await lace_apps.DbLaceApps(AsyncSessionLocal, _lace()).x("post", "42") is None


async def test_a_refused_or_failed_lookup_is_an_app_error(monkeypatch):
    _connections(monkeypatch, ["x"])
    apps = lace_apps.DbLaceApps(AsyncSessionLocal, _lace())
    monkeypatch.setattr(lace_apps.connection_service, "execute_tool",
                        lambda *a: {"data": None, "error": "429 Too Many Requests", "log_id": None})
    with pytest.raises(AppError, match="429"):
        await apps.x("profile", "acme")

    def boom(*a):
        raise ConnectionError("reset")
    monkeypatch.setattr(lace_apps.connection_service, "execute_tool", boom)
    with pytest.raises(AppError, match="ConnectionError"):
        await apps.x("profile", "acme")
