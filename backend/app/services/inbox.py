"""Replies and bounces for sent outreach, synced from the user's Gmail.

One mailbox search per user per sync (recent mail not from the user), matched
to the threads of emails sent from GTMX. A reply becomes an inbound message
in that thread; a delivery-failure notice marks the sent email bounced. Read
only: syncing never sends, labels or deletes anything in the mailbox.
"""

import asyncio
import re
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.database import models
from backend.app.services import connections as connection_service
from config import settings
from utils.log import logger

_FETCH_TOOL = "GMAIL_FETCH_EMAILS"  # verified against the live Composio catalog
_PAGE_SIZE = 100
_MAX_PAGES = 3
_BODY_CHARS = 20_000
_BOUNCE_SENDERS = ("mailer-daemon", "postmaster")
_BOUNCE_SUBJECTS = re.compile(r"delivery status notification|undeliverable|delivery failure|returned mail|failure notice", re.I)
_ADDRESS_RE = re.compile(r"<?([^<>\s]+@[^<>\s]+)>?\s*$")


@dataclass
class SyncResult:
    replies: list[models.OutreachMessage] = field(default_factory=list)
    bounced: list[models.OutreachMessage] = field(default_factory=list)


def _address(sender: str) -> str:
    match = _ADDRESS_RE.search(sender or "")
    return (match.group(1) if match else sender or "").strip().lower()


def _display_name(sender: str) -> str | None:
    name = (sender or "").split("<")[0].strip().strip('"')
    return name or None


def _timestamp(raw) -> datetime:
    try:
        return datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
    except ValueError:
        return datetime.now(UTC)


def is_bounce(message: dict) -> bool:
    sender = _address(message.get("sender") or "")
    return sender.split("@")[0] in _BOUNCE_SENDERS or bool(_BOUNCE_SUBJECTS.search(message.get("subject") or ""))


def _fetch_recent(user_id: uuid.UUID, connection_id: str, days: int) -> list[dict]:
    """Recent mail not sent by the user, newest first, bounded."""
    messages: list[dict] = []
    page_token = None
    for _ in range(_MAX_PAGES):
        arguments = {"query": f"newer_than:{days}d -from:me", "max_results": _PAGE_SIZE, "include_payload": False}
        if page_token:
            arguments["page_token"] = page_token
        result = connection_service.execute_tool(user_id, _FETCH_TOOL, arguments, connection_id)
        if result["error"] or not isinstance(result["data"], dict):
            logger.info("Gmail fetch for user %s failed: %s", user_id, result["error"])
            break
        messages.extend(result["data"].get("messages") or [])
        page_token = result["data"].get("nextPageToken")
        if not page_token:
            break
    return messages


async def _sent_threads(db: AsyncSession, user_id: uuid.UUID, since: datetime) -> dict[str, models.OutreachMessage]:
    """thread_id -> the latest email the user sent in it, within the window."""
    rows = (await db.execute(
        select(models.OutreachMessage).where(
            models.OutreachMessage.user_id == user_id,
            models.OutreachMessage.channel == "email",
            models.OutreachMessage.direction == "outbound",
            models.OutreachMessage.thread_id.is_not(None),
            models.OutreachMessage.sent_at >= since,
        ).order_by(models.OutreachMessage.sent_at)
    )).scalars().all()
    return {row.thread_id: row for row in rows}


def _text(message: dict) -> str:
    for key in ("messageText", "preview"):
        value = message.get(key)
        if isinstance(value, str) and value.strip():
            return value
        if isinstance(value, dict) and isinstance(value.get("body"), str):
            return value["body"]
    return ""


def _inbound(sent: models.OutreachMessage, message: dict, status: str) -> models.OutreachMessage:
    sender = message.get("sender") or ""
    return models.OutreachMessage(
        workspace_id=sent.workspace_id, user_id=sent.user_id, account_id=sent.account_id,
        channel="email", direction="inbound", status=status, thread_id=sent.thread_id,
        provider_message_id=message.get("messageId"),
        recipient_name=_display_name(sender) or sent.recipient_name,
        recipient_company=sent.recipient_company, recipient_address=_address(sender) or None,
        subject=(message.get("subject") or "")[:255] or None,
        body=_text(message)[:_BODY_CHARS],
        sent_at=_timestamp(message.get("messageTimestamp")),
    )


def _bounced_send(message: dict, threads: dict[str, models.OutreachMessage]) -> models.OutreachMessage | None:
    """The sent email a bounce notice is about: same thread, or the bounce
    text names its recipient."""
    if message.get("threadId") in threads:
        return threads[message["threadId"]]
    text = _text(message).lower()
    return next((s for s in threads.values() if s.recipient_address and s.recipient_address.lower() in text), None)


async def sync_user(db: AsyncSession, user_id: uuid.UUID) -> SyncResult:
    """Store new replies and bounces for the user's recent sends."""
    result = SyncResult()
    since = datetime.now(UTC) - timedelta(days=settings.inbox_sync_window_days)
    threads = await _sent_threads(db, user_id, since)
    if not threads:
        return result
    gmail = next((c for c in await connection_service.list_for_user(db, user_id)
                  if c.platform == "gmail" and c.status == "live"), None)
    if gmail is None:
        return result

    fetched = await asyncio.to_thread(_fetch_recent, user_id, gmail.id, settings.inbox_sync_window_days)
    known = set((await db.execute(
        select(models.OutreachMessage.provider_message_id).where(
            models.OutreachMessage.user_id == user_id, models.OutreachMessage.provider_message_id.is_not(None),
        )
    )).scalars())
    for message in fetched:
        if not message.get("messageId") or message["messageId"] in known:
            continue
        if is_bounce(message):
            sent = _bounced_send(message, threads)
            if sent is None:
                continue
            sent.status, sent.error = "bounced", "This address bounced: the email was not delivered."
            db.add(_inbound(sent, message, "bounced"))
            result.bounced.append(sent)
        elif message.get("threadId") in threads:
            reply = _inbound(threads[message["threadId"]], message, "received")
            db.add(reply)
            result.replies.append(reply)
        known.add(message["messageId"])
    try:
        await db.commit()
    except IntegrityError:  # a concurrent sync stored the same messages first
        await db.rollback()
        return SyncResult()
    return result


async def users_to_sync(db: AsyncSession) -> list[uuid.UUID]:
    """Users with an email sent from GTMX inside the sync window."""
    since = datetime.now(UTC) - timedelta(days=settings.inbox_sync_window_days)
    return list((await db.execute(
        select(models.OutreachMessage.user_id).where(
            models.OutreachMessage.direction == "outbound",
            models.OutreachMessage.thread_id.is_not(None),
            models.OutreachMessage.sent_at >= since,
        ).distinct()
    )).scalars())
