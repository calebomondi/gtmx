"""Replies to a Lace's outreach: synced from Gmail into the Lace's thread,
read, answered as a draft in the same thread, and honoured when they ask to
stop. The Lace tells the founder; nothing is sent."""

import json
import uuid
from datetime import UTC, datetime

import psycopg
from langchain_core.messages import AIMessage

from agents.pipelines.outreach.gtm_replies import ReplyResult
from agents.schemas.accounts import AccountRecord, TriggerEvent
from agents.schemas.outreach import ReplyAnalysis, ReplyDraft
from backend.app.runs import lace_jobs, scheduler
from backend.app.services import connections as connection_service
from backend.tests.helpers import stub_accounts
from backend.tests.test_lace_jobs import _runs, _wait_for_turns, lace  # noqa: F401 -- fixture
from backend.tests.test_laces_api import API, lace_runtime  # noqa: F401 -- fixture
from backend.tests.test_runs import _wait_for_status
from config import settings


def _sent(lace_id, user_id, thread="t_1") -> uuid.UUID:
    record = AccountRecord(name="SunCulture", website="https://sunculture.test",
                           trigger_event=TriggerEvent(event="Raised", signal_type="funding_round", source="https://n.test"))
    with psycopg.connect(settings.database_url, autocommit=True) as conn:
        account = conn.execute(
            "INSERT INTO lace_accounts (id, lace_id, key, name, account_type, record) VALUES"
            " (%s, %s, 'sunculture.test', 'SunCulture', 'company', %s) RETURNING id",
            (uuid.uuid4(), lace_id, json.dumps(record.model_dump(mode="json")))).fetchone()[0]
        conn.execute(
            "INSERT INTO lace_outreach (id, lace_id, user_id, account_id, channel, recipient_name, recipient_company,"
            " recipient_address, subject, body, status, thread_id, sent_at) VALUES (%s, %s, %s, %s, 'email',"
            " 'Samir Ibrahim', 'SunCulture', 'samir@sunculture.test', 'Your Series B', 'Hi Samir', 'sent', %s, %s)",
            (uuid.uuid4(), lace_id, user_id, account, thread, datetime.now(UTC)))
    return account


def _inbox(monkeypatch, *messages):
    def execute(user_id, tool, arguments, account):
        return {"data": {"messages": list(messages)}, "error": None, "log_id": "log_1"}

    stub_accounts(monkeypatch, {"gmail"}, name="me@acme.example")
    monkeypatch.setattr(connection_service, "execute_tool", execute)

    async def no_slots(db, user_id):
        return [], ""
    monkeypatch.setattr(lace_jobs.calendar_service, "free_slots", no_slots)

    async def sender(user_id):
        return "Caleb"
    monkeypatch.setattr(lace_jobs.outreach_service, "sender_for_user", sender)


def _reply(message_id, thread="t_1", text="Interesting. What does it cost?", sender="Samir Ibrahim <samir@sunculture.test>"):
    return {"messageId": message_id, "threadId": thread, "sender": sender, "subject": "Re: Your Series B",
            "messageText": text, "messageTimestamp": datetime.now(UTC).isoformat()}


def _reader(monkeypatch, intent="question", answer="Hi Samir, pricing starts at...", seen=None):
    def draft_reply(brief):
        if seen is not None:
            seen.append(brief)
        analysis = ReplyAnalysis(intent=intent, summary="They asked about price.", reply_needed=bool(answer))
        return ReplyResult(analysis, ReplyDraft(body=answer) if answer else None)
    monkeypatch.setattr(lace_jobs.gtm_replies, "draft_reply", draft_reply)


def test_a_reply_is_read_answered_as_a_draft_and_reported(client, lace, lace_runtime, user, monkeypatch):  # noqa: F811
    _sent(lace, user.id)
    # Gmail quotes the email it answers below the reply: only the reply is kept.
    _inbox(monkeypatch, _reply("m_1", text="Interesting. What does it cost?\n\nOn Thu, Oct 22, 2026, 15:14 Caleb "
                                           "<caleb@shanga.test> wrote:\n\n> Hi Samir"))
    seen = []
    _reader(monkeypatch, seen=seen)
    lace_runtime.append(AIMessage(content="Samir asked about pricing; an answer is ready for you."))

    assert client.portal.call(scheduler.sync_inboxes) == 1
    [job] = client.portal.call(_runs, lace, "lace_reply")
    client.portal.call(_wait_for_status, job.id, {"completed"})
    turns = client.portal.call(_wait_for_turns, lace, 1)

    assert seen[0].thread == [("us", "Hi Samir"), ("them", "Interesting. What does it cost?")]
    assert seen[0].sender_name == "Caleb" and "SunCulture" in seen[0].account
    update = turns[-1].input["updates"][0]
    assert "Samir Ibrahim at SunCulture replied (question)" in update and "An answer is drafted in Outreach" in update
    messages = client.get(f"{API}/laces/{lace}/outreach").json()
    inbound = next(m for m in messages if m["direction"] == "inbound")
    answer = next(m for m in messages if m["status"] == "draft")
    assert inbound["status"] == "received" and inbound["body"] == "Interesting. What does it cost?"
    assert answer["recipient_address"] == "samir@sunculture.test" and answer["body"].startswith("Hi Samir")
    with psycopg.connect(settings.database_url) as conn:
        assert conn.execute("SELECT thread_id FROM lace_outreach WHERE status = 'draft'").fetchone()[0] == "t_1"
        assert conn.execute("SELECT intent FROM lace_outreach WHERE direction = 'inbound'").fetchone()[0] == "question"
        assert conn.execute("SELECT count(*) FROM signals").fetchone()[0] == 0  # the Lace tells the founder itself
        kind, title, ref_type, ref_id = conn.execute("SELECT kind, title, ref_type, ref_id FROM lace_activity").fetchone()
        assert (kind, title, ref_type, str(ref_id)) == ("reply_received", "SunCulture replied (question)", "outreach",
                                                        inbound["id"])
    # Synced once: the same message is not stored twice.
    assert client.portal.call(scheduler.sync_inboxes) == 0


