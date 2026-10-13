"""The public waitlist: anyone can join without signing in, details are added
with the private token, pilot opt-ins count against the spots, and abuse is
limited per IP."""

import psycopg
import pytest
from fastapi import HTTPException

from backend.app.api.deps import require_user
from backend.app.services import email
from config import settings

API = "/api/v1/waitlist"


@pytest.fixture
def anonymous(client):
    """The API with nobody signed in: any route that needs a user refuses."""
    def refuse():
        raise HTTPException(status_code=401, detail="Not signed in")
    client.app.dependency_overrides[require_user] = refuse
    return client


@pytest.fixture
def outbox(monkeypatch):
    sent = []

    async def capture(to, subject, text, html):
        sent.append((to, subject))
        return True
    monkeypatch.setattr(email, "send", capture)
    return sent


def _rows() -> list[tuple]:
    with psycopg.connect(settings.database_url) as conn:
        return conn.execute(
            "SELECT email, wants_pilot, stage, expectations, source, confirmation_sent_at IS NOT NULL "
            "FROM waitlist_signups ORDER BY created_at"
        ).fetchall()


def _join(client, address="Founder@Startup.example", ip="10.0.0.1", **extra):
    body = {"email": address, "consent": True, "source": {"utm_source": "linkedin"}, **extra}
    return client.post(API, json=body, headers={"X-Real-IP": ip})


def test_anyone_can_join_and_joining_twice_is_harmless(anonymous, outbox):
    first = _join(anonymous)
    assert first.status_code == 201 and first.json()["token"] and first.json()["pilot_spots_left"] == 50
    again = _join(anonymous)
    assert again.status_code == 201 and again.json()["token"] != first.json()["token"]
    assert _rows() == [("founder@startup.example", False, None, None, {"utm_source": "linkedin"}, True)]
    assert outbox == [("founder@startup.example", "You're on the GTMX waitlist")]  # once, not per signup


def test_details_and_pilot_opt_in_with_the_token(anonymous, outbox):
    token = _join(anonymous).json()["token"]
    saved = anonymous.patch(f"{API}/{token}", json={
        "name": "  Wanjiru Kamau ", "stage": "revenue", "sells_to": "b2b", "countries": ["Kenya", "Nigeria"],
        "wants_pilot": True, "expectations": "Find SACCOs that need a CRM",
    })
    assert saved.status_code == 200 and saved.json() == {"wants_pilot": True, "pilot_spots_left": 49}
    assert anonymous.get(f"{API}/pilot").json() == {"total": 50, "taken": 1, "left": 49}
    assert _rows()[0][1:4] == (True, "revenue", "Find SACCOs that need a CRM")
    assert outbox[-1] == ("founder@startup.example", "You're in line for the GTMX pilot")
    anonymous.patch(f"{API}/{token}", json={"wants_pilot": True})
    assert sum(subject.startswith("You're in line") for _, subject in outbox) == 1  # only on first opt-in


def test_bad_input_and_unknown_tokens_are_refused(anonymous):
    assert anonymous.post(API, json={"email": "not-an-email", "consent": True}).status_code == 422
    assert anonymous.post(API, json={"email": "a@b.example", "consent": False}).status_code == 422
    token = _join(anonymous).json()["token"]
    assert anonymous.patch(f"{API}/{token}", json={"stage": "unicorn"}).status_code == 422
    assert anonymous.patch(f"{API}/{token}", json={"expectations": "x" * 501}).status_code == 422
    assert anonymous.patch(f"{API}/not-a-real-token", json={"name": "x"}).status_code == 404


def test_a_bot_filling_the_hidden_field_is_told_yes_and_ignored(anonymous, outbox):
    response = _join(anonymous, nickname="buy cheap pills")
    assert response.status_code == 201
    assert _rows() == [] and outbox == []


def test_signups_are_limited_per_network(anonymous, outbox):
    for i in range(settings.waitlist_signups_per_ip_per_hour):
        assert _join(anonymous, f"person{i}@startup.example").status_code == 201
    limited = _join(anonymous, "one.more@startup.example")
    assert limited.status_code == 429 and limited.headers.get("retry-after")
    assert _join(anonymous, "elsewhere@startup.example", ip="10.0.0.2").status_code == 201
