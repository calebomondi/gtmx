"""Replies and bounces for sent outreach are synced from the user's Gmail into
the sent email's thread, once each, and reach the feed. Replying from GTMX
goes into the same thread."""

import json
import uuid

import psycopg
import pytest

from backend.app.services import connections as connection_service
from backend.app.services.connections import ConnectionInfo
from backend.tests.test_outreach import account_id, drafted  # noqa: F401 -- shared fixtures
from config import settings

API = "/api/v1/workspaces"


@pytest.fixture
def mailbox(monkeypatch):
    """A fake Gmail: sends get thread t1; the inbox holds `box["messages"]`."""
    box = {"messages": [], "calls": []}

    async def connections(db, user_id):
        return [ConnectionInfo("ca_gmail", "gmail", "live", "me@us.example", None, None)]
    monkeypatch.setattr(connection_service, "list_for_user", connections)

    def execute(user_id, tool, arguments, account):
        box["calls"].append((tool, arguments))
        if tool == "GMAIL_FETCH_EMAILS":
            return {"data": {"messages": box["messages"]}, "error": None, "log_id": "l"}
        return {"data": {"id": f"sent{len(box['calls'])}", "threadId": "t1"}, "error": None, "log_id": "l"}
    monkeypatch.setattr(connection_service, "execute_tool", execute)
    return box


def _sent(client, drafted):  # noqa: F811
    path = f"{API}/{drafted['workspace']}/outreach/messages/{drafted['messages'][0]['id']}"
    return client.post(f"{path}/send").json()


def _feed(client):
    return [s for s in client.get("/api/v1/signals").json() if "draft" not in s["title"]]


def _messages(client, workspace):
    return client.get(f"{API}/{workspace}/outreach").json()["messages"]


def test_replies_land_in_the_thread_once_and_reach_the_feed(client, drafted, mailbox):  # noqa: F811
    sent = _sent(client, drafted)
    assert sent["thread_id"] == "t1"
    mailbox["messages"] = [
        {"messageId": "r1", "threadId": "t1", "sender": "Ada Lovelace <ada@acme.example>",
         "subject": "Re: Quick idea for Acme", "messageText": "Sounds good, call Thursday?",
         "messageTimestamp": "2026-10-12T09:00:00Z"},
        {"messageId": "x1", "threadId": "other", "sender": "news@shop.example", "subject": "Sale", "messageText": "50% off"},
    ]
    sync = f"{API}/{drafted['workspace']}/outreach/sync"
    assert client.post(sync).json() == {"replies": 1, "bounced": 0}
    assert client.post(sync).json() == {"replies": 0, "bounced": 0}  # stored once

    reply = next(m for m in _messages(client, drafted["workspace"]) if m["direction"] == "inbound")
    assert (reply["thread_id"], reply["recipient_address"], reply["body"], reply["read_at"]) == (
        "t1", "ada@acme.example", "Sounds good, call Thursday?", None)
    assert [(s["title"], s["hot"]) for s in _feed(client)] == [("Ada Lovelace replied", True)]

    read = client.post(f"{API}/{drafted['workspace']}/outreach/messages/{reply['id']}/read").json()
    assert read["read_at"] is not None
    assert client.post(f"{API}/{drafted['workspace']}/outreach/messages/{reply['id']}/send").status_code == 409


def test_bounces_mark_the_sent_email(client, drafted, mailbox):  # noqa: F811
    _sent(client, drafted)
    mailbox["messages"] = [{
        "messageId": "b1", "threadId": "t9", "sender": "Mail Delivery Subsystem <mailer-daemon@googlemail.com>",
        "subject": "Delivery Status Notification (Failure)",
        "messageText": "Your message wasn't delivered to ada@acme.example because the address couldn't be found",
    }]
    assert client.post(f"{API}/{drafted['workspace']}/outreach/sync").json() == {"replies": 0, "bounced": 1}
    sent = next(m for m in _messages(client, drafted["workspace"]) if m["direction"] == "outbound")
    assert sent["status"] == "bounced"
    assert [s["title"] for s in _feed(client)] == ["Bounced: ada@acme.example"]


def test_a_draft_in_a_thread_is_sent_as_a_reply(client, drafted, mailbox, user):  # noqa: F811
    with psycopg.connect(settings.database_url, autocommit=True) as conn:
        reply_id = conn.execute(
            "INSERT INTO outreach_messages (id, workspace_id, user_id, channel, recipient_company, recipient_address,"
            " body, status, thread_id) VALUES (%s, %s, %s, 'email', 'Acme', 'ada@acme.example', 'Thursday 10am works.',"
            " 'draft', 't1') RETURNING id",
            (uuid.uuid4(), drafted["workspace"], user.id),
        ).fetchone()[0]
    sent = client.post(f"{API}/{drafted['workspace']}/outreach/messages/{reply_id}/send").json()
    assert sent["status"] == "sent"
    assert mailbox["calls"][-1] == ("GMAIL_REPLY_TO_THREAD", {
        "thread_id": "t1", "recipient_email": "ada@acme.example", "message_body": "Thursday 10am works.",
    })


def test_nothing_to_sync_without_sends(client, owned, mailbox):
    assert client.post(f"{API}/{owned['workspace']}/outreach/sync").json() == {"replies": 0, "bounced": 0}
    assert mailbox["calls"] == []


def test_scheduled_sync_covers_users_with_recent_sends(client, drafted, mailbox):  # noqa: F811
    from backend.app.runs import scheduler
    _sent(client, drafted)
    mailbox["messages"] = [{"messageId": "r2", "threadId": "t1", "sender": "ada@acme.example", "messageText": "Yes"}]
    assert client.portal.call(scheduler.sync_inboxes) == 1
    assert json.dumps(_feed(client)).count("replied") == 1
