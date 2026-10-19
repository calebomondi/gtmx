"""Sending outreach on the founder's behalf, shared by every send path: the
email send through their own connected Gmail, the daily send cap, and the
name messages are signed with."""

import asyncio
import re
import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app import supabase_admin
from backend.app.database.lace_models import LaceOutreach
from backend.app.services import connections as connection_service
from backend.app.services.errors import ConflictError, InvalidInputError, RateLimitedError
from config import settings
from utils.log import logger

CHANNELS = ("email", "linkedin")
# The connected-account platform each channel goes out through.
CHANNEL_PLATFORM = {"email": "gmail", "linkedin": "linkedin"}
_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
_EDITABLE = ("draft", "failed")
_SEND_TOOL = "GMAIL_SEND_EMAIL"  # verified against the live Composio catalog
_REPLY_TOOL = "GMAIL_REPLY_TO_THREAD"


# Channels that send through the user's own accounts, under one daily cap.
_SENT_BY_US = ("email", "x")


async def sends_today(db: AsyncSession, user_id: uuid.UUID) -> int:
    """Messages sent for the user in the last day, by email or X, across all
    their Laces: the daily cap is the user's, wherever they send from."""
    since = datetime.now(UTC) - timedelta(days=1)
    o = LaceOutreach
    return int(await db.scalar(select(func.count()).select_from(o).where(
        o.user_id == user_id, o.status == "sent", o.channel.in_(_SENT_BY_US), o.sent_at >= since,
    )) or 0)


def ensure_under_daily_cap(sent: int) -> None:
    if sent >= settings.max_outreach_sends_per_day:
        raise RateLimitedError(
            f"You've reached today's limit of {settings.max_outreach_sends_per_day} sent messages.",
            retry_after_s=3600,
        )


async def send_email(db: AsyncSession, message):
    """Send one approved outbound email (a LaceOutreach) through the user's
    own connected Gmail. Only ever called on the user's explicit action."""
    if message.channel != "email":
        raise ConflictError("LinkedIn messages are sent by you: copy the draft into LinkedIn.")
    if message.direction != "outbound":
        raise ConflictError("Replies you received can't be sent.")
    if message.status not in _EDITABLE:
        raise ConflictError("This message was already sent.")
    if not _EMAIL_RE.match(message.recipient_address or ""):
        raise InvalidInputError("Add a valid recipient email address before sending.")
    if not (message.body or "").strip() or not (message.thread_id or (message.subject or "").strip()):
        raise InvalidInputError("Add a subject and a message before sending.")
    ensure_under_daily_cap(await sends_today(db, message.user_id))
    gmail = next((c for c in await connection_service.list_for_user(db, message.user_id)
                  if c.platform == "gmail" and c.status == "live"), None)
    if gmail is None:
        raise ConflictError("Connect your Gmail account (Accounts page) to send email.")

    # Claim the message before the network call, so a double click can't send twice.
    message.status, message.error = "sending", None
    await db.commit()
    try:
        # A draft in an existing thread is a reply: it goes into that thread.
        tool, arguments = (_REPLY_TOOL, {
            "thread_id": message.thread_id, "recipient_email": message.recipient_address,
            "message_body": message.body,
        }) if message.thread_id else (_SEND_TOOL, {
            "recipient_email": message.recipient_address, "subject": message.subject, "body": message.body,
        })
        result = await asyncio.to_thread(connection_service.execute_tool, message.user_id, tool, arguments, gmail.id)
        failed = bool(result.get("error"))
        message.provider_log_id = result.get("log_id")
        sent = result.get("data") if isinstance(result.get("data"), dict) else {}
        message.thread_id = message.thread_id or sent.get("threadId")
        message.provider_message_id = sent.get("id")
        message.status = "failed" if failed else "sent"
        message.error = "Gmail rejected the message. Check the recipient address and try again." if failed else None
        message.sent_at = None if failed else datetime.now(UTC)
    except Exception:  # noqa: BLE001 -- an expected outcome: recorded on the message
        logger.exception("Outreach send failed for message %s", message.id)
        message.status = "failed"
        message.error = "Couldn't reach Gmail. Please try again."
    finally:
        await db.commit()
        await db.refresh(message)
    return message


_OFFER_CAPABILITIES = 6  # features the drafting agent can tie a payoff to


def sender_name(name: str | None, email: str | None) -> str:
    """The name outreach is signed with: the profile name, else the email's local part."""
    if name and name.strip():
        return name.strip()
    local = (email or "").split("@")[0].replace(".", " ").replace("_", " ")
    return local.title() or "Me"


async def sender_for_user(user_id: uuid.UUID) -> str:
    """The sender name for a user, outside a request (e.g. a scheduled sync)."""
    try:
        user = await supabase_admin.get_user(user_id)
    except Exception:  # noqa: BLE001 -- signing falls back; drafting must not fail on it
        logger.exception("Looking up user %s for the sender name failed", user_id)
        return "Me"
    metadata = getattr(user, "user_metadata", None) or {}
    return sender_name(metadata.get("full_name") or metadata.get("name"), getattr(user, "email", None))
