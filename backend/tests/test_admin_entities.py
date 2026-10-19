"""Admin entity views: paginated users (from Supabase), runs with their
timeline and cost, and what founders ask their Laces -- all admin-only."""

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
def directory(client, user, owned_runs, monkeypatch):
    """`user` owns a Lace with two runs; two more accounts exist in Supabase."""
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
    assert len(owner) == 1 and owner[0]["laces"] == 1 and owner[0]["runs"] == 2

    detail = client.get(f"{API}/users/{user.id}").json()
    assert [(lace["name"], lace["user_email"]) for lace in detail["lace_list"]] == [("Owner Lace", "owner@example.com")]
    assert len(detail["recent_runs"]) == 2 and detail["spend_usd"] == 0
    assert client.get(f"{API}/users/{uuid.uuid4()}").status_code == 404


def test_run_detail_has_timeline_and_cost(client, owned_runs, directory, monkeypatch):
    monkeypatch.setattr(settings, "llm_prices", {"qwen3.7-plus": [1.0, 1.0]})
    run_id = owned_runs["competitor_run"]
    with psycopg.connect(settings.database_url, autocommit=True) as conn:
        for kind in ("started", "complete"):
            conn.execute("INSERT INTO run_events (run_id, type, payload) VALUES (%s, %s, %s)",
                         (run_id, kind, json.dumps({"k": kind})))
        conn.execute("INSERT INTO llm_calls (run_id, log_label, provider, model, input_tokens, output_tokens, seconds, ok)"
                     " VALUES (%s, 'x', 'qwen', 'qwen3.7-plus', 500000, 500000, 1, true)", (run_id,))

    runs = client.get(f"{API}/runs", params={"kind": "lace_competitors"}).json()
    assert runs["total"] == 1 and runs["items"][0]["cost_usd"] == 1.0
    assert runs["items"][0]["lace_name"] == "Owner Lace"
    detail = client.get(f"{API}/runs/{run_id}").json()
    assert [e["type"] for e in detail["events"]] == ["started", "complete"]
    assert detail["llm_costs"][0]["input_tokens"] == 500000
    assert client.get(f"{API}/runs/{uuid.uuid4()}").status_code == 404


def _ask(user_id, lace_id, text, status="completed"):
    with psycopg.connect(settings.database_url, autocommit=True) as conn:
        conn.execute("INSERT INTO runs (id, user_id, lace_id, kind, status, input) VALUES (%s, %s, %s, 'lace_turn', %s, %s)",
                     (uuid.uuid4(), user_id, lace_id, status, json.dumps({"text": text})))


def test_questions_are_listed_newest_first_and_filterable(client, user, owned_runs, directory):
    lace = owned_runs["lace"]
    with psycopg.connect(settings.database_url, autocommit=True) as conn:
        conn.execute("INSERT INTO runs (id, user_id, lace_id, kind, status) VALUES (%s, %s, %s, 'lace_onboarding',"
                     " 'completed')", (uuid.uuid4(), user.id, lace))
    _ask(user.id, lace, "Who are my top competitors?")
    _ask(user.id, lace, "Draft a note to 100% of Kenya leads", status="running")
    _ask(uuid.uuid4(), None, "Someone else's question")

    page = client.get(f"{API}/questions").json()
    assert page["total"] == 3
    assert [q["text"] for q in page["items"][:2]] == ["Someone else's question", "Draft a note to 100% of Kenya leads"]
    mine = client.get(f"{API}/questions", params={"user_id": str(user.id)}).json()["items"]
    assert [(q["lace_name"], q["user_email"], q["status"]) for q in mine] == [
        ("Owner Lace", "owner@example.com", "running"), ("Owner Lace", "owner@example.com", "completed")]
    assert client.get(f"{API}/questions", params={"lace_id": lace}).json()["total"] == 2
    # The search is a literal match: "%" is not a wildcard.
    assert [q["text"] for q in client.get(f"{API}/questions", params={"q": "100%"}).json()["items"]] == [
        "Draft a note to 100% of Kenya leads"]
    assert client.get(f"{API}/questions", params={"q": "COMPETITORS"}).json()["total"] == 1


@pytest.mark.parametrize("path", ["/users", "/runs", "/questions"])
def test_entities_are_admin_only_and_bounded(client, path):
    assert client.get(f"{API}{path}").status_code == 403
    client.sign_in(make_user("Boss", is_admin=True))
    assert client.get(f"{API}{path}", params={"per_page": 1000}).status_code == 422
