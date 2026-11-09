"""Who to contact today: one ranking computed from what is on file, most
urgent first and each lead once; the Lace's tool and the daily brief use it."""

import json
import uuid
from datetime import UTC, date, datetime, timedelta

import psycopg

from backend.app.database.connect import AsyncSessionLocal
from backend.app.services import contact_today, lace_briefs
from backend.tests.test_lace_jobs import lace  # noqa: F401 -- fixture
from backend.tests.test_laces_api import lace_runtime  # noqa: F401 -- fixture
from config import settings

NOW = datetime.now(UTC)


def _lead(lace_id, name, **columns) -> uuid.UUID:
    record = json.dumps({"trigger_event": {"event": f"{name} raised a round"}})
    values = {"temperature": "cold", "fit_strength": "moderate", "contact_status": "person", **columns}
    with psycopg.connect(settings.database_url, autocommit=True) as conn:
        return conn.execute(
            f"INSERT INTO lace_accounts (id, lace_id, key, name, account_type, record, status, {', '.join(values)})"
            f" VALUES (%s, %s, %s, %s, 'company', %s, 'target', {', '.join(['%s'] * len(values))}) RETURNING id",
            (uuid.uuid4(), lace_id, name.lower(), name, record, *values.values())).fetchone()[0]


def _message(lace_id, account_id, *, direction, status, thread, step=0) -> None:
    with psycopg.connect(settings.database_url, autocommit=True) as conn:
        conn.execute("INSERT INTO lace_outreach (id, lace_id, user_id, account_id, channel, direction, status,"
                     " thread_id, sequence_step, recipient_name, recipient_company, body) VALUES (%s, %s, %s, %s,"
                     " 'email', %s, %s, %s, %s, 'Ada', (SELECT name FROM lace_accounts WHERE id = %s), '...')",
                     (uuid.uuid4(), lace_id, uuid.uuid4(), account_id, direction, status, thread, step, account_id))


async def _today(lace_id, limit=10):
    async with AsyncSessionLocal() as db:
        return await contact_today.today(db, uuid.UUID(lace_id), NOW, limit)


def test_the_most_urgent_come_first_and_each_lead_once(client, lace):  # noqa: F811
    replied = _lead(lace, "Replied Co", temperature="warm", temperature_changed_at=NOW)
    _message(lace, replied, direction="outbound", status="sent", thread="t1")
    _message(lace, replied, direction="inbound", status="received", thread="t1")
    _message(lace, replied, direction="outbound", status="draft", thread="t1")
    _lead(lace, "Hot Co", temperature="hot", temperature_reason="Asked for a meeting")
    _lead(lace, "Warm Co", temperature="warm", temperature_reason="Replied with a question",
          temperature_changed_at=NOW - timedelta(days=2))
    _lead(lace, "Stale Co", temperature="warm", temperature_changed_at=NOW - timedelta(days=20))
    _lead(lace, "Later Co", temperature="warm", temperature_changed_at=NOW, snoozed_until=NOW + timedelta(days=9))
    quiet = _lead(lace, "Quiet Co")
    _message(lace, quiet, direction="outbound", status="sent", thread="t2")
    _message(lace, quiet, direction="outbound", status="draft", thread="t2", step=1)
    _lead(lace, "Strong Co", fit_strength="strong")
    _lead(lace, "Customer Co", fit_strength="strong", crm_status="customer")
    _lead(lace, "Weak Co", fit_strength="weak")
    _lead(lace, "Stopped Co", fit_strength="strong", do_not_contact=True)

    found = client.portal.call(_today, lace)
    assert [(c.name, c.action) for c in found] == [
        ("Replied Co", "send_reply"), ("Hot Co", "hot"), ("Warm Co", "warm"), ("Quiet Co", "send_follow_up"),
        ("Strong Co", "first_email")]
    assert found[1].why == "Hot: Asked for a meeting. Confirm or book the meeting."
    assert found[4].why == "New strong lead (Strong Co raised a round): worth a first email."
    assert len(client.portal.call(_today, lace, 2)) == 2


async def _digest(lace_id):
    async with AsyncSessionLocal() as db:
        return await lace_briefs.digest(db, uuid.UUID(lace_id), NOW - timedelta(days=1), date.today())


def test_the_brief_leads_with_who_to_contact_today(client, lace):  # noqa: F811
    _lead(lace, "Hot Co", temperature="hot", temperature_reason="Asked for a meeting")
    digest = client.portal.call(_digest, lace)
    assert digest.startswith("Who to contact today:\n- Hot Co: Hot: Asked for a meeting.")
