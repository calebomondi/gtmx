"""Admin engagement, funnel and connection metrics, the users list's activity
columns, and the user detail's activity and connected accounts."""

import json
import uuid
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import psycopg
import pytest

from backend.app.services import admin as admin_service
from backend.app.services import admin_directory
from backend.app.services import connections as connection_service
from backend.tests.helpers import make_user
from config import settings

API = "/api/v1/admin"
NOW = datetime.now(UTC)


def _person(uid, email, created):
    return SimpleNamespace(id=str(uid), email=email, created_at=created.isoformat(), last_sign_in_at=None,
                           app_metadata={}, user_metadata={}, banned_until=None)


@pytest.fixture
def world(client, monkeypatch):
    """Three users: `ann` (busy), `bob` (an onboarding failed), `cat` (signed up long ago, idle)."""
    ann, bob, cat = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    people = [_person(ann, "ann@example.com", NOW), _person(bob, "bob@example.com", NOW),
              _person(cat, "cat@example.com", NOW - timedelta(days=40))]

    async def all_users():
        return list(people)

    async def one_user(uid):
        return next(p for p in people if p.id == str(uid))
    monkeypatch.setattr(admin_service, "list_all_users", all_users)
    monkeypatch.setattr(admin_directory, "get_supabase_user", one_user)
    monkeypatch.setattr(settings, "llm_prices", {"qwen3.7-plus": [1.0, 1.0]})

    widgets, audits, old, bobs, onboarding, account = (uuid.uuid4() for _ in range(6))
    with psycopg.connect(settings.database_url, autocommit=True) as c:
        c.execute("INSERT INTO laces (id, user_id, name, website, status) VALUES (%s, %s, 'Widgets', 'https://w.test',"
                  " 'active'), (%s, %s, 'Audits', 'https://a.test', 'active'), (%s, %s, 'Bobs', 'https://b.test',"
                  " 'onboarding')", (widgets, ann, audits, ann, bobs, bob))
        c.execute("INSERT INTO laces (id, user_id, name, website, status, created_at) VALUES (%s, %s, 'Old',"
                  " 'https://o.test', 'active', %s)", (old, cat, NOW - timedelta(days=40)))
        for uid, started, seconds in [(ann, NOW, 600), (ann, NOW - timedelta(days=2), 300), (bob, NOW, 120)]:
            c.execute("INSERT INTO app_sessions (user_id, started_at, last_seen_at, active_seconds)"
                      " VALUES (%s, %s, %s, %s)", (uid, started, started, seconds))
        c.execute("INSERT INTO runs (id, user_id, lace_id, kind, status, started_at, finished_at)"
                  " VALUES (%s, %s, %s, 'lace_onboarding', 'completed', %s, %s)",
                  (onboarding, ann, widgets, NOW - timedelta(minutes=3), NOW))
        c.execute("INSERT INTO runs (id, user_id, lace_id, kind, status, error, finished_at) VALUES"
                  " (%s, %s, %s, 'lace_onboarding', 'failed', 'boom', %s)", (uuid.uuid4(), bob, bobs, NOW))
        for kind, input_ in [("lace_turn", {"text": "Who are my rivals?"}), ("lace_turn", {"text": "Any leads?"}),
                             ("lace_accounts", None), ("lace_competitors", None)]:
            c.execute("INSERT INTO runs (id, user_id, lace_id, kind, status, input) VALUES (%s, %s, %s, %s,"
                      " 'completed', %s)", (uuid.uuid4(), ann, widgets, kind, json.dumps(input_) if input_ else None))
        c.execute("INSERT INTO runs (id, user_id, lace_id, kind, status) VALUES (%s, %s, %s, 'lace_turn', 'completed')",
                  (uuid.uuid4(), ann, audits))
        # A deleted account's history: never counted as a person.
        c.execute("INSERT INTO runs (id, user_id, kind, status, created_at) VALUES (%s, %s, 'lace_onboarding',"
                  " 'completed', %s)", (uuid.uuid4(), uuid.uuid4(), NOW - timedelta(days=60)))
        c.execute("INSERT INTO llm_calls (run_id, log_label, provider, model, input_tokens, output_tokens, seconds, ok)"
                  " VALUES (%s, 'x', 'qwen', 'qwen3.7-plus', 1000000, 1000000, 1, true)", (onboarding,))
        for kind in ("accounts_found", "brief", "brief"):
            c.execute("INSERT INTO lace_activity (id, lace_id, kind, title) VALUES (%s, %s, %s, 'x')",
                      (uuid.uuid4(), audits, kind))
        c.execute("INSERT INTO lace_accounts (id, lace_id, key, name, account_type, record, status) VALUES"
                  " (%s, %s, 'acme.test', 'Acme', 'company', '{\"name\": \"Acme\"}', 'target')", (account, widgets))
        c.execute("INSERT INTO lace_contacts (id, lace_id, account_id, key, name, source, approved_at) VALUES"
                  " (%s, %s, %s, 'amina', 'Amina', 'discovery', %s)", (uuid.uuid4(), widgets, account, NOW))
        c.execute("INSERT INTO lace_outreach (id, lace_id, user_id, channel, recipient_company, body, status, sent_at,"
                  " direction) VALUES (%s, %s, %s, 'email', 'Acme', 'x', 'sent', %s, 'outbound'),"
                  " (%s, %s, %s, 'linkedin', 'Acme', 'x', 'draft', NULL, 'outbound'),"
                  " (%s, %s, %s, 'email', 'Acme', 'thanks', 'received', NULL, 'inbound')",
                  (uuid.uuid4(), widgets, ann, NOW, uuid.uuid4(), widgets, ann, uuid.uuid4(), widgets, ann))

    async def live_by_user(db):
        return {ann: {"gmail", "linkedin"}}
    monkeypatch.setattr(connection_service, "live_by_user", live_by_user)
    client.sign_in(make_user("Boss", is_admin=True))
    return SimpleNamespace(ann=ann, bob=bob)


