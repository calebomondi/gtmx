"""Inbound DMs to a founder's Instagram business account or Facebook Page:
linked to one Lace, synced into its threads, read, and answered as a draft on
the same channel. Composio is faked with the response shapes it documents."""

from datetime import UTC, datetime, timedelta

import psycopg
import pytest
from langchain_core.messages import AIMessage

from agents.pipelines.outreach.gtm_replies import ReplyResult
from agents.schemas.outreach import ReplyAnalysis, ReplyDraft
from backend.app.runs import lace_jobs, scheduler
from backend.app.services import connections as connection_service
from backend.tests.helpers import stub_accounts
from backend.tests.helpers import make_user
from backend.tests.test_lace_jobs import _runs, _wait_for_turns, lace  # noqa: F401 -- fixture
from backend.tests.test_laces_api import API, _create, lace_runtime  # noqa: F401 -- fixture
from backend.tests.test_runs import _wait_for_status
from config import settings

NOW = datetime.now(UTC)


@pytest.fixture
def meta(monkeypatch):
    """A fake Composio for Instagram and Facebook. `box["messages"]` is the
    Instagram conversation's messages; `box["live"]` the live platforms."""
    box = {"live": {"instagram", "facebook"}, "calls": [], "messages": [
        {"id": "m1", "from": {"id": "u9", "username": "farmer_joe"}, "message": "Do you build irrigation sensors?",
         "created_time": (NOW - timedelta(minutes=5)).isoformat()},
        {"id": "m2", "from": {"id": "ig_1", "username": "shangalabs"}, "to": {"data": [{"id": "u9"}]},
         "message": "Hi Joe, thanks for asking!", "created_time": (NOW - timedelta(minutes=4)).isoformat()},
    ]}

    def execute(user_id, tool, arguments, connection_id):
        box["calls"].append(tool)
        data = {
            "INSTAGRAM_GET_USER_INFO": {"id": "ig_1", "username": "shangalabs"},
            "FACEBOOK_LIST_MANAGED_PAGES": {"data": [{"id": "pg_1", "name": "Shanga Labs"}]},
            "INSTAGRAM_LIST_ALL_CONVERSATIONS": {"data": [{"id": "c1", "updated_time": NOW.isoformat()}]},
            "INSTAGRAM_LIST_ALL_MESSAGES": {"data": box["messages"]},
        }.get(tool, {"data": []})
        return {"data": data, "error": None, "log_id": "l"}

    stub_accounts(monkeypatch, box["live"], name="me")
    monkeypatch.setattr(connection_service, "execute_tool", execute)

    def draft_reply(brief):
        box["brief"] = brief
        return ReplyResult(ReplyAnalysis(intent="question", summary="Asks if we build sensors.", reply_needed=True),
                           ReplyDraft(body="Hi Joe, yes: we design and build them."))
    monkeypatch.setattr(lace_jobs.gtm_replies, "draft_reply", draft_reply)

    async def no_slots(db, user_id):
        return [], ""
    monkeypatch.setattr(lace_jobs.calendar_service, "free_slots", no_slots)

    async def sender(user_id):
        return "Caleb"
    monkeypatch.setattr(lace_jobs.outreach_service, "sender_for_user", sender)
    return box


def test_linking_offers_only_the_founders_own_accounts(client, lace, lace_runtime, meta):  # noqa: F811
    assert client.get(f"{API}/laces/{lace}/channels/available?platform=instagram").json() == [
        {"id": "ig_1", "name": "shangalabs"}]
    assert client.get(f"{API}/laces/{lace}/channels/available?platform=facebook").json() == [
        {"id": "pg_1", "name": "Shanga Labs"}]
    assert client.post(f"{API}/laces/{lace}/channels", json={"platform": "instagram", "account_id": "someone_else"}
                       ).status_code == 422
    linked = client.post(f"{API}/laces/{lace}/channels", json={"platform": "instagram", "account_id": "ig_1"})
    assert linked.status_code == 201 and linked.json()["account_name"] == "shangalabs"
    # One Lace per account.
    other = _create(client, name="Bob", website="bob.test").json()["lace"]["id"]
    assert client.post(f"{API}/laces/{other}/channels", json={"platform": "instagram", "account_id": "ig_1"}
                       ).status_code == 409
    channel_id = linked.json()["id"]
    client.sign_in(make_user("Intruder"))
    assert client.get(f"{API}/laces/{lace}/channels").status_code == 404
    assert client.delete(f"{API}/laces/{lace}/channels/{channel_id}").status_code == 404


