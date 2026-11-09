"""Lead temperature: set in code from what the lead did. Replies move it by
their intent, a meeting makes it hot, the founder can mark a customer, quiet
leads cool, and each change keeps its reason and its signal."""

import uuid
from datetime import UTC, datetime, timedelta

import psycopg
import pytest

from agents.schemas.lace import ProposedAction
from backend.app.database.connect import AsyncSessionLocal
from backend.app.database.lace_models import LaceAccount, LaceOutreach
from backend.app.runs import scheduler
from backend.app.services import lace_app_actions, lace_outreach, lead_temperature
from backend.app.services.lace_app_actions import Outcome
from backend.tests.helpers import stub_accounts
from backend.tests.test_lace_app_actions import _propose
from backend.tests.test_lace_jobs import lace  # noqa: F401 -- fixture
from backend.tests.test_laces_api import API, lace_runtime  # noqa: F401 -- fixture
from config import settings


def _account(lace_id: str, name: str, email: str | None = None, **columns) -> str:
    account_id = str(uuid.uuid4())
    names = ", ".join(columns)
    values = "".join(", %s" for _ in columns)
    with psycopg.connect(settings.database_url, autocommit=True) as conn:
        conn.execute(f"INSERT INTO lace_accounts (id, lace_id, key, name, account_type, record, status"
                     f"{', ' + names if names else ''}) VALUES (%s, %s, %s, %s, 'company', '{{}}', 'target'{values})",
                     (account_id, lace_id, name.lower(), name, *columns.values()))
        if email:
            conn.execute("INSERT INTO lace_contacts (id, lace_id, account_id, key, name, email, source) VALUES"
                         " (%s, %s, %s, %s, 'Ada', %s, 'discovery')", (uuid.uuid4(), lace_id, account_id, email, email))
    return account_id


def _state(account_id: str) -> tuple:
    with psycopg.connect(settings.database_url) as conn:
        return conn.execute("SELECT temperature, temperature_reason, snoozed_until IS NOT NULL, do_not_contact"
                            " FROM lace_accounts WHERE id = %s", (account_id,)).fetchone()


def _signals(account_id: str) -> list[tuple]:
    with psycopg.connect(settings.database_url) as conn:
        return conn.execute("SELECT kind, before, after FROM lace_account_signals WHERE account_id = %s"
                            " ORDER BY at, after", (account_id,)).fetchall()


async def _read_reply(lace_id: str, account_id: str, intent: str, user_id) -> None:
    """A reply from the lead arrives and is read as `intent`."""
    async with AsyncSessionLocal() as db:
        reply = LaceOutreach(lace_id=uuid.UUID(lace_id), user_id=user_id, account_id=uuid.UUID(account_id),
                             channel="email", direction="inbound", status="received", body="...")
        db.add(reply)
        await db.flush()
        await lace_outreach.record_reading(db, reply, intent, None, uuid.uuid4())
        await db.commit()


def test_replies_warm_a_lead_and_a_meeting_request_makes_it_hot(client, lace, user):  # noqa: F811
    lead = _account(lace, "Acme")
    assert _state(lead)[0] == "cold"
    client.portal.call(_read_reply, lace, lead, "question", user.id)
    assert _state(lead)[:2] == ("warm", "Replied with a question")
    client.portal.call(_read_reply, lace, lead, "meeting_request", user.id)
    assert _state(lead)[:2] == ("hot", "Asked for a meeting")
    # A warmer-than-cold reply later doesn't cool it: it stays hot, as activity.
    client.portal.call(_read_reply, lace, lead, "interested", user.id)
    assert _state(lead)[:2] == ("hot", "Asked for a meeting")
    assert _signals(lead) == [("reply", "cold", "warm"), ("reply", "warm", "hot"), ("reply", "hot", "hot")]


@pytest.mark.parametrize(("intent", "expected"), [
    ("not_now", ("warm", "Said not now", True, False)),
    ("unsubscribe", ("cold", "Asked not to be contacted", False, True)),
    ("out_of_office", ("cold", None, False, False)),
])
def test_not_now_snoozes_an_opt_out_stops_contact_and_out_of_office_changes_nothing(
        client, lace, user, intent, expected):  # noqa: F811
    lead = _account(lace, "Acme")
    client.portal.call(_read_reply, lace, lead, intent, user.id)
    assert _state(lead) == expected


