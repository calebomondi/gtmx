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
    """Three users: `ann` (busy), `bob` (abandoned an interview), `cat` (signed up long ago, idle)."""
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

    w1, w2, w3, discovery, abandoned = (uuid.uuid4() for _ in range(5))
    with psycopg.connect(settings.database_url, autocommit=True) as c:
        c.execute("INSERT INTO workspaces (id, user_id, name, offer_type) VALUES"
                  " (%s, %s, 'Widgets', 'product'), (%s, %s, 'Audits', 'service')", (w1, ann, w2, ann))
        c.execute("INSERT INTO workspaces (id, user_id, name, date_created) VALUES (%s, %s, 'Old', %s)",
                  (w3, cat, NOW - timedelta(days=40)))
        c.execute("INSERT INTO projects (id, user_id, name, name_key) VALUES (%s, %s, 'Acme', 'acme')",
                  (uuid.uuid4(), ann))
        for uid, started, seconds in [(ann, NOW, 600), (ann, NOW - timedelta(days=2), 300), (bob, NOW, 120)]:
            c.execute("INSERT INTO app_sessions (user_id, started_at, last_seen_at, active_seconds)"
                      " VALUES (%s, %s, %s, %s)", (uid, started, started, seconds))
        c.execute("INSERT INTO workspace_activity (user_id, workspace_id, day, active_seconds, visits, last_seen_at)"
                  " VALUES (%s, %s, %s, 500, 2, %s), (%s, %s, %s, 100, 1, %s)",
                  (ann, w1, NOW.date(), NOW, ann, w2, NOW.date(), NOW))
        c.execute("INSERT INTO runs (id, user_id, workspace_id, kind, status, started_at, finished_at)"
                  " VALUES (%s, %s, %s, 'discovery', 'completed', %s, %s)",
                  (discovery, ann, w1, NOW - timedelta(minutes=3), NOW))
        c.execute("INSERT INTO runs (id, user_id, kind, status) VALUES (%s, %s, 'discovery', 'cancelled')",
                  (abandoned, bob))
        c.execute("INSERT INTO runs (id, user_id, kind, status, error) VALUES (%s, %s, 'discovery', 'failed', 'boom')",
                  (uuid.uuid4(), bob))
        c.execute("INSERT INTO runs (id, user_id, workspace_id, kind, status) VALUES (%s, %s, %s, 'accounts', 'completed')",
                  (uuid.uuid4(), ann, w1))
        # A deleted account's history: never counted as a person.
        c.execute("INSERT INTO runs (id, user_id, kind, status, created_at) VALUES (%s, %s, 'discovery', 'completed', %s)",
                  (uuid.uuid4(), uuid.uuid4(), NOW - timedelta(days=60)))
        for run, question in [(abandoned, "product_service_description_confirmation"), (abandoned, "target_market")]:
            c.execute("INSERT INTO run_events (run_id, type, payload) VALUES (%s, 'interrupt', %s)",
                      (run, json.dumps({"interrupt_type": question})))
        c.execute("INSERT INTO llm_calls (run_id, log_label, provider, model, input_tokens, output_tokens, seconds, ok)"
                  " VALUES (%s, 'x', 'qwen', 'qwen3.7-plus', 1000000, 1000000, 1, true)", (discovery,))
        c.execute("INSERT INTO chat_messages (id, workspace_id, user_id, role, content) VALUES (%s, %s, %s, 'user', 'hi')",
                  (uuid.uuid4(), w1, ann))
        c.execute("INSERT INTO outreach_messages (id, workspace_id, user_id, channel, recipient_company, body, status, sent_at)"
                  " VALUES (%s, %s, %s, 'email', 'Acme', 'x', 'sent', %s), (%s, %s, %s, 'linkedin', 'Acme', 'x', 'draft', NULL)",
                  (uuid.uuid4(), w1, ann, NOW, uuid.uuid4(), w1, ann))

    async def live_by_user():
        return {ann: {"gmail", "linkedin"}}
    monkeypatch.setattr(connection_service, "live_by_user", live_by_user)
    client.sign_in(make_user("Boss", is_admin=True))
    return SimpleNamespace(ann=ann, bob=bob, w1=w1)


