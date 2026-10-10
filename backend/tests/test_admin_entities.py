"""Admin entity views: paginated users (from Supabase), workspaces, runs with
their timeline and cost, and signals -- all admin-only."""

import json
import uuid
from types import SimpleNamespace

import psycopg
import pytest

from backend.app.services import admin as admin_service
from backend.app.services import admin_directory
from backend.app.services.errors import NotFoundError
from backend.tests.helpers import make_user
from config import settings

API = "/api/v1/admin"


def _supabase_user(uid, email, created, **extra):
    return SimpleNamespace(id=str(uid), email=email, created_at=created, last_sign_in_at=None,
                           app_metadata=extra.get("app_metadata", {}), user_metadata={"full_name": email.split("@")[0]},
                           banned_until=extra.get("banned_until"))


@pytest.fixture
def directory(client, user, owned, monkeypatch):
    """`user` owns the seeded workspace; two more accounts exist in Supabase."""
    people = [
        _supabase_user(user.id, "owner@example.com", "2026-10-01T00:00:00Z"),
        _supabase_user(uuid.uuid4(), "zed@example.com", "2026-10-03T00:00:00Z", banned_until="2999-01-01T00:00:00Z"),
        _supabase_user(uuid.uuid4(), "boss@example.com", "2026-10-02T00:00:00Z", app_metadata={"role": "admin"}),
    ]

    async def all_users():
        return list(people)

    async def one_user(uid):
        for p in people:
            if p.id == str(uid):
                return p
        raise NotFoundError("User not found.")
    monkeypatch.setattr(admin_service, "list_all_users", all_users)
    monkeypatch.setattr(admin_directory, "get_supabase_user", one_user)
    client.sign_in(make_user("Boss", is_admin=True))
    return people


def test_users_are_paginated_searchable_and_carry_activity(client, user, directory):
    first = client.get(f"{API}/users", params={"per_page": 2}).json()
    assert first["total"] == 3 and [u["email"] for u in first["items"]] == ["zed@example.com", "boss@example.com"]
    assert first["items"][0]["suspended"] and first["items"][1]["is_admin"]
    owner = client.get(f"{API}/users", params={"q": "OWNER"}).json()["items"]
    assert len(owner) == 1 and owner[0]["workspaces"] == 1 and owner[0]["runs"] == 2

    detail = client.get(f"{API}/users/{user.id}").json()
    assert detail["workspace_list"][0]["user_email"] == "owner@example.com"
    assert len(detail["recent_runs"]) == 2 and detail["spend_usd"] == 0
    assert client.get(f"{API}/users/{uuid.uuid4()}").status_code == 404


def test_run_detail_has_timeline_and_cost(client, owned, directory, monkeypatch):
    monkeypatch.setattr(settings, "llm_prices", {"qwen3.7-plus": [1.0, 1.0]})
    run_id = owned["competitor_run"]
    with psycopg.connect(settings.database_url, autocommit=True) as conn:
        for kind in ("started", "complete"):
            conn.execute("INSERT INTO run_events (run_id, type, payload) VALUES (%s, %s, %s)",
                         (run_id, kind, json.dumps({"k": kind})))
        conn.execute("INSERT INTO llm_calls (run_id, log_label, provider, model, input_tokens, output_tokens, seconds, ok)"
                     " VALUES (%s, 'x', 'qwen', 'qwen3.7-plus', 500000, 500000, 1, true)", (run_id,))

    runs = client.get(f"{API}/runs", params={"kind": "competitors"}).json()
    assert runs["total"] == 1 and runs["items"][0]["cost_usd"] == 1.0
    assert runs["items"][0]["workspace_name"] == "Owner Workspace"
    detail = client.get(f"{API}/runs/{run_id}").json()
    assert [e["type"] for e in detail["events"]] == ["started", "complete"]
    assert detail["llm_costs"][0]["input_tokens"] == 500000
    assert client.get(f"{API}/runs/{uuid.uuid4()}").status_code == 404


def test_workspaces_and_signals_listing(client, owned, directory):
    with psycopg.connect(settings.database_url, autocommit=True) as conn:
        conn.execute(
            "INSERT INTO signals (id, user_id, workspace_id, category, title, entity, summary, reason)"
            " SELECT %s, user_id, id, 'competitor', 'Rival cut prices', '', '', '' FROM workspaces WHERE id = %s",
            (uuid.uuid4(), owned["workspace"]),
        )
    workspaces = client.get(f"{API}/workspaces", params={"q": "owner"}).json()
    assert workspaces["total"] == 1 and workspaces["items"][0]["competitors"] == 1
    signals = client.get(f"{API}/signals").json()
    assert signals["items"][0]["title"] == "Rival cut prices"
    assert signals["items"][0]["user_email"] == "owner@example.com"


@pytest.mark.parametrize("path", ["/users", "/workspaces", "/runs", "/signals"])
def test_entities_are_admin_only_and_bounded(client, path):
    assert client.get(f"{API}{path}").status_code == 403
    client.sign_in(make_user("Boss", is_admin=True))
    assert client.get(f"{API}{path}", params={"per_page": 1000}).status_code == 422