def test_founders_mark_a_customer_and_can_take_it_back(client, lace):  # noqa: F811
    lead = _account(lace, "Acme")
    marked = client.put(f"{API}/laces/{lace}/accounts/{lead}/customer", json={"customer": True})
    assert marked.status_code == 200
    assert (marked.json()["temperature"], marked.json()["temperature_reason"]) == ("customer", "Marked as a customer")
    back = client.put(f"{API}/laces/{lace}/accounts/{lead}/customer", json={"customer": False}).json()
    assert back["temperature"] == "cold"
    assert client.put(f"{API}/laces/{lace}/accounts/{uuid.uuid4()}/customer",
                      json={"customer": True}).status_code == 404


def test_leads_are_listed_hottest_first_and_filter_by_temperature(client, lace):  # noqa: F811
    _account(lace, "Cold Co")
    _account(lace, "Hot Co", temperature="hot", temperature_reason="Asked for a meeting")
    _account(lace, "Warm Co", temperature="warm")
    _account(lace, "Bought Co", temperature="customer")
    listed = client.get(f"{API}/laces/{lace}/accounts").json()
    assert [a["name"] for a in listed] == ["Hot Co", "Warm Co", "Cold Co", "Bought Co"]
    assert listed[0]["temperature_reason"] == "Asked for a meeting"
    assert [a["name"] for a in client.get(f"{API}/laces/{lace}/accounts", params={"temperature": "warm"}).json()] == [
        "Warm Co"]
    assert client.get(f"{API}/laces/{lace}/accounts", params={"temperature": "lukewarm"}).status_code == 422


def test_quiet_leads_cool_a_step_but_not_snoozed_ones_or_customers(client, lace):  # noqa: F811
    long_ago = datetime.now(UTC) - timedelta(days=settings.lead_cooling_days + 1)
    hot = _account(lace, "Hot Co", temperature="hot", temperature_changed_at=long_ago)
    warm = _account(lace, "Warm Co", temperature="warm", temperature_changed_at=long_ago)
    snoozed = _account(lace, "Later Co", temperature="warm", temperature_changed_at=long_ago,
                       snoozed_until=datetime.now(UTC) + timedelta(days=5))
    recent = _account(lace, "Recent Co", temperature="warm", temperature_changed_at=datetime.now(UTC))
    customer = _account(lace, "Bought Co", temperature="customer", temperature_changed_at=long_ago)
    assert client.portal.call(scheduler.cool_leads) == 2
    assert [_state(a)[0] for a in (hot, warm, snoozed, recent, customer)] == ["warm", "cold", "warm", "warm",
                                                                                 "customer"]
    assert _signals(warm) == [("cooled", "warm", "cold")]
    assert client.portal.call(scheduler.cool_leads) == 0  # just cooled: the clock started again


def test_an_approved_meeting_with_someone_at_a_lead_makes_it_hot(client, lace, lace_runtime, monkeypatch):  # noqa: F811
    lead = _account(lace, "Acme", email="ada@acme.test")
    other = _account(lace, "Elsewhere", email="bo@elsewhere.test")
    stub_accounts(monkeypatch, {"googlecalendar"})

    async def create(ctx, arguments):
        return Outcome("Added to the calendar.", url=None, log_id="log_1")
    monkeypatch.setitem(lace_app_actions.RUNNERS, ("googlecalendar", "create_event"), create)
    card = _propose(client, lace, ProposedAction(
        app="googlecalendar", action="create_event", title="Intro call with Acme", preview="Thu 10:00",
        arguments={"title": "Intro call with Acme", "start": "2026-11-12T10:00:00", "minutes": 30,
                   "attendees": ["Ada@Acme.test"]}))
    assert client.post(f"{API}/laces/{lace}/app-actions/{card['id']}/approve").json()["status"] == "done"
    assert _state(lead)[:2] == ("hot", "Meeting booked: Intro call with Acme")
    assert _state(other)[0] == "cold"


async def test_a_meeting_with_no_lead_among_its_guests_changes_nothing(lace):  # noqa: F811
    async with AsyncSessionLocal() as db:
        assert await lead_temperature.on_meeting(db, uuid.UUID(lace), ["someone@nowhere.test", ""], "Coffee") == []
        assert (await db.get(LaceAccount, uuid.uuid4())) is None