def test_engagement(client, world):
    m = client.get(f"{API}/metrics/engagement", params={"days": 30}).json()
    assert (m["total_users"], m["new_users"]) == (3, 2)
    assert (m["weekly_active_users"], m["monthly_active_users"], m["returning_users"]) == (2, 2, 1)
    assert m["stickiness"] == 0.05  # 3 active user-days / 30 / 2 monthly actives
    assert (m["sessions"], m["active_time_users"], m["total_active_seconds"]) == (3, 2, 1020)
    assert (m["avg_active_seconds_per_user"], m["avg_session_seconds"]) == (510.0, 340.0)
    assert (m["workspaces_total"], m["workspaces_created"], m["projects_total"], m["projects_created"]) == (3, 2, 1, 1)
    assert m["offer_types"] == {"product": 1, "service": 1, "unknown": 1}
    assert (m["avg_workspaces_per_user"], m["avg_projects_per_user"]) == (1.0, 0.33)
    top = m["top_workspaces"][0]
    assert (top["name"], top["user_email"], top["active_seconds"], top["visits"]) == ("Widgets", "ann@example.com", 500, 2)
    today = m["series"][-1]
    assert len(m["series"]) == 30
    assert {k: today[k] for k in today if k != "day"} == {
        "new_users": 2, "active_users": 2, "active_seconds": 720, "workspaces_created": 2, "products_created": 1,
        "services_created": 1, "projects_created": 1, "workspaces_interacted": 2, "chat_messages": 1,
        "competitor_runs": 0, "account_runs": 1, "outreach_drafted": 2, "outreach_sent": 1,
    }


def test_funnel(client, world):
    m = client.get(f"{API}/metrics/funnel", params={"days": 30}).json()
    assert [(s["key"], s["users"]) for s in m["steps"]] == [
        ("signed_up", 3), ("started_discovery", 2), ("completed_discovery", 1),
        ("ran_research", 1), ("drafted_outreach", 1), ("sent_outreach", 1),
    ]
    assert (m["discoveries_started"], m["discoveries_completed"]) == (3, 1)
    # The question the cancelled run stopped at is its last one.
    assert m["interview_dropoffs"] == [{"question": "target_market", "runs": 1}]
    assert [(f["message"], f["runs"]) for f in m["failure_reasons"]] == [("boom", 1)]


def test_connections(client, world, monkeypatch):
    m = client.get(f"{API}/metrics/connections").json()
    gmail = next(p for p in m["platforms"] if p["platform"] == "gmail")
    assert (gmail["connected_users"], gmail["sends"], gmail["senders"]) == (1, 1, 1)
    assert (m["error"], m["users_with_connections"], m["avg_connections_per_user"]) == (None, 1, 0.67)

    async def down():
        raise ConnectionError("composio down")
    monkeypatch.setattr(connection_service, "live_by_user", down)
    m = client.get(f"{API}/metrics/connections").json()
    assert m["error"] and m["avg_connections_per_user"] is None
    assert next(p for p in m["platforms"] if p["platform"] == "gmail")["sends"] == 1


def test_overview_economics(client, world):
    m = client.get(f"{API}/metrics", params={"days": 30}).json()
    assert m["discovery_p50_s"] == 180.0
    assert m["cost_per_completed_discovery_usd"] == 2.0
    assert m["spend_per_active_user_usd"] == 1.0  # $2 over two active users
    assert [(s["email"], s["runs"], s["cost_usd"]) for s in m["top_spenders"]] == [("ann@example.com", 2, 2.0)]


def test_users_list_and_detail_show_activity_and_connections(client, world, monkeypatch):
    [ann] = client.get(f"{API}/users", params={"q": "ann"}).json()["items"]
    assert (ann["projects"], ann["workspaces"], ann["active_seconds_30d"], ann["connections"]) == (1, 2, 900, 2)
    assert ann["last_seen_at"] is not None

    async def ann_connections(user_id):
        return [connection_service.ConnectionInfo("ca_1", "gmail", "live", "ann@acme.com", NOW, NOW)]
    monkeypatch.setattr(connection_service, "list_for_user", ann_connections)
    detail = client.get(f"{API}/users/{world.ann}").json()
    assert detail["connection_list"] == [
        {"platform": "gmail", "status": "live", "display_name": "ann@acme.com", "sends": 1},
    ]
    assert detail["connections"] == 1 and len(detail["activity"]) == 30
    assert detail["activity"][-1]["active_seconds"] == 600
    assert [w["name"] for w in detail["top_workspaces"]] == ["Widgets", "Audits"]
    assert {w["name"]: w["offer_type"] for w in detail["workspace_list"]} == {"Widgets": "product", "Audits": "service"}


@pytest.mark.parametrize("path", ["/metrics/engagement", "/metrics/funnel", "/metrics/connections"])
def test_admin_only_and_bounded(client, path):
    client.sign_in(make_user("Pleb"))
    assert client.get(f"{API}{path}").status_code == 403
    client.sign_in(make_user("Boss", is_admin=True))
    assert client.get(f"{API}{path}", params={"days": 365}).status_code == 422