def test_engagement(client, world):
    m = client.get(f"{API}/metrics/engagement", params={"days": 30}).json()
    assert (m["total_users"], m["new_users"]) == (3, 2)
    assert (m["weekly_active_users"], m["monthly_active_users"], m["returning_users"]) == (2, 2, 1)
    assert m["stickiness"] == 0.05  # 3 active user-days / 30 / 2 monthly actives
    assert (m["sessions"], m["active_time_users"], m["total_active_seconds"]) == (3, 2, 1020)
    assert (m["avg_active_seconds_per_user"], m["avg_session_seconds"]) == (510.0, 340.0)
    assert (m["laces_total"], m["laces_created"], m["avg_laces_per_user"], m["questions"]) == (4, 3, 1.33, 3)
    assert [(t["name"], t["user_email"], t["runs"], t["activity"]) for t in m["top_laces"]] == [
        ("Widgets", "ann@example.com", 5, 0), ("Audits", "ann@example.com", 1, 3), ("Bobs", "bob@example.com", 1, 0)]
    today = m["series"][-1]
    assert len(m["series"]) == 30
    assert {k: today[k] for k in today if k != "day"} == {
        "new_users": 2, "active_users": 2, "active_seconds": 720, "laces_created": 3, "onboardings_completed": 1,
        "onboardings_failed": 1, "laces_active": 3, "questions": 3, "competitor_runs": 1, "account_runs": 1,
        "outreach_drafted": 2, "outreach_sent": 1,
    }


def test_funnel(client, world):
    m = client.get(f"{API}/metrics/funnel", params={"days": 30}).json()
    assert [(s["key"], s["users"]) for s in m["steps"]] == [
        ("signed_up", 3), ("created_lace", 3), ("onboarded", 1), ("saved_account", 1), ("approved_contact", 1),
        ("sent_outreach", 1), ("got_reply", 1),
    ]
    assert (m["laces_created"], m["onboardings_completed"], m["onboardings_failed"]) == (3, 1, 1)
    assert [(f["message"], f["runs"]) for f in m["failure_reasons"]] == [("boom", 1)]


def test_connections(client, world, monkeypatch):
    m = client.get(f"{API}/metrics/connections").json()
    gmail = next(p for p in m["platforms"] if p["platform"] == "gmail")
    assert (gmail["connected_users"], gmail["sends"], gmail["senders"]) == (1, 1, 1)
    assert (m["error"], m["users_with_connections"], m["avg_connections_per_user"]) == (None, 1, 0.67)

    async def down(db):
        raise ConnectionError("composio down")
    monkeypatch.setattr(connection_service, "live_by_user", down)
    m = client.get(f"{API}/metrics/connections").json()
    assert m["error"] and m["avg_connections_per_user"] is None
    assert next(p for p in m["platforms"] if p["platform"] == "gmail")["sends"] == 1


def test_overview_economics(client, world):
    m = client.get(f"{API}/metrics", params={"days": 30}).json()
    assert m["onboarding_p50_s"] == 180.0
    assert m["cost_per_onboarded_lace_usd"] == 2.0
    assert m["spend_per_active_user_usd"] == 1.0  # $2 over two active users
    assert [(s["email"], s["runs"], s["cost_usd"]) for s in m["top_spenders"]] == [("ann@example.com", 6, 2.0)]


def test_users_list_and_detail_show_activity_and_connections(client, world, monkeypatch):
    [ann] = client.get(f"{API}/users", params={"q": "ann"}).json()["items"]
    assert (ann["laces"], ann["runs"], ann["active_seconds_30d"], ann["connections"]) == (2, 6, 900, 2)
    assert ann["last_seen_at"] is not None

    async def ann_connections(db, user_id):
        return [connection_service.ConnectionInfo("ca_1", "gmail", "live", "ann@acme.com", NOW, NOW, str(user_id))]
    monkeypatch.setattr(connection_service, "list_with_laces", ann_connections)
    detail = client.get(f"{API}/users/{world.ann}").json()
    assert detail["connection_list"] == [
        {"platform": "gmail", "status": "live", "display_name": "ann@acme.com", "sends": 1},
    ]
    assert detail["connections"] == 1 and len(detail["activity"]) == 30
    assert detail["activity"][-1]["active_seconds"] == 600
    assert [t["name"] for t in detail["top_laces"]] == ["Widgets", "Audits"]
    assert {lace["name"] for lace in detail["lace_list"]} == {"Widgets", "Audits"}


@pytest.mark.parametrize("path", ["/metrics/engagement", "/metrics/funnel", "/metrics/connections"])
def test_admin_only_and_bounded(client, path):
    client.sign_in(make_user("Pleb"))
    assert client.get(f"{API}{path}").status_code == 403
    client.sign_in(make_user("Boss", is_admin=True))
    assert client.get(f"{API}{path}", params={"days": 365}).status_code == 422
