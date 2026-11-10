"""Follow-ups to first emails nobody answered: due a few days after sending,
drafted in the same thread for the founder to send, two at most, and stopped
by a reply, a bounce, a hot lead, a draft already waiting, or "not now"."""

import uuid
from datetime import UTC, datetime, timedelta

import psycopg
from langchain_core.messages import AIMessage

from agents.schemas.outreach import OutreachDraft
from backend.app.database.connect import AsyncSessionLocal
from backend.app.database.lace_models import LaceOutreach
from backend.app.runs import follow_up_jobs, manager, scheduler
from backend.app.services import follow_ups
from backend.tests.test_lace_jobs import _runs, lace  # noqa: F401 -- fixture
from backend.tests.test_laces_api import lace_runtime  # noqa: F401 -- fixture
from backend.tests.test_runs import _wait_for_status
from config import settings

LONG_AGO = datetime.now(UTC) - timedelta(days=10)


def _sent(lace_id, user_id, *, thread="t1", step=0, due=LONG_AGO, account=None, status="sent") -> uuid.UUID:
    """An email the founder sent, in its own thread, its follow-up due."""
    with psycopg.connect(settings.database_url, autocommit=True) as conn:
        if account is None:
            account = conn.execute(
                "INSERT INTO lace_accounts (id, lace_id, key, name, account_type, record, status) VALUES"
                " (%s, %s, %s, 'Acme Clinics', 'company', '{}', 'target') RETURNING id",
                (uuid.uuid4(), lace_id, f"acme-{thread}.test")).fetchone()[0]
        return conn.execute(
            "INSERT INTO lace_outreach (id, lace_id, user_id, account_id, channel, direction, recipient_name,"
            " recipient_company, recipient_address, subject, body, status, thread_id, mailbox, sent_at,"
            " sequence_step, follow_up_due_at) VALUES (%s, %s, %s, %s, 'email', 'outbound', 'Ada Lovelace',"
            " 'Acme Clinics', 'ada@acme.test', 'Payroll for 12 sites', 'Hi Ada, ... Wanjiku', %s, %s, 'gmail',"
            " %s, %s, %s) RETURNING id",
            (uuid.uuid4(), lace_id, user_id, account, status, thread, LONG_AGO - timedelta(days=3), step, due),
        ).fetchone()[0]


def _row(message_id) -> tuple:
    with psycopg.connect(settings.database_url) as conn:
        return conn.execute("SELECT follow_up_due_at FROM lace_outreach WHERE id = %s", (message_id,)).fetchone()


def _drafts(lace_id) -> list[tuple]:
    with psycopg.connect(settings.database_url) as conn:
        return conn.execute("SELECT thread_id, sequence_step, recipient_address, mailbox, body FROM lace_outreach"
                            " WHERE lace_id = %s AND status = 'draft' ORDER BY created_at", (lace_id,)).fetchall()


def _writer(monkeypatch) -> list:
    briefs = []

    def write(brief):
        briefs.append(brief)
        return OutreachDraft(body=f"Hi Ada,\n\nA new idea, step {brief.step}.\n\nWanjiku")

    async def sender(user_id):
        return "Wanjiku"
    monkeypatch.setattr(follow_up_jobs, "write_follow_up", write)
    monkeypatch.setattr(follow_up_jobs.outreach_service, "sender_for_user", sender)
    return briefs


def _run_job(client, lace_id, user_id):
    run = client.portal.call(manager.start_lace_job, "lace_follow_ups", user_id, uuid.UUID(lace_id), {"scheduled": True})
    return client.portal.call(_wait_for_status, run.id, {"completed"})


def test_a_due_follow_up_is_drafted_in_the_thread_once(client, lace, lace_runtime, user, monkeypatch):  # noqa: F811
    briefs = _writer(monkeypatch)
    lace_runtime.extend(AIMessage(content="A follow-up is ready.") for _ in range(2))
    sent = _sent(lace, user.id)
    run = _run_job(client, lace, user.id)
    assert run.progress == {"due": 1, "drafted": 1, "failed": 0}
    assert _drafts(lace) == [("t1", 1, "ada@acme.test", "gmail", "Hi Ada,\n\nA new idea, step 1.\n\nWanjiku")]
    assert briefs[0].earlier == ["Hi Ada, ... Wanjiku"] and briefs[0].step == 1 and briefs[0].company == "Acme Clinics"
    assert _row(sent) == (None,)
    # The founder discards it: it isn't drafted again.
    with psycopg.connect(settings.database_url, autocommit=True) as conn:
        conn.execute("DELETE FROM lace_outreach WHERE status = 'draft'")
    assert _run_job(client, lace, user.id).progress == {"due": 0, "drafted": 0, "failed": 0}


def _with(lace_id, sent_id, sql: str, *args) -> None:
    with psycopg.connect(settings.database_url, autocommit=True) as conn:
        conn.execute(sql, args)


