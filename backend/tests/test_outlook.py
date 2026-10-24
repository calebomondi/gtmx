"""Email through Outlook: sending (found again in Sent Items for its
conversation), answering in a conversation, and replies synced back."""

import uuid
from datetime import UTC, datetime

import psycopg

from backend.app.database.connect import AsyncSessionLocal
from backend.app.services import connections as connection_service
from backend.app.services import inbox, outlook
from backend.app.services.connections import ConnectionInfo
from backend.tests.helpers import stub_accounts
from backend.tests.test_lace_jobs import lace  # noqa: F401 -- fixture
from backend.tests.test_lace_outreach import _message
from backend.tests.test_laces_api import API, lace_runtime  # noqa: F401 -- fixture
from config import settings

# Outlook's ids are long: past what Gmail's needed.
THREAD = "AAQkAGI2" + "t" * 140
MESSAGE = "AAMkAGI2" + "m" * 140


def _outlook(monkeypatch, inbox_mail=(), sent_to="jane@alpha.test"):
    """A live shared Outlook; records each tool called, and answers Sent
    Items and Inbox listings."""
    calls = []

    def execute(entity, tool, arguments, connection_id):
        calls.append((tool, arguments))
        if tool == "OUTLOOK_OUTLOOK_LIST_MESSAGES" and arguments["folder"] == "SentItems":
            value = [{"id": MESSAGE, "conversationId": THREAD,
                      "toRecipients": [{"emailAddress": {"address": sent_to.upper()}}]}]
        else:
            value = list(inbox_mail)
        return {"data": {"response_data": {"value": value}}, "error": None, "log_id": "log_1"}
    stub_accounts(monkeypatch, {"outlook"})
    monkeypatch.setattr(connection_service, "execute_tool", execute)
    return calls


def test_inbox_mail_reads_as_the_reply_sync_expects(monkeypatch):
    monkeypatch.setattr(connection_service, "execute_tool", lambda *a: {"data": {"response_data": {"value": [{
        "id": "m1", "conversationId": "c1", "subject": "Re: Hi", "receivedDateTime": "2026-10-24T10:00:00Z",
        "from": {"emailAddress": {"name": "Jane Doe", "address": "jane@alpha.test"}},
        "uniqueBody": {"contentType": "html", "content": "<div>Sounds good &amp; cheap.</div><style>p{}</style>"},
    }]}}, "error": None, "log_id": "l"})
    account = ConnectionInfo("ca_o", "outlook", "live", None, None, None, "u1")
    assert outlook.recent(account, "2026-10-20T00:00:00+00:00") == [{
        "messageId": "m1", "threadId": "c1", "sender": "Jane Doe <jane@alpha.test>", "subject": "Re: Hi",
        "messageText": "Sounds good & cheap.", "messageTimestamp": "2026-10-24T10:00:00Z"}]


def test_a_new_email_goes_out_through_outlook_and_keeps_its_conversation(client, lace, lace_runtime, user,  # noqa: F811
                                                                       monkeypatch):
    calls = _outlook(monkeypatch)
    message = _message(lace, user.id)
    assert client.post(f"{API}/laces/{lace}/outreach/{message}/send").json()["status"] == "sent"
    assert calls[0] == ("OUTLOOK_OUTLOOK_SEND_EMAIL", {"to_email": "jane@alpha.test", "subject": "Hi",
                                                       "body": "Hello Jane", "is_html": False,
                                                       "save_to_sent_items": True})
    with psycopg.connect(settings.database_url) as conn:
        assert conn.execute("SELECT thread_id, provider_message_id FROM lace_outreach WHERE id = %s",
                            (message,)).fetchone() == (THREAD, MESSAGE)


def test_an_answer_goes_into_the_outlook_conversation(client, lace, lace_runtime, user, monkeypatch):  # noqa: F811
    calls = _outlook(monkeypatch)
    with psycopg.connect(settings.database_url, autocommit=True) as conn:
        conn.execute("INSERT INTO lace_outreach (id, lace_id, user_id, channel, direction, status, thread_id,"
                     " provider_message_id, recipient_address, body, sent_at) VALUES"
                     " (%s, %s, %s, 'email', 'inbound', 'received', %s, %s, 'jane@alpha.test', 'How much?', %s)",
                     (uuid.uuid4(), lace, user.id, THREAD, MESSAGE, datetime.now(UTC)))
        answer = conn.execute("INSERT INTO lace_outreach (id, lace_id, user_id, channel, thread_id, recipient_address,"
                              " body, status) VALUES (%s, %s, %s, 'email', %s, 'jane@alpha.test', 'From $20.', 'draft')"
                              " RETURNING id", (uuid.uuid4(), lace, user.id, THREAD)).fetchone()[0]
    assert client.post(f"{API}/laces/{lace}/outreach/{answer}/send").json()["status"] == "sent"
    assert calls == [("OUTLOOK_OUTLOOK_REPLY_EMAIL", {"message_id": MESSAGE, "comment": "From $20."})]


def test_gmail_is_used_when_the_lace_has_both(client, lace, lace_runtime, user, monkeypatch):  # noqa: F811
    calls = _outlook(monkeypatch)
    stub_accounts(monkeypatch, {"gmail", "outlook"})
    client.post(f"{API}/laces/{lace}/outreach/{_message(lace, user.id)}/send")
    assert calls[0][0] == "GMAIL_SEND_EMAIL"


def test_replies_sync_from_outlook(client, lace, lace_runtime, user, monkeypatch):  # noqa: F811
    with psycopg.connect(settings.database_url, autocommit=True) as conn:
        conn.execute("INSERT INTO lace_outreach (id, lace_id, user_id, channel, direction, status, thread_id,"
                     " recipient_address, subject, body, sent_at) VALUES"
                     " (%s, %s, %s, 'email', 'outbound', 'sent', %s, 'jane@alpha.test', 'Hi', 'Hello Jane', %s)",
                     (uuid.uuid4(), lace, user.id, THREAD, datetime.now(UTC)))
    _outlook(monkeypatch, inbox_mail=[{
        "id": "AAMk-reply", "conversationId": THREAD, "subject": "Re: Hi", "receivedDateTime": datetime.now(UTC).isoformat(),
        "from": {"emailAddress": {"name": "Jane", "address": "jane@alpha.test"}},
        "uniqueBody": {"contentType": "text", "content": "What does it cost?"},
    }])

    async def sync():
        async with AsyncSessionLocal() as db:
            return await inbox.sync_user(db, user.id)
    result = client.portal.call(sync)
    assert [(r.body, r.recipient_address) for r in result.replies] == [("What does it cost?", "jane@alpha.test")]
