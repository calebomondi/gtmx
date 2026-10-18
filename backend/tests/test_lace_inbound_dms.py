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
from backend.app.services.connections import ConnectionInfo
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

    async def connections(db, user_id):
        return [ConnectionInfo(f"ca_{p}", p, "live", "me", None, None) for p in sorted(box["live"])]

    def execute(user_id, tool, arguments, connection_id):
        box["calls"].append(tool)
        data = {
            "INSTAGRAM_GET_USER_INFO": {"id": "ig_1", "username": "shangalabs"},
            "FACEBOOK_LIST_MANAGED_PAGES": {"data": [{"id": "pg_1", "name": "Shanga Labs"}]},
            "INSTAGRAM_LIST_ALL_CONVERSATIONS": {"data": [{"id": "c1", "updated_time": NOW.isoformat()}]},
            "INSTAGRAM_LIST_ALL_MESSAGES": {"data": box["messages"]},
        }.get(tool, {"data": []})
        return {"data": data, "error": None, "log_id": "l"}

    monkeypatch.setattr(connection_service, "list_for_user", connections)
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
    other = _create(client, name="Bob").json()["lace"]["id"]
    assert client.post(f"{API}/laces/{other}/channels", json={"platform": "instagram", "account_id": "ig_1"}
                       ).status_code == 409
    channel_id = linked.json()["id"]
    client.sign_in(make_user("Intruder"))
    assert client.get(f"{API}/laces/{lace}/channels").status_code == 404
    assert client.delete(f"{API}/laces/{lace}/channels/{channel_id}").status_code == 404


def test_linking_needs_a_live_connection(client, lace, lace_runtime, meta):  # noqa: F811
    meta["live"] = {"facebook"}
    refused = client.get(f"{API}/laces/{lace}/channels/available?platform=instagram")
    assert refused.status_code == 409 and "Connect your Instagram" in refused.json()["detail"]


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
    meta["live"] = set()
    meta["calls"].clear()
    assert client.portal.call(scheduler.sync_lace_channels) == 0
    assert meta["calls"] == []
