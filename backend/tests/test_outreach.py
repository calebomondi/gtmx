"""Outreach: the agent drafts per account, the user edits, and an email is
sent only on an explicit request, through the user's own live Gmail."""

import asyncio
import json
import uuid

import psycopg
import pytest

from agents.schemas.outreach import OutreachDraft
from backend.app.runs import background, manager
from backend.app.services import connections as connection_service
from backend.app.services.connections import ConnectionInfo
from backend.tests.helpers import make_user
from backend.tests.test_runs import _wait_for_status
from config import settings

API = "/api/v1/workspaces"


async def _drain():
    if manager._tasks:
        await asyncio.gather(*manager._tasks.values(), return_exceptions=True)


@pytest.fixture
def account_id(owned):
    with psycopg.connect(settings.database_url, autocommit=True) as conn:
        conn.execute(
            "UPDATE accounts SET key_contacts = %s, why_reach_out = %s WHERE id = %s",
            (json.dumps([{"name": "Ada Lovelace", "email": "ada@acme.example"}]), json.dumps(["Hiring 3 SDRs"]), owned["account"]),
        )
    return owned["account"]


@pytest.fixture
def drafted(client, owned, account_id, monkeypatch):
    seen = {}

    def fake_draft(channel, context, account, sender):
        seen.update(channel=channel, account=account, sender=sender)
        return OutreachDraft(subject="Quick idea for Acme", body="Hi Ada, ...")
    monkeypatch.setattr(background.draft_messages, "draft", fake_draft)
    run = client.post(f"{API}/{owned['workspace']}/outreach/drafts", json={"account_ids": [account_id]}).json()
    client.portal.call(_wait_for_status, uuid.UUID(run["id"]), {"completed"})
    client.portal.call(_drain)
    messages = client.get(f"{API}/{owned['workspace']}/outreach").json()["messages"]
    return {"messages": messages, "seen": seen, "workspace": owned["workspace"]}


@pytest.fixture
def gmail(monkeypatch, user):
    calls = []

    async def connections(user_id):
        return [ConnectionInfo("ca_gmail", "gmail", "live", "me@acme.example", None, None)]
    monkeypatch.setattr(connection_service, "list_for_user", connections)

    def execute(user_id, tool, arguments, account):
        calls.append((tool, arguments, account))
        return {"data": {"id": "m1"}, "error": None, "log_id": "log_1"}
    monkeypatch.setattr(connection_service, "execute_tool", execute)
    return calls


def test_drafts_are_grounded_and_addressed(drafted):
    [message] = drafted["messages"]
    assert (message["status"], message["recipient_address"], message["recipient_name"]) == ("draft", "ada@acme.example", "Ada Lovelace")
    assert message["subject"] == "Quick idea for Acme"
    assert "Hiring 3 SDRs" in drafted["seen"]["account"] and "Contact first name: Ada" in drafted["seen"]["account"]
    assert drafted["seen"]["sender"] == "Owner"


def test_send_goes_through_the_users_gmail_once(client, drafted, gmail):
    path = f"{API}/{drafted['workspace']}/outreach/messages/{drafted['messages'][0]['id']}"
    edited = client.patch(path, json={"subject": "Edited subject"}).json()
    assert edited["subject"] == "Edited subject"

    sent = client.post(f"{path}/send").json()
    assert sent["status"] == "sent" and sent["sent_at"]
    assert gmail == [("GMAIL_SEND_EMAIL", {"recipient_email": "ada@acme.example", "subject": "Edited subject", "body": "Hi Ada, ..."}, "ca_gmail")]
    assert client.post(f"{path}/send").status_code == 409  # never twice
    assert client.patch(path, json={"body": "x"}).status_code == 409  # sent is final


def test_send_guards(client, drafted, gmail, monkeypatch):
    path = f"{API}/{drafted['workspace']}/outreach/messages/{drafted['messages'][0]['id']}"
    client.patch(path, json={"recipient_address": "not-an-email"})
    assert client.post(f"{path}/send").status_code == 422
    client.patch(path, json={"recipient_address": "ada@acme.example"})

    monkeypatch.setattr(settings, "max_outreach_sends_per_day", 0)
    assert client.post(f"{path}/send").status_code == 429
    monkeypatch.setattr(settings, "max_outreach_sends_per_day", 50)

    async def none(user_id):
        return []
    monkeypatch.setattr(connection_service, "list_for_user", none)
    assert client.post(f"{path}/send").status_code == 409  # no Gmail connected
    assert gmail == []

    client.sign_in(make_user("Intruder"))
    assert client.post(f"{path}/send").status_code == 404


def test_gmail_failures_are_recorded_not_raised(client, drafted, gmail, monkeypatch):
    path = f"{API}/{drafted['workspace']}/outreach/messages/{drafted['messages'][0]['id']}"
    monkeypatch.setattr(connection_service, "execute_tool", lambda *a: {"data": None, "error": "invalid to", "log_id": "log_2"})
    failed = client.post(f"{path}/send").json()
    assert failed["status"] == "failed" and "recipient" in failed["error"]

    def boom(*a):
        raise RuntimeError("network down with internals")
    monkeypatch.setattr(connection_service, "execute_tool", boom)
    failed = client.post(f"{path}/send").json()  # a failed message may be retried
    assert failed["status"] == "failed" and "internals" not in failed["error"]


def test_linkedin_drafts_are_copied_not_sent(client, owned, account_id, monkeypatch, gmail):
    monkeypatch.setattr(background.draft_messages, "draft", lambda *a: OutreachDraft(subject="", body="Hi"))
    run = client.post(f"{API}/{owned['workspace']}/outreach/drafts", json={"account_ids": [account_id], "channel": "linkedin"}).json()
    client.portal.call(_wait_for_status, uuid.UUID(run["id"]), {"completed"})
    client.portal.call(_drain)
    [message] = client.get(f"{API}/{owned['workspace']}/outreach").json()["messages"]
    assert message["channel"] == "linkedin" and message["recipient_address"] is None
    assert client.post(f"{API}/{owned['workspace']}/outreach/messages/{message['id']}/send").status_code == 409


def test_recipient_prefers_people_and_never_role_inboxes():
    from types import SimpleNamespace

    from backend.app.services.outreach import recipient_for

    def pick(contacts):
        return recipient_for(SimpleNamespace(key_contacts=contacts), "email")

    assert pick([{"email": "legal@anyscale.com"}, {"email": "support@openai.com"}]) == (None, None)
    assert pick([{"email": "hello@acme.io"}, {"name": "Ada", "email": "ada@acme.io"}]) == ("Ada", "ada@acme.io")
    assert pick([{"email": "accommodations@harvey.ai"}, {"email": "hi@halmoslabs.com"}]) == (None, "hi@halmoslabs.com")
    assert pick([{"name": "Ada"}, {"email": "linus@halmoslabs.com"}])[1] == "linus@halmoslabs.com"
    assert pick([{"email": "not-an-email"}]) == (None, None)
