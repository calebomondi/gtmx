"""Inbound DMs to a founder's linked Instagram business account or Facebook
Page, synced into the owning Lace's outreach threads.

One conversation list per linked account per sync, then the messages of the
conversations updated since the last one. A message from the other person is
an inbound "received" row; the business's own messages are stored as sent, so
the Lace reads the whole conversation. Read only: syncing never sends or marks
anything on the platform.

Meta lets an app answer only people who wrote first, so a first touch is sent
by the founder by hand and marked sent. When that person answers, their
conversation is joined to it (by Instagram username against the handle in the
profile URL, else by name): the hand-sent message takes the conversation's
thread, the new rows carry its account and company, and the founder's own
message, synced back, isn't stored twice. The Lace then reads the whole
exchange and drafts the answers.
"""

import asyncio
import re
import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.database.lace_models import Lace, LaceChannel, LaceOutreach
from backend.app.services import connections as connection_service
from backend.app.services import telegram_inbox
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


def _fetch(channel: LaceChannel, connection: connection_service.ConnectionInfo, tool: str,
           arguments: dict) -> list[dict]:
    result = connection_service.execute_tool(connection.entity, tool, arguments, connection.id)
    if result.get("error"):
        logger.info("%s for %s %s failed: %s", tool, channel.platform, channel.account_id, result["error"])
        return []
    return items(result.get("data"))


# The handle in a profile URL the founder messaged: instagram.com/<handle>.
_HANDLE = re.compile(r"(?:instagram|facebook)\.com/([A-Za-z0-9_.]+)", re.I)


async def _started_by_hand(db: AsyncSession, channel: LaceChannel) -> list[LaceOutreach]:
    """First touches the founder sent by hand on this channel, not yet joined
    to a conversation."""
    return list((await db.scalars(select(LaceOutreach).where(
        LaceOutreach.lace_id == channel.lace_id, LaceOutreach.channel == channel.platform,
        LaceOutreach.direction == "outbound", LaceOutreach.status == "sent", LaceOutreach.thread_id.is_(None),
    ))).all())


def _started_with(person: dict, started: list[LaceOutreach]) -> LaceOutreach | None:
    """The hand-sent first touch to this person: their username is the handle
    the founder messaged, else their name is the one it was addressed to."""
    username = (person.get("username") or "").lower()
    name = (person.get("name") or "").strip().lower()
    for row in started:
        handle = _HANDLE.search(row.recipient_address or "")
        if username and handle and handle.group(1).lower() == username:
            return row
    named = [row for row in started if name and (row.recipient_name or "").strip().lower() == name]
    return named[0] if len(named) == 1 else None


async def _opener(db: AsyncSession, channel: LaceChannel, thread: str) -> LaceOutreach | None:
    """The conversation's first message from the founder on file, if any:
    what new messages in it take their account and company from."""
    return await db.scalar(select(LaceOutreach).where(
        LaceOutreach.lace_id == channel.lace_id, LaceOutreach.channel == channel.platform,
        LaceOutreach.thread_id == thread, LaceOutreach.direction == "outbound",
    ).order_by(LaceOutreach.created_at).limit(1))


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
    lace = await db.get(Lace, channel.lace_id)
    try:
        connection = await live_connection(db, lace, channel.platform)
    except ConflictError:
        return []  # disconnected since it was linked: nothing to read until reconnected
    if channel.platform == "telegram":
        return await telegram_inbox.sync_bot(db, channel, connection)
    since = channel.synced_until or datetime.now(UTC) - timedelta(days=settings.inbox_sync_window_days)
    tool, arguments = _CONVERSATIONS[channel.platform]
    conversations = await asyncio.to_thread(_fetch, channel, connection, tool, arguments(channel))
    fresh = [c for c in conversations if c.get("id") and timestamp(c.get("updated_time")) > since]
    if not fresh:
        return []
    known = set((await db.scalars(select(LaceOutreach.provider_message_id).where(
        LaceOutreach.lace_id == channel.lace_id, LaceOutreach.channel == channel.platform,
        LaceOutreach.provider_message_id.is_not(None)))).all())
    started = await _started_by_hand(db, channel)

    arrived: list[LaceOutreach] = []
    newest = since
    for conversation in fresh:
        thread = str(conversation["id"])[:255]
        opener = await _opener(db, channel, thread)
        tool, arguments = _MESSAGES[channel.platform]
        messages = await asyncio.to_thread(_fetch, channel, connection, tool, arguments(channel, conversation["id"]))
        for message in sorted(messages, key=lambda m: timestamp(m.get("created_time"))):
            text = (message.get("message") or "").strip()
            if not message.get("id") or message["id"] in known or not text:
                continue
            inbound = _person(message.get("from")).get("id") != channel.account_id
            other = _other_party(message, channel.account_id)
            sent_at = timestamp(message.get("created_time"))
            if opener is None and (first := _started_with(other, started)) is not None:
                # Their conversation is the one the founder started by hand.
                first.thread_id = thread
                started.remove(first)
                opener = first
            if not inbound and opener is not None and opener.provider_message_id is None and opener.body.strip() == text:
                # The founder's hand-sent message, synced back: already on file.
                opener.provider_message_id = str(message["id"])[:255]
                known.add(message["id"])
                continue
            row = LaceOutreach(
                lace_id=channel.lace_id, user_id=channel.user_id, channel=channel.platform,
                direction="inbound" if inbound else "outbound", status="received" if inbound else "sent",
                thread_id=thread, provider_message_id=str(message["id"])[:255],
                account_id=opener.account_id if opener else None,
                recipient_company=opener.recipient_company if opener else "",
                recipient_name=(opener.recipient_name if opener else None)
                or (other.get("username") or other.get("name") or "")[:255] or None,
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
