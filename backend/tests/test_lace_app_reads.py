"""Reading the founder's mail, calendar and X mentions through the apps on
for a Lace: shaped for the Lace, and a founder's own mailbox read only for
them."""

import uuid

import psycopg
import pytest

from agents.lace.apps import AppError
from backend.app.database.connect import AsyncSessionLocal
from backend.app.services import lace_apps
from backend.tests.helpers import stub_accounts
from config import settings


def _lace() -> tuple[uuid.UUID, uuid.UUID]:
    owner = uuid.uuid4()
    with psycopg.connect(settings.database_url, autocommit=True) as conn:
        lace = conn.execute("INSERT INTO laces (id, user_id, name, website) VALUES (%s, %s, 'Ada', 'https://acme.test')"
                            " RETURNING id", (uuid.uuid4(), owner)).fetchone()[0]
    return lace, owner


def _tools(monkeypatch, responses: dict) -> list:
    calls = []

    def execute(entity, tool, arguments, connection_id):
        calls.append((tool, arguments, connection_id))
        return {"data": responses[tool], "error": None, "log_id": "l1"}
    monkeypatch.setattr(lace_apps.connection_service, "execute_tool", execute)
    return calls


async def test_the_owner_searches_their_gmail(monkeypatch):
    stub_accounts(monkeypatch, {"gmail"})
    calls = _tools(monkeypatch, {"GMAIL_FETCH_EMAILS": {"messages": [
        {"threadId": "t1", "sender": "Jane <jane@acme.test>", "subject": "Pilot", "messageTimestamp": "2026-11-03",
         "messageText": "  We'd love to try it.  "}]}})
    lace, owner = _lace()
    found = await lace_apps.DbLaceApps(AsyncSessionLocal, lace, owner).email_search("from:jane@acme.test", 30)
    assert found == [{"thread_id": "t1", "from": "Jane <jane@acme.test>", "subject": "Pilot", "date": "2026-11-03",
                      "snippet": "We'd love to try it."}]
    assert calls[0][1]["query"] == "from:jane@acme.test newer_than:30d"


async def test_a_cofounder_cannot_read_the_owners_own_mail_but_can_read_the_startups(monkeypatch):
    stub_accounts(monkeypatch, {"gmail", "googlecalendar"})
    _tools(monkeypatch, {"GMAIL_FETCH_EMAILS": {"messages": []}, "GOOGLECALENDAR_EVENTS_LIST": {"items": []}})
    lace, _ = _lace()
    cofounder = lace_apps.DbLaceApps(AsyncSessionLocal, lace, uuid.uuid4())
    with pytest.raises(AppError, match="owner's own account"):
        await cofounder.email_search("pilot", 7)
    with pytest.raises(AppError, match="owner's own account"):
        await cofounder.calendar_events(7)
    # A mailbox connected for this Lace is the startup's: the team reads it.
    stub_accounts(monkeypatch, set(), own={"gmail"})
    assert await cofounder.email_search("pilot", 7) == []


async def test_a_thread_reads_oldest_first_and_bounded(monkeypatch):
    stub_accounts(monkeypatch, {"gmail"})
    _tools(monkeypatch, {"GMAIL_FETCH_MESSAGE_BY_THREAD_ID": {"messages": [
        {"sender": "jane@acme.test", "messageTimestamp": "1", "messageText": "x" * 5000},
        {"sender": "me", "messageTimestamp": "2", "preview": {"body": "Thanks!"}}]}})
    lace, owner = _lace()
    thread = await lace_apps.DbLaceApps(AsyncSessionLocal, lace, owner).email_thread("t1")
    assert [m["from"] for m in thread] == ["jane@acme.test", "me"]
    assert len(thread[0]["text"]) == lace_apps.EMAIL_CHARS and thread[1]["text"] == "Thanks!"


async def test_calendar_events_name_the_others_attending(monkeypatch):
    stub_accounts(monkeypatch, {"googlecalendar"})
    _tools(monkeypatch, {"GOOGLECALENDAR_EVENTS_LIST": {"items": [
        {"summary": "Call with Acme", "start": {"dateTime": "2026-11-05T10:00:00Z"}, "end": {"dateTime": "2026-11-05T10:30:00Z"},
         "attendees": [{"email": "me@thalace.com", "self": True}, {"email": "jane@acme.test", "displayName": "Jane"}]},
        {"start": {"date": "2026-11-06"}, "end": {"date": "2026-11-07"}}]}})
    lace, owner = _lace()
    events = await lace_apps.DbLaceApps(AsyncSessionLocal, lace, owner).calendar_events(7)
    assert events == [
        {"title": "Call with Acme", "start": "2026-11-05T10:00:00Z", "end": "2026-11-05T10:30:00Z",
         "attendees": [{"name": "Jane", "email": "jane@acme.test"}]},
        {"title": "(no title)", "start": "2026-11-06", "end": "2026-11-07", "attendees": []}]


async def test_x_mentions_name_who_posted(monkeypatch):
    stub_accounts(monkeypatch, {"x"})
    calls = _tools(monkeypatch, {
        "TWITTER_USER_LOOKUP_ME": {"data": {"id": "99", "username": "thalace"}},
        "TWITTER_GET_USER_MENTIONS": {"data": [{"id": "5", "author_id": "7", "text": "@thalace looks great",
                                                "created_at": "2026-11-04"}],
                                      "includes": {"users": [{"id": "7", "username": "jane", "name": "Jane"}]}}})
    lace, _ = _lace()
    mentions = await lace_apps.DbLaceApps(AsyncSessionLocal, lace).x_mentions()
    assert mentions == [{"author": "Jane", "handle": "jane", "text": "@thalace looks great", "date": "2026-11-04",
                         "url": "https://x.com/i/web/status/5"}]
    assert calls[1][1]["id"] == "99"


async def test_nothing_on_means_none(monkeypatch):
    stub_accounts(monkeypatch, set())
    lace, owner = _lace()
    apps = lace_apps.DbLaceApps(AsyncSessionLocal, lace, owner)
    assert await apps.email_search("x", 7) is None and await apps.calendar_events(7) is None
    assert await apps.x_mentions() is None
