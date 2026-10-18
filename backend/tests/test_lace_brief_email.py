"""The brief by email: only when the founder asked, never in their quiet
hours (sent once they end), once per brief, rendered from its markdown."""

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import psycopg
import pytest
from langchain_core.messages import AIMessage

from backend.app import supabase_admin
from backend.app.runs import scheduler
from backend.app.services import email, lace_brief_email
from backend.tests.helpers import FakeSupabase, make_user, supabase_user
from backend.tests.test_lace_briefs import _due_now, _seed
from backend.tests.test_lace_jobs import _runs, lace  # noqa: F401 -- fixture
from backend.tests.test_laces_api import API, lace_runtime  # noqa: F401 -- fixture
from backend.tests.test_runs import _wait_for_status
from config import settings


@pytest.mark.parametrize("quiet, hour, inside", [
    ((None, None), 3, False),
    ((22, 7), 23, True), ((22, 7), 3, True), ((22, 7), 7, False), ((22, 7), 12, False),
    ((13, 15), 13, True), ((13, 15), 15, False),
])
def test_quiet_hours_wrap_midnight(quiet, hour, inside):
    lace_row = SimpleNamespace(quiet_start=quiet[0], quiet_end=quiet[1], timezone="Africa/Nairobi")
    now = datetime(2026, 10, 19, hour, 30, tzinfo=UTC) - timedelta(hours=3)  # Nairobi is UTC+3
    assert lace_brief_email.in_quiet_hours(lace_row, now) is inside


def test_markdown_to_email_html():
    html = lace_brief_email.to_html("**Waiting on you**\n- Send the [draft](https://a.test/x?a=1&b=2)\n"
                                    "- <script>x</script>\n\n1. Decide today\n## Next")
    assert "<strong>Waiting on you</strong>" in html
    assert '<ul' in html and "<li>Send the <a href=\"https://a.test/x?a=1&amp;b=2\"" in html
    assert "&lt;script&gt;" in html and "<script>" not in html
    assert "<ol" in html and "<li>Decide today</li></ol>" in html and "<strong>Next</strong>" in html


@pytest.fixture
def outbox(monkeypatch, user):
    sent: list[dict] = []

    async def send(to, subject, text, html):
        sent.append({"to": to, "subject": subject, "text": text, "html": html})
        return True

    fake = FakeSupabase([supabase_user(user.id, "founder@acme.test")])

    async def client():
        return fake

    monkeypatch.setattr(email, "configured", lambda: True)
    monkeypatch.setattr(email, "send", send)
    monkeypatch.setattr(supabase_admin, "get_client", client)
    return sent


def _settings(lace_id, **values):
    assignments = ", ".join(f"{column} = %s" for column in values)
    with psycopg.connect(settings.database_url, autocommit=True) as conn:
        conn.execute(f"UPDATE laces SET {assignments} WHERE id = %s", (*values.values(), lace_id))


def _post_brief(client, lace_id, lace_runtime):  # noqa: F811
    lace_runtime.append(AIMessage(content="**Waiting on you**\n- The SunCulture draft."))
    assert client.portal.call(scheduler.sweep_briefs) == 1
    [turn] = [r for r in client.portal.call(_runs, lace_id, "lace_turn") if (r.input or {}).get("brief_id")]
    client.portal.call(_wait_for_status, turn.id, {"completed"})


def _emailed(lace_id) -> list:
    with psycopg.connect(settings.database_url) as conn:
        return [r[0] for r in conn.execute("SELECT b.emailed_at FROM lace_briefs b WHERE b.lace_id = %s", (lace_id,))]


def test_the_brief_is_emailed_when_asked(client, lace, lace_runtime, user, outbox):  # noqa: F811
    _seed(lace, user.id)
    _due_now(lace)
    _settings(lace, brief_email=True)
    _post_brief(client, lace, lace_runtime)
    [mail] = outbox
    assert mail["to"] == "founder@acme.test" and "'s brief, " in mail["subject"]
    assert "<strong>Waiting on you</strong>" in mail["html"] and f"/lace/{lace}" in mail["text"]
    assert all(_emailed(lace))
    assert client.portal.call(lace_brief_email.email_waiting, datetime.now(UTC)) == 0  # once


def test_no_email_unless_asked(client, lace, lace_runtime, user, outbox):  # noqa: F811
    _seed(lace, user.id)
    _due_now(lace)
    _post_brief(client, lace, lace_runtime)
    assert outbox == [] and _emailed(lace) == [None]
    assert client.portal.call(lace_brief_email.email_waiting, datetime.now(UTC)) == 0


def test_quiet_hours_hold_the_email_until_they_end(client, lace, lace_runtime, user, outbox):  # noqa: F811
    _seed(lace, user.id)
    _due_now(lace)
    hour = datetime.now(UTC).hour
    _settings(lace, brief_email=True, quiet_start=hour, quiet_end=(hour + 2) % 24)
    _post_brief(client, lace, lace_runtime)
    assert outbox == []
    assert client.portal.call(lace_brief_email.email_waiting, datetime.now(UTC) + timedelta(minutes=5)) == 0
    assert client.portal.call(lace_brief_email.email_waiting, datetime.now(UTC) + timedelta(hours=3)) == 1
    assert len(outbox) == 1
    # A day later a missed email is let go, not sent stale.
    with psycopg.connect(settings.database_url, autocommit=True) as conn:
        conn.execute("UPDATE lace_briefs SET emailed_at = NULL")
    assert client.portal.call(lace_brief_email.email_waiting, datetime.now(UTC) + timedelta(hours=25)) == 0


def test_brief_email_settings(client, lace, lace_runtime, monkeypatch):  # noqa: F811
    monkeypatch.setattr(email, "configured", lambda: True)
    url = f"{API}/laces/{lace}/brief"
    initial = client.get(url).json()
    assert (initial["brief_email"], initial["quiet_hours"], initial["email_available"]) == (False, None, True)
    updated = client.patch(url, json={"brief_email": True, "quiet_hours": {"start": 22, "end": 7}}).json()
    assert updated["brief_email"] and updated["quiet_hours"] == {"start": 22, "end": 7}
    assert client.patch(url, json={"brief_hour": 9}).json()["quiet_hours"] == {"start": 22, "end": 7}  # kept
    assert client.patch(url, json={"quiet_hours": None}).json()["quiet_hours"] is None
    assert client.patch(url, json={"quiet_hours": {"start": 5, "end": 5}}).status_code == 422
    assert client.patch(url, json={"brief_email": None}).json()["brief_email"] is True
    client.sign_in(make_user("Intruder"))
    assert client.patch(url, json={"brief_email": False}).status_code == 404
