"""Replies and bounces for sent outreach are synced from the user's Gmail into
the sent email's thread, once each, and reach the feed. Replying from GTMX
goes into the same thread."""

import asyncio
import json
import uuid

import psycopg
import pytest

from agents.pipelines.outreach.gtm_replies import ReplyResult
from agents.schemas.outreach import ReplyAnalysis, ReplyDraft
from backend.app.runs import background, manager
from backend.app.services import connections as connection_service
from backend.app.services.connections import ConnectionInfo
from backend.tests.test_outreach import account_id, drafted  # noqa: F401 -- shared fixtures
from config import settings

API = "/api/v1/workspaces"


async def _drain():
    if manager._tasks:
        await asyncio.gather(*manager._tasks.values(), return_exceptions=True)


@pytest.fixture(autouse=True)
def specialist(monkeypatch):
    """The GTM specialist's reply agent, stubbed: `answer["analysis"]` decides."""
    answer = {"analysis": ReplyAnalysis(intent="question", summary="Asks price", reply_needed=True), "briefs": []}

    def fake(brief):
        answer["briefs"].append(brief)
        analysis = answer["analysis"]
        return ReplyResult(analysis, ReplyDraft(body="Hi Ada, 20 seats is $400/mo. Thursday works.\n\nOwner")
                           if analysis.reply_needed else None)
    monkeypatch.setattr(background.gtm_replies, "draft_reply", fake)

    async def no_slots(db, user_id):
        return ["Thu 16 Oct, 10:00-10:30 (Africa/Nairobi)"], "Africa/Nairobi"
    monkeypatch.setattr(background.calendar_service, "free_slots", no_slots)

    async def owner(user_id):
        return "Owner"
    monkeypatch.setattr(background.outreach_service, "sender_for_user", owner)
    return answer


@pytest.fixture
def mailbox(monkeypatch):
    """A fake Gmail: sends get thread t1; the inbox holds `box["messages"]`."""
    box = {"messages": [], "calls": []}

    async def connections(db, user_id):
        return [ConnectionInfo("ca_gmail", "gmail", "live", "me@us.example", None, None),
                ConnectionInfo("ca_cal", "googlecalendar", "live", "me@us.example", None, None)]
    monkeypatch.setattr(connection_service, "list_for_user", connections)

    def execute(user_id, tool, arguments, account):
        box["calls"].append((tool, arguments))
        if tool == "GMAIL_FETCH_EMAILS":
            return {"data": {"messages": box["messages"]}, "error": None, "log_id": "l"}
        if tool == "GOOGLECALENDAR_CREATE_EVENT":
            return {"data": {"response_data": {"htmlLink": "https://calendar.example/e1"}}, "error": None, "log_id": "l"}
        return {"data": {"id": f"sent{len(box['calls'])}", "threadId": "t1"}, "error": None, "log_id": "l"}
    monkeypatch.setattr(connection_service, "execute_tool", execute)
    return box


def _sent(client, drafted):  # noqa: F811
    path = f"{API}/{drafted['workspace']}/outreach/messages/{drafted['messages'][0]['id']}"
    return client.post(f"{path}/send").json()


def _feed(client):
    return [s for s in client.get("/api/v1/signals").json() if "draft" not in s["title"].lower()]


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
    client.portal.call(_drain)
    assert client.post(sync).json() == {"replies": 0, "bounced": 0}  # stored once

    reply = next(m for m in _messages(client, drafted["workspace"]) if m["direction"] == "inbound")
    assert reply["intent"] == "question"
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


def test_a_reply_gets_a_threaded_answer_drafted_with_the_team_and_calendar(client, drafted, mailbox, specialist):  # noqa: F811
    _sent(client, drafted)
    mailbox["messages"] = [{"messageId": "r1", "threadId": "t1", "sender": "Ada Lovelace <ada@acme.example>",
                            "messageText": "What does 20 seats cost? Thursday 10am?"}]
    client.post(f"{API}/{drafted['workspace']}/outreach/sync")
    client.portal.call(_drain)

    [brief] = specialist["briefs"]
    assert brief.thread[-1] == ("them", "What does 20 seats cost? Thursday 10am?") and brief.thread[0][0] == "us"
    assert brief.free_slots == ["Thu 16 Oct, 10:00-10:30 (Africa/Nairobi)"] and brief.sender_name == "Owner"
    assert set(brief.research) >= {"product", "market", "competition", "gtm"}
    draft = next(m for m in _messages(client, drafted["workspace"]) if m["status"] == "draft" and m["thread_id"] == "t1")
    assert (draft["recipient_address"], draft["body"].startswith("Hi Ada"), draft["subject"]) == ("ada@acme.example", True, None)
    assert "Reply drafted for Ada Lovelace" in [s["title"] for s in client.get("/api/v1/signals").json()]