def test_linking_needs_a_live_connection(client, lace, lace_runtime, meta):  # noqa: F811
    meta["live"].clear()
    meta["live"].add("facebook")
    refused = client.get(f"{API}/laces/{lace}/channels/available?platform=instagram")
    assert refused.status_code == 409 and "Connect an Instagram" in refused.json()["detail"]


def test_a_dm_is_synced_read_and_answered_on_its_channel(client, lace, lace_runtime, meta):  # noqa: F811
    client.post(f"{API}/laces/{lace}/channels", json={"platform": "instagram", "account_id": "ig_1"})
    lace_runtime.append(AIMessage(content="farmer_joe asked on Instagram whether you build irrigation sensors."))

    assert client.portal.call(scheduler.sync_lace_channels) == 1
    [job] = client.portal.call(_runs, lace, "lace_reply")
    client.portal.call(_wait_for_status, job.id, {"completed"})
    turns = client.portal.call(_wait_for_turns, lace, 1)

    assert meta["brief"].thread == [("them", "Do you build irrigation sensors?"), ("us", "Hi Joe, thanks for asking!")]
    assert "farmer_joe on instagram" in meta["brief"].account
    assert "farmer_joe by instagram DM replied (question)" in turns[-1].input["updates"][0]
    messages = client.get(f"{API}/laces/{lace}/outreach").json()
    answer = next(m for m in messages if m["status"] == "draft")
    assert (answer["channel"], answer["recipient_address"], answer["thread_id"]) == ("instagram", "u9", "c1")
    ours = next(m for m in messages if m["direction"] == "outbound" and m["status"] == "sent")
    assert ours["body"] == "Hi Joe, thanks for asking!" and ours["recipient_address"] == "u9"
    # Synced once; a later sync with nothing new reads no conversation again.
    assert client.portal.call(scheduler.sync_lace_channels) == 0
    with psycopg.connect(settings.database_url) as conn:
        assert conn.execute("SELECT count(*) FROM lace_outreach WHERE provider_message_id = 'm1'").fetchone()[0] == 1
        assert conn.execute("SELECT synced_until IS NOT NULL FROM lace_channels").fetchone()[0]


def test_a_disconnected_account_is_skipped(client, lace, lace_runtime, meta):  # noqa: F811
    client.post(f"{API}/laces/{lace}/channels", json={"platform": "instagram", "account_id": "ig_1"})
    meta["live"].clear()
    meta["calls"].clear()
    assert client.portal.call(scheduler.sync_lace_channels) == 0
    assert meta["calls"] == []


def _answer(lace_id, channel="instagram", thread="c1", recipient="u9"):
    with psycopg.connect(settings.database_url, autocommit=True) as conn:
        user_id = conn.execute("SELECT user_id FROM laces WHERE id = %s", (lace_id,)).fetchone()[0]
        return conn.execute(
            "INSERT INTO lace_outreach (id, lace_id, user_id, channel, recipient_address, body, thread_id)"
            " VALUES (gen_random_uuid(), %s, %s, %s, %s, 'Hi Joe, yes we do.', %s) RETURNING id",
            (lace_id, user_id, channel, recipient, thread)).fetchone()[0]


def _send_result(monkeypatch, meta, error=None):
    sent = []
    original = connection_service.execute_tool

    def execute(user_id, tool, arguments, connection_id):
        if tool in ("INSTAGRAM_SEND_TEXT_MESSAGE", "FACEBOOK_SEND_MESSAGE"):
            sent.append((tool, arguments))
            return {"data": None if error else {"recipient_id": "u9", "message_id": "mid_1"}, "error": error,
                    "log_id": "l9"}
        return original(user_id, tool, arguments, connection_id)
    monkeypatch.setattr(connection_service, "execute_tool", execute)
    return sent


@pytest.mark.parametrize("platform, account, tool, arguments", [
    ("instagram", "ig_1", "INSTAGRAM_SEND_TEXT_MESSAGE",
     {"ig_user_id": "ig_1", "recipient_id": "u9", "text": "Hi Joe, yes we do."}),
    ("facebook", "pg_1", "FACEBOOK_SEND_MESSAGE",
     {"page_id": "pg_1", "recipient_id": "u9", "message_text": "Hi Joe, yes we do.", "messaging_type": "RESPONSE"}),
])
def test_an_answer_goes_out_in_its_conversation(client, lace, lace_runtime, meta, monkeypatch,  # noqa: F811
                                                 platform, account, tool, arguments):
    client.post(f"{API}/laces/{lace}/channels", json={"platform": platform, "account_id": account})
    sent = _send_result(monkeypatch, meta)
    message = _answer(lace, channel=platform)
    out = client.post(f"{API}/laces/{lace}/outreach/{message}/send").json()
    assert out["status"] == "sent" and out["sent_at"]
    assert sent == [(tool, arguments)]
    with psycopg.connect(settings.database_url) as conn:
        assert conn.execute("SELECT provider_message_id, provider_log_id FROM lace_outreach WHERE id = %s",
                            (message,)).fetchone() == ("mid_1", "l9")
    assert client.post(f"{API}/laces/{lace}/outreach/{message}/send").status_code == 409  # sent once


