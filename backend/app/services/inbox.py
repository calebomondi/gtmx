"""Replies and bounces for sent outreach, synced from the user's Gmail.

One mailbox search per user per sync (recent mail not from the user), matched
to the threads of emails a Lace sent. A reply
becomes an inbound message in that thread, in the same table as the email it
answers; a delivery-failure notice marks the sent email bounced. Read only:
syncing never sends, labels or deletes anything in the mailbox.
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
# Where a reply's own words end and the mail it answers begins: Gmail's
# "On <date>, <name> wrote:" (often wrapped over two lines), Outlook's
# "-----Original Message-----" or "From: ... Sent: ..." header, or a run of
# "> " quoted lines. Mirrored in migration 20261022_1200_strip_quotes_from_email_replies.
_QUOTE_STARTS = (
    re.compile(r"^[ \t]*On\b[^\n]{0,300}(?:\n[^\n]{0,300})?\bwrote:[ \t]*$", re.M),
    re.compile(r"^[ \t]*-{2,}[ \t]*Original Message[ \t]*-{2,}", re.M | re.I),
    re.compile(r"^[ \t]*From:[^\n]*\n[ \t]*(?:Sent|Date):", re.M),
    re.compile(r"^[ \t]*>", re.M),
)


# Sent outreach the sync watches. v1 workspace outreach is no longer synced.
_OUTREACH = (models.LaceOutreach,)
Outreach = models.LaceOutreach


@dataclass
class SyncResult:
    replies: list[Outreach] = field(default_factory=list)
    bounced: list[Outreach] = field(default_factory=list)


def _address(sender: str) -> str:
    match = _ADDRESS_RE.search(sender or "")
    return (match.group(1) if match else sender or "").strip().lower()


def _display_name(sender: str) -> str | None:
    name = (sender or "").split("<")[0].strip().strip('"')
    return name or None


def timestamp(raw) -> datetime:
    """A provider's timestamp as an aware UTC datetime; now when unreadable."""
    try:
        parsed = datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
    except ValueError:
        return datetime.now(UTC)
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)


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


def check_minutes() -> int:
    """How often replies to sent messages are looked for; 0 when never."""
    return round(settings.inbox_sync_interval_s / 60) if settings.inbox_sync_enabled else 0


async def _sent_threads(db: AsyncSession, user_id: uuid.UUID, since: datetime) -> dict[str, Outreach]:
    """thread_id -> the latest email the user sent in it, within the window."""
    threads: dict[str, Outreach] = {}
    for model in _OUTREACH:
        rows = (await db.execute(
            select(model).where(
                model.user_id == user_id, model.channel == "email", model.direction == "outbound",
                model.thread_id.is_not(None), model.sent_at >= since,
            ).order_by(model.sent_at)
        )).scalars().all()
        threads.update((row.thread_id, row) for row in rows)
    return threads


def reply_only(text: str) -> str:
    """The reply without the earlier mail it quotes. A message that is
    nothing but a quote is kept whole, so no reply ever reads as empty."""
    cut = min((m.start() for pattern in _QUOTE_STARTS if (m := pattern.search(text))), default=len(text))
    return text[:cut].rstrip() or text.strip()


def _text(message: dict) -> str:
    for key in ("messageText", "preview"):
        value = message.get(key)
        if isinstance(value, str) and value.strip():
            return value
        if isinstance(value, dict) and isinstance(value.get("body"), str):
            return value["body"]
    return ""


def _inbound(sent: Outreach, message: dict, status: str) -> Outreach:
    """The received message, in the same table as the email it answers."""
    sender = message.get("sender") or ""
    return type(sent)(
        lace_id=sent.lace_id, user_id=sent.user_id, account_id=sent.account_id,
        channel="email", direction="inbound", status=status, thread_id=sent.thread_id,
        provider_message_id=message.get("messageId"),
        recipient_name=_display_name(sender) or sent.recipient_name,
        recipient_company=sent.recipient_company, recipient_address=_address(sender) or None,
        subject=(message.get("subject") or "")[:255] or None,
        body=reply_only(_text(message))[:_BODY_CHARS],
        sent_at=timestamp(message.get("messageTimestamp")),
    )


def _bounced_send(message: dict, threads: dict[str, Outreach]) -> Outreach | None:
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
    known: set[str] = set()
    for model in _OUTREACH:
        known |= set((await db.execute(select(model.provider_message_id).where(
            model.user_id == user_id, model.provider_message_id.is_not(None),
        ))).scalars())
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
    """Users with an email a Lace sent inside the sync window."""
    since = datetime.now(UTC) - timedelta(days=settings.inbox_sync_window_days)
    users: set[uuid.UUID] = set()
    for model in _OUTREACH:
        users |= set((await db.execute(select(model.user_id).where(
            model.direction == "outbound", model.thread_id.is_not(None), model.sent_at >= since,
        ).distinct())).scalars())
    return sorted(users)