def test_asking_to_stop_is_honoured(client, lace, lace_runtime, user, monkeypatch):  # noqa: F811
    account = _sent(lace, user.id)
    _inbox(monkeypatch, _reply("m_1", text="Please remove me from your list."))
    _reader(monkeypatch, intent="unsubscribe", answer=None)
    lace_runtime.append(AIMessage(content="Samir asked not to be contacted."))
    client.portal.call(scheduler.sync_inboxes)
    [job] = client.portal.call(_runs, lace, "lace_reply")
    client.portal.call(_wait_for_status, job.id, {"completed"})
    turns = client.portal.call(_wait_for_turns, lace, 1)
    assert "asked not to be contacted" in turns[-1].input["updates"][0]
    with psycopg.connect(settings.database_url, autocommit=True) as conn:
        assert conn.execute("SELECT do_not_contact FROM lace_accounts WHERE id = %s", (account,)).fetchone()[0]
        draft = conn.execute("INSERT INTO lace_outreach (id, lace_id, user_id, account_id, channel, recipient_address,"
                             " subject, body) VALUES (%s, %s, %s, %s, 'email', 'samir@sunculture.test', 'Hi', 'x')"
                             " RETURNING id", (uuid.uuid4(), lace, user.id, account)).fetchone()[0]
    refused = client.post(f"{API}/laces/{lace}/outreach/{draft}/send")
    assert refused.status_code == 409 and "asked not to be contacted" in refused.json()["detail"]


def test_one_run_reads_every_reply_that_came_in(client, lace, lace_runtime, user, monkeypatch):  # noqa: F811
    _sent(lace, user.id, thread="t_1")
    with psycopg.connect(settings.database_url, autocommit=True) as conn:
        conn.execute("INSERT INTO lace_outreach (id, lace_id, user_id, channel, recipient_company, recipient_address,"
                     " body, status, thread_id, sent_at) VALUES (%s, %s, %s, 'email', 'Enzi', 'george@enzi.test',"
                     " 'Hi George', 'sent', 't_2', now())", (uuid.uuid4(), lace, user.id))
    _inbox(monkeypatch, _reply("m_1"), _reply("m_2", thread="t_2", sender="George <george@enzi.test>"))
    _reader(monkeypatch)
    lace_runtime.append(AIMessage(content="Two replies came in."))
    assert client.portal.call(scheduler.sync_inboxes) == 2
    runs = client.portal.call(_runs, lace, "lace_reply")
    assert len(runs) == 1
    run = client.portal.call(_wait_for_status, runs[0].id, {"completed"})
    assert run.progress == {"replies": 2}
    client.portal.call(_wait_for_turns, lace, 1)


def test_several_messages_in_one_conversation_get_one_answer(client, lace, lace_runtime, user, monkeypatch):  # noqa: F811
    _sent(lace, user.id, thread="t_1")
    _inbox(monkeypatch, _reply("m_1", text="Interesting."), _reply("m_2", text="What does it cost?"))
    _reader(monkeypatch)
    lace_runtime.append(AIMessage(content="Samir wrote twice; one answer is ready."))
    assert client.portal.call(scheduler.sync_inboxes) == 2
    [run] = client.portal.call(_runs, lace, "lace_reply")
    assert client.portal.call(_wait_for_status, run.id, {"completed"}).progress == {"replies": 1}
    client.portal.call(_wait_for_turns, lace, 1)
    with psycopg.connect(settings.database_url) as conn:
        drafts = conn.execute("SELECT count(*) FROM lace_outreach WHERE lace_id = %s AND status = 'draft'",
                              (lace,)).fetchone()[0]
        unread = conn.execute("SELECT count(*) FROM lace_outreach WHERE lace_id = %s AND direction = 'inbound'"
                              " AND intent IS NULL", (lace,)).fetchone()[0]
    assert (drafts, unread) == (1, 0)  # one answer; both messages read


def test_a_bounce_marks_the_lace_send(client, lace, lace_runtime, user, monkeypatch):  # noqa: F811
    _sent(lace, user.id)
    _inbox(monkeypatch, {"messageId": "b_1", "threadId": "t_1", "sender": "Mail Delivery Subsystem <mailer-daemon@googlemail.com>",
                         "subject": "Delivery Status Notification (Failure)", "messageText": "samir@sunculture.test bounced",
                         "messageTimestamp": datetime.now(UTC).isoformat()})
    client.portal.call(scheduler.sync_inboxes)
    with psycopg.connect(settings.database_url) as conn:
        assert conn.execute("SELECT status FROM lace_outreach WHERE direction = 'outbound'").fetchone()[0] == "bounced"
    assert client.portal.call(_runs, lace, "lace_reply") == []  # a bounce is not a reply to answer