def test_outside_the_window_says_so(client, lace, lace_runtime, meta, monkeypatch):  # noqa: F811
    client.post(f"{API}/laces/{lace}/channels", json={"platform": "instagram", "account_id": "ig_1"})
    _send_result(monkeypatch, meta, error='{"error": {"code": 10, "error_subcode": 2534022}}')
    out = client.post(f"{API}/laces/{lace}/outreach/{_answer(lace)}/send").json()
    assert out["status"] == "failed" and "outside Instagram's reply window" in out["error"]
    assert client.post(f"{API}/laces/{lace}/outreach/{_answer(lace)}/mark-sent").json()["status"] == "sent"


def test_without_a_linked_account_or_a_conversation_it_is_a_handoff(client, lace, lace_runtime, meta, monkeypatch):  # noqa: F811
    sent = _send_result(monkeypatch, meta)
    unlinked = client.post(f"{API}/laces/{lace}/outreach/{_answer(lace)}/send")
    assert unlinked.status_code == 409 and "start this chat yourself" in unlinked.json()["detail"]
    client.post(f"{API}/laces/{lace}/channels", json={"platform": "instagram", "account_id": "ig_1"})
    first_touch = client.post(f"{API}/laces/{lace}/outreach/{_answer(lace, thread=None)}/send")
    assert first_touch.status_code == 409 and sent == []


def test_a_reply_joins_the_chat_the_founder_started_by_hand(client, lace, lace_runtime, meta):  # noqa: F811
    """Meta lets apps answer only people who wrote first: the founder sent the
    first message by hand and marked it sent. When the person replies, their
    conversation is the one the founder started."""
    client.post(f"{API}/laces/{lace}/channels", json={"platform": "instagram", "account_id": "ig_1"})
    with psycopg.connect(settings.database_url, autocommit=True) as conn:
        user_id = conn.execute("SELECT user_id FROM laces WHERE id = %s", (lace,)).fetchone()[0]
        account = conn.execute(
            "INSERT INTO lace_accounts (id, lace_id, key, name, account_type, record) VALUES"
            " (gen_random_uuid(), %s, 'joefarms', 'Joe Farms', 'company', '{}') RETURNING id", (lace,)).fetchone()[0]
        first = conn.execute(
            "INSERT INTO lace_outreach (id, lace_id, user_id, account_id, channel, recipient_name, recipient_company,"
            " recipient_address, body, status, sent_at) VALUES (gen_random_uuid(), %s, %s, %s, 'instagram', 'Joe',"
            " 'Joe Farms', 'https://www.instagram.com/Farmer_Joe', 'Hi Joe, thanks for asking!', 'sent', now())"
            " RETURNING id", (lace, user_id, account)).fetchone()[0]
    lace_runtime.append(AIMessage(content="Joe from Joe Farms replied on Instagram."))
    client.portal.call(scheduler.sync_lace_channels)
    [job] = client.portal.call(_runs, lace, "lace_reply")
    client.portal.call(_wait_for_status, job.id, {"completed"})

    with psycopg.connect(settings.database_url) as conn:
        # The hand-sent message took the conversation, and wasn't stored twice when synced back.
        assert conn.execute("SELECT thread_id, provider_message_id FROM lace_outreach WHERE id = %s",
                            (first,)).fetchone() == ("c1", "m2")
        assert conn.execute("SELECT count(*) FROM lace_outreach WHERE body = 'Hi Joe, thanks for asking!'"
                            ).fetchone()[0] == 1
        # Their reply carries the account and company it was started with.
        assert conn.execute("SELECT account_id, recipient_company, recipient_name FROM lace_outreach"
                            " WHERE provider_message_id = 'm1'").fetchone() == (account, "Joe Farms", "Joe")
    answer = next(m for m in client.get(f"{API}/laces/{lace}/outreach").json() if m["status"] == "draft")
    assert (answer["thread_id"], answer["recipient_address"]) == ("c1", "u9")
