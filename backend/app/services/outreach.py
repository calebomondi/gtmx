"""Sending outreach on the founder's behalf, shared by every send path: the
email send through the mailbox the Lace uses (Gmail or Outlook, its own or
the founder's), the daily send cap, and the name messages are signed with."""

import asyncio
import functools
import re
import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app import supabase_admin
from backend.app.database import models
from backend.app.database.lace_models import Lace
from backend.app.services import connections as connection_service
from backend.app.services import lace_app_settings, outlook
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
    """Messages sent for the user in the last day, by email or X, from a
    workspace or a Lace: the daily cap is the user's, wherever they send from."""
    since = datetime.now(UTC) - timedelta(days=1)
    total = 0
    for model in (models.OutreachMessage, models.LaceOutreach):
        total += int(await db.scalar(select(func.count()).select_from(model).where(
            model.user_id == user_id, model.status == "sent", model.channel.in_(_SENT_BY_US),
            model.sent_at >= since,
        )) or 0)
    return total


def ensure_under_daily_cap(sent: int) -> None:
    if sent >= settings.max_outreach_sends_per_day:
        raise RateLimitedError(
            f"You've reached today's limit of {settings.max_outreach_sends_per_day} sent messages.",
            retry_after_s=3600,
        )


# The mail apps a Lace sends email through, in the order it picks them.
EMAIL_APPS = ("gmail", "outlook")


async def email_account(db: AsyncSession, lace: Lace) -> connection_service.ConnectionInfo | None:
    """The mailbox `lace` sends email from: its Gmail, else its Outlook (each
    its own or the founder's shared one), if switched on for it."""
    uses = await connection_service.for_lace(db, lace)
    for platform in EMAIL_APPS:
        account = uses.get(platform)
        if account is not None and account.status == "live" and await lace_app_settings.enabled(db, lace, platform):
            return account
    return None


async def send_email(db: AsyncSession, message: models.LaceOutreach, lace: Lace):
    """Send one approved outbound email from the mailbox `lace` uses. Only
    ever called on the user's explicit action."""
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
    mailbox = await email_account(db, lace)
    if mailbox is None:
        raise ConflictError("Connect Gmail or Outlook (this Lace's settings) to send email.")
    if mailbox.platform == "outlook":
        answering, subject = await _outlook_thread(db, message)
        send = functools.partial(_send_outlook, mailbox, message, answering, subject)
    else:
        send = functools.partial(_send_gmail, mailbox, message)
    label = connection_service.label(mailbox.platform)

    # Claim the message before the network call, so a double click can't send twice.
    message.status, message.error = "sending", None
    await db.commit()
    try:
        sent = await asyncio.to_thread(send)
        failed = bool(sent["error"])
        message.provider_log_id = sent["log_id"]
        message.thread_id = message.thread_id or sent["thread_id"]
        message.provider_message_id = sent["message_id"]
        message.status = "failed" if failed else "sent"
        message.error = f"{label} rejected the message. Check the recipient address and try again." if failed else None
        message.sent_at = None if failed else datetime.now(UTC)
    except Exception:  # noqa: BLE001 -- an expected outcome: recorded on the message
        logger.exception("Outreach send failed for message %s", message.id)
        message.status = "failed"
        message.error = f"Couldn't reach {label}. Please try again."
    finally:
        await db.commit()
        await db.refresh(message)
    return message


def _send_gmail(gmail: connection_service.ConnectionInfo, message: models.LaceOutreach) -> dict:
    # A draft in an existing thread is a reply: it goes into that thread.
    tool, arguments = (_REPLY_TOOL, {
        "thread_id": message.thread_id, "recipient_email": message.recipient_address,
        "message_body": message.body,
    }) if message.thread_id else (_SEND_TOOL, {
        "recipient_email": message.recipient_address, "subject": message.subject, "body": message.body,
    })
    result = connection_service.execute_tool(gmail.entity, tool, arguments, gmail.id)
    sent = result.get("data") if isinstance(result.get("data"), dict) else {}
    return {"error": result.get("error"), "log_id": result.get("log_id"),
            "thread_id": sent.get("threadId"), "message_id": sent.get("id")}


async def _outlook_thread(db: AsyncSession, message: models.LaceOutreach) -> tuple[str | None, str]:
    """For an Outlook draft in a conversation: the latest message received in
    it (answered in place), and the subject a new email in it would carry
    when nothing was received yet."""
    if not message.thread_id:
        return None, message.subject or ""
    o = models.LaceOutreach
    in_thread = (o.lace_id == message.lace_id, o.thread_id == message.thread_id)
    answering = await db.scalar(select(o.provider_message_id).where(
        *in_thread, o.direction == "inbound", o.provider_message_id.is_not(None)).order_by(o.sent_at.desc()).limit(1))
    first = await db.scalar(select(o.subject).where(*in_thread, o.subject.is_not(None)).order_by(o.created_at).limit(1))
    return answering, message.subject or (f"Re: {first}" if first else "")


def _send_outlook(outlook_account: connection_service.ConnectionInfo, message: models.LaceOutreach,
                  answering: str | None, subject: str) -> dict:
    if answering:
        replied = outlook.reply(outlook_account, answering, message.body)
        return {**replied, "thread_id": None, "message_id": None}
    return outlook.send(outlook_account, message.recipient_address, subject, message.body)


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