def test_the_sequence_stops_or_waits(client, lace, lace_runtime, user, monkeypatch):  # noqa: F811
    _writer(monkeypatch)
    replied = _sent(lace, user.id, thread="t_replied")
    _with(lace, replied, "INSERT INTO lace_outreach (id, lace_id, user_id, channel, direction, body, status, thread_id)"
          " VALUES (%s, %s, %s, 'email', 'inbound', 'Thanks!', 'received', 't_replied')", uuid.uuid4(), lace, user.id)
    bounced = _sent(lace, user.id, thread="t_bounced", status="bounced")
    hot = _sent(lace, user.id, thread="t_hot")
    _with(lace, hot, "UPDATE lace_accounts SET temperature = 'hot' WHERE key = 'acme-t_hot.test'")
    waiting = _sent(lace, user.id, thread="t_waiting")
    _with(lace, waiting, "INSERT INTO lace_outreach (id, lace_id, user_id, channel, body, status, thread_id)"
          " VALUES (%s, %s, %s, 'email', 'A draft', 'draft', 't_waiting')", uuid.uuid4(), lace, user.id)
    later = datetime.now(UTC) + timedelta(days=5)
    snoozed = _sent(lace, user.id, thread="t_snoozed")
    _with(lace, snoozed, "UPDATE lace_accounts SET snoozed_until = %s WHERE key = 'acme-t_snoozed.test'", later)

    assert _run_job(client, lace, user.id).progress["drafted"] == 0
    assert [_row(m)[0] for m in (replied, bounced, hot, waiting)] == [None] * 4
    assert abs((_row(snoozed)[0] - later).total_seconds()) < 1  # asked again after "not now"
    assert [d[0] for d in _drafts(lace)] == ["t_waiting"]  # only the founder's own draft


async def _schedule(message_id):
    async with AsyncSessionLocal() as db, db.begin():
        message = await db.get(LaceOutreach, message_id)
        await follow_ups.schedule(db, message)


def test_sending_sets_when_the_next_follow_up_is_due(client, lace, user):  # noqa: F811
    first = _sent(lace, user.id, thread="t_a", due=None)
    client.portal.call(_schedule, first)
    with psycopg.connect(settings.database_url) as conn:
        sent_at = conn.execute("SELECT sent_at FROM lace_outreach WHERE id = %s", (first,)).fetchone()[0]
    assert _row(first)[0] == sent_at + timedelta(days=settings.follow_up_first_after_days)
    second = _sent(lace, user.id, thread="t_b", step=1, due=None)
    client.portal.call(_schedule, second)
    assert _row(second)[0] == sent_at + timedelta(days=settings.follow_up_second_after_days)
    last = _sent(lace, user.id, thread="t_c", step=2, due=None)
    client.portal.call(_schedule, last)
    assert _row(last) == (None,)  # two follow-ups at most
    answered = _sent(lace, user.id, thread="t_d", due=None)
    _with(lace, answered, "INSERT INTO lace_outreach (id, lace_id, user_id, channel, direction, body, status, thread_id)"
          " VALUES (%s, %s, %s, 'email', 'inbound', 'Hi', 'received', 't_d')", uuid.uuid4(), lace, user.id)
    client.portal.call(_schedule, answered)
    assert _row(answered) == (None,)  # an answer to them is not a first email


def test_the_sweep_starts_drafting_for_laces_with_follow_ups_due(client, lace, lace_runtime, user,  # noqa: F811
                                                                 monkeypatch):
    _writer(monkeypatch)
    lace_runtime.append(AIMessage(content="A follow-up is ready."))
    _with(lace, None, "UPDATE laces SET status = 'active' WHERE id = %s", lace)
    _sent(lace, user.id)
    assert client.portal.call(scheduler.sweep_follow_ups) == 1
    [run] = client.portal.call(_runs, lace, "lace_follow_ups")
    client.portal.call(_wait_for_status, run.id, {"completed"})
    assert client.portal.call(scheduler.sweep_follow_ups) == 0  # nothing due any more


def test_a_follow_up_goes_by_the_founders_notes_on_the_lead(client, lace, lace_runtime, user, monkeypatch):  # noqa: F811
    briefs = _writer(monkeypatch)
    lace_runtime.extend(AIMessage(content="A follow-up is ready.") for _ in range(2))
    with psycopg.connect(settings.database_url, autocommit=True) as conn:
        account = conn.execute(
            "INSERT INTO lace_accounts (id, lace_id, key, name, account_type, record, status, founder_notes) VALUES"
            " (%s, %s, 'acme.test', 'Acme Clinics', 'company', '{}', 'target', 'Met at iHub; wants pricing')"
            " RETURNING id", (uuid.uuid4(), lace)).fetchone()[0]
    _sent(lace, user.id, account=account)
    _run_job(client, lace, user.id)
    assert "About Acme Clinics, from the founder's leads sheet: Met at iHub; wants pricing" in briefs[0].note
