"""The waitlist in the admin dashboard: admins only, paginated, searchable,
exportable, with numbers, and every status change audited."""

import csv
import io

import psycopg
import pytest

from backend.app.services import email
from backend.tests.helpers import make_user
from config import settings

API = "/api/v1"


@pytest.fixture
def signups(client, monkeypatch):
    """Three signups through the public API; Ada also asks for the pilot."""
    async def no_email(*_):
        return True
    monkeypatch.setattr(email, "send", no_email)
    tokens = {}
    for i, address in enumerate(["ada@lovelace.example", "bo@shop.example", "cy@agency.example"]):
        joined = client.post(f"{API}/waitlist", json={"email": address, "consent": True,
                                                      "source": {"utm_source": "x"}}, headers={"X-Real-IP": f"10.1.0.{i}"})
        tokens[address] = joined.json()["token"]
    client.patch(f"{API}/waitlist/{tokens['ada@lovelace.example']}", json={
        "name": "Ada Lovelace", "company": "Analytical Engines", "stage": "revenue", "sells_to": "b2b",
        "countries": ["Kenya"], "wants_pilot": True, "expectations": "Find banks to sell to",
    })
    return tokens


@pytest.fixture
def admin(client):
    client.sign_in(make_user("Boss", is_admin=True))
    return client


def test_only_admins_see_the_waitlist(client, signups):
    assert client.get(f"{API}/admin/waitlist").status_code == 403
    assert client.get(f"{API}/admin/waitlist/export.csv").status_code == 403


def test_list_search_and_filter(admin, signups):
    page = admin.get(f"{API}/admin/waitlist", params={"per_page": 2}).json()
    assert page["total"] == 3 and len(page["items"]) == 2 and page["items"][0]["email"] == "cy@agency.example"
    assert [r["email"] for r in admin.get(f"{API}/admin/waitlist", params={"q": "analytical"}).json()["items"]] == [
        "ada@lovelace.example"]
    pilots = admin.get(f"{API}/admin/waitlist", params={"pilot": True}).json()["items"]
    assert [(r["email"], r["expectations"], r["countries"]) for r in pilots] == [
        ("ada@lovelace.example", "Find banks to sell to", ["Kenya"])]


def test_stats(admin, signups):
    stats = admin.get(f"{API}/admin/waitlist/stats").json()
    assert (stats["total"], stats["last_7_days"]) == (3, 3)
    assert stats["pilot"] == {"total": 50, "taken": 1, "left": 49,
                              "starts_on": settings.waitlist_pilot_starts_on.isoformat()}
    assert len(stats["by_day"]) == 30 and stats["by_day"][-1]["signups"] == 3
    assert stats["by_stage"] == {"revenue": 1, "unknown": 2} and stats["by_sells_to"] == {"b2b": 1, "unknown": 2}


def test_status_changes_are_audited(admin, signups):
    ada = admin.get(f"{API}/admin/waitlist", params={"q": "ada"}).json()["items"][0]
    updated = admin.patch(f"{API}/admin/waitlist/{ada['id']}", json={"status": "invited"})
    assert updated.status_code == 200 and updated.json()["status"] == "invited"
    assert admin.patch(f"{API}/admin/waitlist/{ada['id']}", json={"status": "vip"}).status_code == 422
    with psycopg.connect(settings.database_url) as conn:
        action, before, after = conn.execute(
            "SELECT action, before, after FROM admin_audit_log ORDER BY created_at DESC LIMIT 1").fetchone()
    assert (action, before["status"], after["status"]) == ("waitlist.status", "new", "invited")


def test_csv_export(admin, signups):
    response = admin.get(f"{API}/admin/waitlist/export.csv", params={"pilot": True})
    assert response.headers["content-type"].startswith("text/csv")
    assert "attachment" in response.headers["content-disposition"]
    rows = list(csv.DictReader(io.StringIO(response.text)))
    assert [(r["email"], r["wants_pilot"], r["utm_source"]) for r in rows] == [("ada@lovelace.example", "yes", "x")]
