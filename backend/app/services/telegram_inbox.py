"""Messages to a founder's Telegram bot, synced into the linked Lace's
conversations.

Telegram has no conversation list for bots: each read takes the bot's new
updates (after the last one read; Telegram keeps a day of them). A private
chat with the bot is kept whole; in a group, only messages that mention the
bot or reply to it, so a busy group doesn't flood the Lace. Each kept message
is an inbound "received" row in its chat's thread; bot commands (/start)
are left out. Read only: syncing sends nothing. Composio tool verified against the live catalog (2026-10-25)."""

import asyncio
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.database.lace_models import LaceChannel, LaceOutreach
from backend.app.services import connections as connection_service
from backend.app.services.connections import ConnectionInfo
from utils.log import logger

UPDATES_PER_SYNC = 100
_BODY_CHARS = 20_000
_PRIVATE = "private"


def _updates(connection: ConnectionInfo, after: str | None) -> list[dict]:
    arguments = {"limit": UPDATES_PER_SYNC, "allowed_updates": ["message"],
                 **({"offset": int(after) + 1} if after else {})}
    result = connection_service.execute_tool(connection.entity, "TELEGRAM_GET_UPDATES", arguments, connection.id)
    if result.get("error"):
        logger.info("Telegram updates for %s failed: %s", connection.entity, result["error"])
        return []
    data = result.get("data")
    rows = data.get("result", data.get("updates")) if isinstance(data, dict) else data
    return [u for u in rows or [] if isinstance(u, dict)]


def for_the_bot(message: dict, bot: str) -> bool:
    """A private message to the bot, or one in a group that mentions it or replies to it."""
    if (message.get("chat") or {}).get("type") == _PRIVATE:
        return True
    text = message.get("text") or ""
    replied = ((message.get("reply_to_message") or {}).get("from") or {}).get("username") or ""
    return bot.lower() in text.lower() or f"@{replied}".lower() == bot.lower()


def _sender(message: dict) -> str:
    person = message.get("from") or {}
    name = " ".join(filter(None, (person.get("first_name"), person.get("last_name")))) or person.get("username")
    chat = message.get("chat") or {}
    where = f" in {chat.get('title')}" if chat.get("type") != _PRIVATE and chat.get("title") else ""
    return f"{name or 'Someone'}{where}"[:255]


async def sync_bot(db: AsyncSession, channel: LaceChannel, connection: ConnectionInfo) -> list[LaceOutreach]:
    """Store the bot's new messages for this Lace. Returns the new inbound ones."""
    updates = await asyncio.to_thread(_updates, connection, channel.sync_cursor)
    if not updates:
        return []
    known = set((await db.scalars(select(LaceOutreach.provider_message_id).where(
        LaceOutreach.lace_id == channel.lace_id, LaceOutreach.channel == "telegram",
        LaceOutreach.provider_message_id.is_not(None)))).all())
    arrived: list[LaceOutreach] = []
    for update in sorted(updates, key=lambda u: u.get("update_id") or 0):
        message = update.get("message") or {}
        chat_id = (message.get("chat") or {}).get("id")
        text = (message.get("text") or "").strip()
        key = f"{chat_id}:{message.get('message_id')}"
        # A command (/start, sent when someone opens the bot) says nothing to answer.
        if (not text or text.startswith("/") or chat_id is None or key in known
                or (message.get("from") or {}).get("is_bot") or not for_the_bot(message, channel.account_name)):
            continue
        row = LaceOutreach(
            lace_id=channel.lace_id, user_id=channel.user_id, channel="telegram", direction="inbound",
            status="received", thread_id=str(chat_id), provider_message_id=key, recipient_name=_sender(message),
            recipient_address=str(chat_id), recipient_company="", body=text[:_BODY_CHARS],
            sent_at=datetime.fromtimestamp(message.get("date") or 0, UTC) if message.get("date") else datetime.now(UTC),
        )
        db.add(row)
        known.add(key)
        arrived.append(row)
    channel.sync_cursor = str(max(u.get("update_id") or 0 for u in updates))
    channel.synced_until = datetime.now(UTC)
    await db.commit()
    return arrived
