"""A founder's Telegram bot as a Lace's inbox: linked like an Instagram
account, its private chats and the group messages meant for it synced in,
and answers sent back through the bot."""

import psycopg
import pytest
from sqlalchemy import select

from backend.app.database.connect import AsyncSessionLocal
from backend.app.database.lace_models import LaceChannel
from backend.app.services import connections as connection_service
from backend.app.services import social_inbox
from backend.app.services.telegram_inbox import for_the_bot
from backend.tests.helpers import stub_accounts
from backend.tests.test_lace_jobs import lace  # noqa: F401 -- fixture
from backend.tests.test_laces_api import API, lace_runtime  # noqa: F401 -- fixture
from config import settings

BOT = {"id": 777, "is_bot": True, "username": "shanga_bot", "first_name": "Shanga"}


def _msg(update_id, message_id, chat, text, sender="joe", reply_to=None, is_bot=False):
    return {"update_id": update_id, "message": {
        "message_id": message_id, "date": 1761400000, "text": text, "chat": chat,
        "from": {"id": 9, "username": sender, "first_name": sender.title(), "is_bot": is_bot},
        **({"reply_to_message": {"from": reply_to}} if reply_to else {})}}


PRIVATE = {"id": 9, "type": "private"}
GROUP = {"id": -100555, "type": "supergroup", "title": "Farmers Kenya"}


@pytest.fixture
def telegram(monkeypatch):
    """A live Telegram bot: GET_ME, the updates in `box["updates"]`, and sends recorded."""
    box = {"updates": [], "calls": []}

    def execute(entity, tool, arguments, connection_id):
        box["calls"].append((tool, arguments))
        data = {"TELEGRAM_GET_ME": {"ok": True, "result": BOT},
                "TELEGRAM_GET_UPDATES": {"ok": True, "result": box["updates"]},
                "TELEGRAM_SEND_MESSAGE": {"ok": True, "result": {"message_id": 5}}}.get(tool, {})
        return {"data": data, "error": None, "log_id": "l1"}
    stub_accounts(monkeypatch, {"telegram"})
    monkeypatch.setattr(connection_service, "execute_tool", execute)
    return box


@pytest.mark.parametrize("message, kept", [
    ({"chat": PRIVATE, "text": "hi"}, True),
    ({"chat": GROUP, "text": "@Shanga_bot what does it cost?"}, True),
    ({"chat": GROUP, "text": "thanks!", "reply_to_message": {"from": {"username": "shanga_bot"}}}, True),
    ({"chat": GROUP, "text": "anyone selling seeds?"}, False),
])
def test_what_the_bot_keeps_from_a_group(message, kept):
    assert for_the_bot(message, "@shanga_bot") is kept


async def _sync(lace_id):
    async with AsyncSessionLocal() as db:
        channel = await db.scalar(select(LaceChannel).where(LaceChannel.lace_id == lace_id))
        arrived = await social_inbox.sync_channel(db, channel)
        return [(m.recipient_name, m.body, m.thread_id) for m in arrived], channel.sync_cursor


def test_a_linked_bot_brings_its_messages_and_answers_go_back(client, lace, lace_runtime, telegram):  # noqa: F811
    assert client.get(f"{API}/laces/{lace}/channels/available", params={"platform": "telegram"}).json() == [
        {"id": "777", "name": "@shanga_bot"}]
    assert client.post(f"{API}/laces/{lace}/channels", json={"platform": "telegram", "account_id": "777"}).status_code == 201

    telegram["updates"] = [_msg(10, 1, PRIVATE, "Do you deliver to Nakuru?"),
                           _msg(11, 2, GROUP, "@shanga_bot pricing?", sender="ann"),
                           _msg(12, 3, GROUP, "unrelated chatter", sender="bob"),
                           _msg(13, 4, PRIVATE, "/start", sender="spam_bot", is_bot=True)]
    arrived, cursor = client.portal.call(_sync, lace)
    assert arrived == [("Joe", "Do you deliver to Nakuru?", "9"), ("Ann in Farmers Kenya", "@shanga_bot pricing?", "-100555")]
    assert cursor == "13"
    # The next read starts after the last update, and nothing is stored twice.
    again, _ = client.portal.call(_sync, lace)
    assert again == [] and telegram["calls"][-1] == ("TELEGRAM_GET_UPDATES", {
        "limit": 100, "allowed_updates": ["message"], "offset": 14})

    with psycopg.connect(settings.database_url, autocommit=True) as conn:
        user_id = conn.execute("SELECT user_id FROM laces WHERE id = %s", (lace,)).fetchone()[0]
        answer = conn.execute(
            "INSERT INTO lace_outreach (id, lace_id, user_id, channel, recipient_address, body, thread_id)"
            " VALUES (gen_random_uuid(), %s, %s, 'telegram', '9', 'Yes, every Tuesday.', '9') RETURNING id",
            (lace, user_id)).fetchone()[0]
    assert client.post(f"{API}/laces/{lace}/outreach/{answer}/send").json()["status"] == "sent"
    assert telegram["calls"][-1] == ("TELEGRAM_SEND_MESSAGE", {"chat_id": "9", "text": "Yes, every Tuesday."})