def test_out_of_office_needs_no_answer(client, drafted, mailbox, specialist):  # noqa: F811
    specialist["analysis"] = ReplyAnalysis(intent="out_of_office", summary="Away", reply_needed=False)
    _sent(client, drafted)
    mailbox["messages"] = [{"messageId": "r1", "threadId": "t1", "sender": "ada@acme.example", "messageText": "I'm away"}]
    client.post(f"{API}/{drafted['workspace']}/outreach/sync")
    client.portal.call(_drain)
    assert sorted(m["status"] for m in _messages(client, drafted["workspace"]) if m["thread_id"] == "t1") == ["received", "sent"]


def test_an_agreed_time_becomes_a_meeting_added_only_on_click(client, drafted, mailbox, specialist):  # noqa: F811
    specialist["analysis"] = ReplyAnalysis(intent="meeting_request", summary="Thu", reply_needed=True,
                                           agreed_time="2026-10-16T10:00:00")
    _sent(client, drafted)
    mailbox["messages"] = [{"messageId": "r1", "threadId": "t1", "sender": "ada@acme.example", "messageText": "Thu 10am"}]
    client.post(f"{API}/{drafted['workspace']}/outreach/sync")
    client.portal.call(_drain)
    draft = next(m for m in _messages(client, drafted["workspace"]) if m["status"] == "draft" and m["thread_id"] == "t1")
    assert draft["meeting"]["start"] == "2026-10-16T10:00:00" and draft["meeting"]["attendee"] == "ada@acme.example"
    assert not any(tool == "GOOGLECALENDAR_CREATE_EVENT" for tool, _ in mailbox["calls"])  # nothing booked by itself

    path = f"{API}/{drafted['workspace']}/outreach/messages/{draft['id']}/meeting"
    added = client.post(path).json()
    assert added["meeting"]["event_url"] == "https://calendar.example/e1"
    client.post(path)  # a second click doesn't double-book
    creates = [args for tool, args in mailbox["calls"] if tool == "GOOGLECALENDAR_CREATE_EVENT"]
    assert len(creates) == 1 and creates[0]["attendees"] == ["ada@acme.example"]
    assert creates[0]["start_datetime"] == "2026-10-16T10:00:00" and creates[0]["event_duration_minutes"] == 30


def test_only_received_replies_can_be_answered(client, drafted):  # noqa: F811
    path = f"{API}/{drafted['workspace']}/outreach/messages/{drafted['messages'][0]['id']}/reply-draft"
    assert client.post(path).status_code == 409


def test_an_unsubscribe_stops_all_further_outreach_to_the_account(client, drafted, mailbox, specialist, account_id):  # noqa: F811
    specialist["analysis"] = ReplyAnalysis(intent="unsubscribe", summary="Stop", reply_needed=False)
    _sent(client, drafted)
    mailbox["messages"] = [{"messageId": "u1", "threadId": "t1", "sender": "ada@acme.example", "messageText": "Remove me."}]
    client.post(f"{API}/{drafted['workspace']}/outreach/sync")
    client.portal.call(_drain)

    [account] = client.get(f"{API}/{drafted['workspace']}/accounts").json()["accounts"]
    assert account["do_not_contact"] is True
    assert client.post(f"{API}/{drafted['workspace']}/outreach/drafts",
                       json={"account_ids": [account_id]}).status_code == 409
    with psycopg.connect(settings.database_url, autocommit=True) as conn:
        draft_id = conn.execute(
            "INSERT INTO outreach_messages (id, workspace_id, user_id, account_id, channel, recipient_company,"
            " recipient_address, subject, body, status) SELECT %s, w.id, w.user_id, %s, 'email', 'Acme',"
            " 'ada@acme.example', 'Hi', 'Hello', 'draft' FROM workspaces w WHERE w.id = %s RETURNING id",
            (uuid.uuid4(), account_id, drafted["workspace"]),
        ).fetchone()[0]
    assert client.post(f"{API}/{drafted['workspace']}/outreach/messages/{draft_id}/send").status_code == 409
