"""Inbound DMs to a founder's linked Instagram business account or Facebook
Page, synced into the owning Lace's outreach threads.

One conversation list per linked account per sync, then the messages of the
conversations updated since the last one. A message from the other person is
an inbound "received" row; the business's own messages are stored as sent, so
the Lace reads the whole conversation. Read only: syncing never sends or marks
anything on the platform.
"""

import asyncio
import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.database.lace_models import LaceChannel, LaceOutreach
from backend.app.services import connections as connection_service
from backend.app.services.errors import ConflictError
from backend.app.services.inbox import timestamp
from backend.app.services.lace_channels import items, live_connection
from config import settings
from utils.log import logger

CONVERSATIONS_PER_SYNC = 25
MESSAGES_PER_CONVERSATION = 25
_BODY_CHARS = 20_000
_FIELDS = "id,created_time,from,to,message"

# Verified against the live Composio catalog (docs/lace-plan.md, Channels).
_CONVERSATIONS = {
    "instagram": ("INSTAGRAM_LIST_ALL_CONVERSATIONS",
                  lambda ch: {"platform": "instagram", "ig_user_id": ch.account_id, "limit": CONVERSATIONS_PER_SYNC,
                              "fields": "id,updated_time"}),
    "facebook": ("FACEBOOK_GET_PAGE_CONVERSATIONS",
                 lambda ch: {"page_id": ch.account_id, "limit": CONVERSATIONS_PER_SYNC, "fields": "id,updated_time"}),
}
_MESSAGES = {
    "instagram": ("INSTAGRAM_LIST_ALL_MESSAGES",
                  lambda ch, conv: {"conversation_id": conv, "limit": MESSAGES_PER_CONVERSATION, "fields": _FIELDS}),
    "facebook": ("FACEBOOK_GET_CONVERSATION_MESSAGES",
                 lambda ch, conv: {"page_id": ch.account_id, "conversation_id": conv,
                                   "limit": MESSAGES_PER_CONVERSATION, "fields": _FIELDS}),
}


def _fetch(channel: LaceChannel, connection_id: str, tool: str, arguments: dict) -> list[dict]:
    result = connection_service.execute_tool(channel.user_id, tool, arguments, connection_id)
    if result.get("error"):
        logger.info("%s for %s %s failed: %s", tool, channel.platform, channel.account_id, result["error"])
        return []
    return items(result.get("data"))


def _person(value) -> dict:
    return value if isinstance(value, dict) else {}


def _other_party(message: dict, account_id: str) -> dict:
    """Whoever the message is with: its sender, or for our own message its first recipient."""
    sender = _person(message.get("from"))
    if sender.get("id") != account_id:
        return sender
    recipients = items(message.get("to")) or [_person(message.get("to"))]
    return recipients[0] if recipients else {}


async def sync_channel(db: AsyncSession, channel: LaceChannel) -> list[LaceOutreach]:
    """Store new messages from the account's recent conversations. Returns the
    new inbound ones."""
    try:
        connection = await live_connection(db, channel.user_id, channel.platform)
    except ConflictError:
        return []  # disconnected since it was linked: nothing to read until reconnected
    since = channel.synced_until or datetime.now(UTC) - timedelta(days=settings.inbox_sync_window_days)
    tool, arguments = _CONVERSATIONS[channel.platform]
    conversations = await asyncio.to_thread(_fetch, channel, connection.id, tool, arguments(channel))
    fresh = [c for c in conversations if c.get("id") and timestamp(c.get("updated_time")) > since]
    if not fresh:
        return []
    known = set((await db.scalars(select(LaceOutreach.provider_message_id).where(
        LaceOutreach.lace_id == channel.lace_id, LaceOutreach.channel == channel.platform,
        LaceOutreach.provider_message_id.is_not(None)))).all())

    arrived: list[LaceOutreach] = []
    newest = since
    for conversation in fresh:
        tool, arguments = _MESSAGES[channel.platform]
        messages = await asyncio.to_thread(_fetch, channel, connection.id, tool, arguments(channel, conversation["id"]))
        for message in sorted(messages, key=lambda m: timestamp(m.get("created_time"))):
            text = (message.get("message") or "").strip()
            if not message.get("id") or message["id"] in known or not text:
                continue
            inbound = _person(message.get("from")).get("id") != channel.account_id
            other = _other_party(message, channel.account_id)
            sent_at = timestamp(message.get("created_time"))
            row = LaceOutreach(
                lace_id=channel.lace_id, user_id=channel.user_id, channel=channel.platform,
                direction="inbound" if inbound else "outbound", status="received" if inbound else "sent",
                thread_id=str(conversation["id"])[:64], provider_message_id=str(message["id"])[:128],
                recipient_name=(other.get("username") or other.get("name") or "")[:255] or None,
                recipient_address=str(other.get("id") or "") or None, body=text[:_BODY_CHARS], sent_at=sent_at,
            )
            db.add(row)
            known.add(message["id"])
            newest = max(newest, sent_at)
            if inbound:
                arrived.append(row)
        newest = max(newest, timestamp(conversation.get("updated_time")))
    channel.synced_until = newest
    await db.commit()
    return arrived


async def sync_all(db: AsyncSession) -> dict[uuid.UUID, tuple[uuid.UUID, int]]:
    """Sync every linked account. Returns {lace_id: (user_id, new inbound)}
    for the Laces that received something."""
    received: dict[uuid.UUID, tuple[uuid.UUID, int]] = {}
    for channel in list((await db.scalars(select(LaceChannel))).all()):
        try:
            arrived = await sync_channel(db, channel)
        except Exception:  # noqa: BLE001 -- one account failing must not stop the rest
            logger.exception("Syncing %s %s failed", channel.platform, channel.account_id)
            await db.rollback()
            continue
        if arrived:
            user_id, count = received.get(channel.lace_id, (channel.user_id, 0))
            received[channel.lace_id] = (user_id, count + len(arrived))
    return received
