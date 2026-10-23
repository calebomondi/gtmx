"""The waitlist's emails introduce Lace, worldwide, and say when the pilot
starts, or that it has been running, as of the day they are sent."""

from datetime import date

from backend.app.services import waitlist_emails
from config import settings


def test_the_joined_email_introduces_lace_and_the_pilot_date(monkeypatch):
    monkeypatch.setattr(settings, "waitlist_pilot_starts_on", date(2026, 10, 24))
    subject, text, html = waitlist_emails.joined(today=date(2026, 10, 23))
    assert subject == "You're on the Thalace waitlist"
    assert "its own assistant, Lace" in text and "places to sell, showcase and partner" in text
    assert "Our pilot for 50 founders starts October 24." in text and "October 24" in html
    for v1 in ("go-to-market", "Kenya", "Nigeria", "South Africa"):
        assert v1 not in text


def test_the_pilot_email_says_the_pilot_is_running_once_it_started(monkeypatch):
    monkeypatch.setattr(settings, "waitlist_pilot_starts_on", date(2026, 10, 24))
    _, before, _ = waitlist_emails.pilot(today=date(2026, 10, 20))
    _, after, _ = waitlist_emails.pilot(today=date(2026, 10, 30))
    assert "starts October 24" in before and "set up your Lace" in before
    assert "has been running since October 24" in after
