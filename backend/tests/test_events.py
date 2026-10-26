"""The app's event log: the app sends batches of named events (unknown
names refused, a Lace kept only when it's theirs, a daily cap, a browser
clock far off taken as now); admins see what's used most, per day, and one
user's events in order."""

import uuid
from datetime import UTC, datetime, timedelta

import psycopg

from backend.app.services import admin_events
from backend.app.services import events as events_service
from backend.tests.helpers import make_user
from backend.tests.test_lace_jobs import lace  # noqa: F401 -- fixture
from backend.tests.test_laces_api import API, lace_runtime  # noqa: F401 -- fixture
from config import settings


def _send(client, *events):
    return client.post(f"{API}/events", json={"events": list(events)})


def test_events_are_kept_with_only_the_user_s_own_lace(client, user, lace):  # noqa: F811
    minutes_ago = (datetime.now(UTC) - timedelta(minutes=5)).isoformat()
    sent = _send(client, {"name": "page_viewed", "detail": "lace_feed#opportunities", "lace_id": lace, "at": minutes_ago},
                 {"name": "lace_settings_opened", "lace_id": str(uuid.uuid4())},
                 {"name": "search_opened", "at": "2001-01-01T00:00:00+00:00"})
    assert sent.json() == {"recorded": 3}
    with psycopg.connect(settings.database_url) as conn:
        rows = conn.execute("SELECT name, detail, lace_id, created_at FROM user_events ORDER BY id").fetchall()
    assert [(n, d, lid) for n, d, lid, _ in rows] == [("page_viewed", "lace_feed#opportunities", uuid.UUID(lace)),
                                                      ("lace_settings_opened", None, None), ("search_opened", None, None)]
    assert rows[0][3] == datetime.fromisoformat(minutes_ago)
    assert rows[2][3] > datetime.now(UTC) - timedelta(minutes=1)  # a clock far off is taken as now


def test_unknown_or_oversized_events_are_refused(client):
    assert _send(client, {"name": "clicked_everything"}).status_code == 422
    assert _send(client, {"name": "page_viewed", "detail": "x" * 65}).status_code == 422
    assert _send(client, *[{"name": "search_opened"}] * 51).status_code == 422
    assert client.post(f"{API}/events", json={"events": []}).status_code == 422


def test_events_have_a_daily_cap(client, monkeypatch):
    monkeypatch.setattr(events_service, "MAX_PER_DAY", 3)
    assert _send(client, *[{"name": "search_opened"}] * 2).json() == {"recorded": 2}
    assert _send(client, *[{"name": "search_opened"}] * 2).json() == {"recorded": 1}
    assert _send(client, {"name": "search_opened"}).json() == {"recorded": 0}


def test_admins_see_what_is_used_and_each_user_s_events(client, user, lace, monkeypatch):  # noqa: F811
    _send(client, {"name": "page_viewed", "detail": "home_feed"}, {"name": "page_viewed", "detail": "home_feed"},
          {"name": "page_viewed", "detail": "lace_chat", "lace_id": lace})
    other = make_user("Other")
    client.sign_in(other)
    _send(client, {"name": "page_viewed", "detail": "home_feed"})
    client.sign_in(make_user("Boss", is_admin=True))
    summary = client.get(f"{API}/admin/events/summary", params={"days": 7}).json()
    assert [(t["detail"], t["count"], t["users"]) for t in summary["totals"]] == [("home_feed", 3, 2), ("lace_chat", 1, 1)]
    assert [(d["count"], d["users"]) for d in summary["per_day"]] == [(4, 2)]
    assert summary["people"] == 2
    mine = client.get(f"{API}/admin/events/summary", params={"user_id": str(user.id)}).json()
    assert sum(t["count"] for t in mine["totals"]) == 3
    async def accounts():
        return {user.id: "owner@example.com"}
    monkeypatch.setattr(admin_events, "emails_by_id", accounts)
    timeline = client.get(f"{API}/admin/events", params={"user_id": str(user.id)}).json()
    assert {e["user_email"] for e in timeline["items"]} == {"owner@example.com"}
    assert [(e["detail"], e["lace_name"]) for e in timeline["items"]] == [("lace_chat", "Ada"), ("home_feed", None),
                                                                          ("home_feed", None)]
    assert client.get(f"{API}/admin/events", params={"lace_id": lace}).json()["total"] == 1


def test_event_views_are_admin_only(client):
    assert client.get(f"{API}/admin/events").status_code == 403
    assert client.get(f"{API}/admin/events/summary").status_code == 403
