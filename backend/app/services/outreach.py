"""Outreach messages: agent drafts, user edits, and sends that happen only on
the user's explicit action, through their own connected Gmail."""

import asyncio
import re
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app import supabase_admin
from backend.app.database import models
from backend.app.services import calendar as calendar_service
from backend.app.services import connections as connection_service
from backend.app.services.errors import ConflictError, InvalidInputError, NotFoundError, RateLimitedError
from config import settings
from utils.log import logger

CHANNELS = ("email", "linkedin")
# The connected-account platform each channel goes out through.
CHANNEL_PLATFORM = {"email": "gmail", "linkedin": "linkedin"}
_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
_EDITABLE = ("draft", "failed")
_SEND_TOOL = "GMAIL_SEND_EMAIL"  # verified against the live Composio catalog
_REPLY_TOOL = "GMAIL_REPLY_TO_THREAD"


async def list_for_workspace(db: AsyncSession, workspace_id: uuid.UUID) -> list[models.OutreachMessage]:
    return list((await db.execute(
        select(models.OutreachMessage)
        .where(models.OutreachMessage.workspace_id == workspace_id)
        .order_by(models.OutreachMessage.updated_at.desc())
        .limit(500)
    )).scalars().all())


async def get_in_workspace(db: AsyncSession, workspace_id: uuid.UUID, message_id: uuid.UUID) -> models.OutreachMessage:
    message = await db.scalar(select(models.OutreachMessage).where(
        models.OutreachMessage.id == message_id, models.OutreachMessage.workspace_id == workspace_id,
    ))
    if message is None:
        raise NotFoundError("Message not found")
    return message


async def accounts_for_drafting(db: AsyncSession, workspace_id: uuid.UUID, account_ids: list[uuid.UUID]) -> list[models.Account]:
    rows = list((await db.execute(select(models.Account).where(
        models.Account.workspace_id == workspace_id, models.Account.id.in_(account_ids),
    ))).scalars().all())
    if not rows:
        raise InvalidInputError("Pick at least one target account to draft for.")
    return rows


# Inboxes that must never receive cold outreach: wrong audience, and mailing
# them damages the sender's domain reputation.
_BLOCKED_INBOXES = re.compile(
    r"^(legal|support|help|privacy|security|abuse|noreply|no-reply|donotreply|accommodations?|"
    r"careers?|jobs|recruiting|hr|press|media|billing|accounts?|invoices?|compliance|dpo|gdpr|"
    r"postmaster|webmaster|admin|info-?jp)@",
    re.IGNORECASE,
)
# Shared inboxes that are acceptable when no named person is known.
_GENERAL_INBOXES = re.compile(r"^(hello|hi|hey|sales|team|founders?|partnerships?|contact|info)@", re.IGNORECASE)


def recipient_for(account: models.Account, channel: str) -> tuple[str | None, str | None]:
    """(name, address) of the best contact found by account discovery: a named
    person first, then a general sales/hello inbox, never a legal/support-style
    role inbox. Only sourced details -- an address is never guessed."""
    contacts = [c for c in (account.key_contacts or []) if isinstance(c, dict)]
    first_named = next((c.get("name") for c in contacts if c.get("name")), None)
    if channel != "email":
        return first_named, None
    best, best_rank = (None, None), 0
    for contact in contacts:
        email = (contact.get("email") or "").strip()
        if not _EMAIL_RE.match(email) or _BLOCKED_INBOXES.match(email):
            continue
        rank = 3 if contact.get("name") else 2 if not _GENERAL_INBOXES.match(email) else 1
        if rank > best_rank:
            best, best_rank = (contact.get("name") or first_named, email), rank
    return best if best_rank else (first_named, None)


async def mark_read(db: AsyncSession, message: models.OutreachMessage) -> models.OutreachMessage:
    if message.direction == "inbound" and message.read_at is None:
        message.read_at = datetime.now(UTC)
        await db.commit()
        await db.refresh(message)
    return message


async def update(db: AsyncSession, message: models.OutreachMessage, changes: dict[str, Any]) -> models.OutreachMessage:
    if message.status not in _EDITABLE:
        raise ConflictError("A sent message can't be edited.")
    for field in ("subject", "body", "recipient_address", "recipient_name"):
        if field in changes:
            setattr(message, field, changes[field])
    if not (message.body or "").strip():
        raise InvalidInputError("The message body can't be empty.")
    await db.commit()
    await db.refresh(message)
    return message


async def delete(db: AsyncSession, message: models.OutreachMessage) -> None:
    if message.status == "sending":
        raise ConflictError("This message is being sent.")
    await db.delete(message)
    await db.commit()


async def _sends_today(db: AsyncSession, user_id: uuid.UUID) -> int:
    return int(await db.scalar(select(func.count()).select_from(models.OutreachMessage).where(
        models.OutreachMessage.user_id == user_id,
        models.OutreachMessage.status == "sent",
        models.OutreachMessage.sent_at >= datetime.now(UTC) - timedelta(days=1),
    )) or 0)


async def send(db: AsyncSession, message: models.OutreachMessage) -> models.OutreachMessage:
    """Send one approved email through the user's connected Gmail."""
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
    if await _sends_today(db, message.user_id) >= settings.max_outreach_sends_per_day:
        raise RateLimitedError(
            f"You've reached today's limit of {settings.max_outreach_sends_per_day} sent emails.",
            retry_after_s=3600,
        )
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


def _lines(label: str, values) -> str:
    values = [v for v in (values or []) if v]
    return f"{label}: " + "; ".join(str(v) for v in values) if values else ""


async def offer_context(db: AsyncSession, workspace_id: uuid.UUID) -> str:
    """The offer and the ICP's messaging, for the drafting agent."""
    insights = await db.scalar(
        select(models.ProductProfile.insights).where(models.ProductProfile.workspace_id == workspace_id)
    ) or {}
    offer, icp = insights.get("offer_snapshot") or {}, insights.get("icp") or {}
    parts = [
        f"Offer: {offer.get('offer_name') or ''} -- {offer.get('offer_description') or ''}",
        f"Problem it solves: {offer.get('problem_solved') or 'n/a'}",
        _lines("Messaging angles", icp.get("messaging_angles")),
        _lines("Buyer pain signals", icp.get("pain_signals")),
        _lines("Buyer titles", icp.get("buyer_titles")),
    ]
    return "\n".join(p for p in parts if p)


def contact_title(account: models.Account, name: str | None) -> str | None:
    return next((c.get("title") for c in account.key_contacts or []
                 if isinstance(c, dict) and name and c.get("name") == name), None)


def account_brief(account: models.Account) -> str:
    """Everything account discovery found about the account, for the GTM specialist."""
    trigger = account.trigger_event or {}
    parts = [
        f"Account: {account.name} ({account.account_type}; {account.website or 'no website'})",
        f"What they do: {account.summary}" if account.summary else "",
        f"Industry: {account.industry or 'n/a'}; size: {account.size or 'n/a'}; geo: {account.geo or 'n/a'}",
        f"Trigger event: {trigger.get('event')} (source: {trigger.get('source')})" if trigger.get("event") else "",
        _lines("Why it fits our ICP", account.why_selected),
        _lines("Angles to reach out now", account.why_reach_out),
        _lines("Pain signals", account.pain_signals),
        _lines("Hiring signals", account.hiring_signals),
        _lines("Recent news", (account.recent_news or [])[:4]),
        _lines("Tech stack", account.tech_stack),
        _lines("Sources", [s.get("url") for s in (account.sources or [])[:5] if isinstance(s, dict)]),
    ]
    return "\n".join(p for p in parts if p)


def sender_name(name: str | None, email: str | None) -> str:
    """The name outreach is signed with: the profile name, else the email's local part."""
    if name and name.strip():
        return name.strip()
    local = (email or "").split("@")[0].replace(".", " ").replace("_", " ")
    return local.title() or "Me"


async def sender_for_user(user_id: uuid.UUID) -> str:
    """The sender name for a user, outside a request (e.g. a scheduled sync)."""
    try:
        client = await supabase_admin.get_client()
        user = (await client.auth.admin.get_user_by_id(str(user_id))).user
    except Exception:  # noqa: BLE001 -- signing falls back; drafting must not fail on it
        logger.exception("Looking up user %s for the sender name failed", user_id)
        return "Me"
    metadata = getattr(user, "user_metadata", None) or {}
    return sender_name(metadata.get("full_name") or metadata.get("name"), getattr(user, "email", None))


async def thread(db: AsyncSession, message: models.OutreachMessage) -> list[models.OutreachMessage]:
    """The message's conversation, oldest first."""
    if not message.thread_id:
        return [message]
    return list((await db.execute(
        select(models.OutreachMessage).where(
            models.OutreachMessage.user_id == message.user_id,
            models.OutreachMessage.thread_id == message.thread_id,
        ).order_by(func.coalesce(models.OutreachMessage.sent_at, models.OutreachMessage.created_at))
    )).scalars().all())


async def add_reply_draft(db: AsyncSession, reply: models.OutreachMessage, body: str,
                          meeting: dict | None, run_id: uuid.UUID | None) -> models.OutreachMessage:
    """A draft answering `reply`, in its thread, to whoever wrote it."""
    draft = models.OutreachMessage(
        workspace_id=reply.workspace_id, user_id=reply.user_id, account_id=reply.account_id, run_id=run_id,
        channel=reply.channel, recipient_name=reply.recipient_name, recipient_company=reply.recipient_company,
        recipient_address=reply.recipient_address, body=body, thread_id=reply.thread_id, meeting=meeting,
    )
    db.add(draft)
    await db.commit()
    return draft


async def add_meeting(db: AsyncSession, message: models.OutreachMessage) -> models.OutreachMessage:
    """Put the meeting a reply draft proposes into the user's Google Calendar.
    Only ever from the user's click."""
    if not message.meeting:
        raise ConflictError("This message has no meeting to add.")
    if message.meeting.get("event_url"):
        return message
    url = await calendar_service.add_meeting(db, message.user_id, message.meeting)
    message.meeting = {**message.meeting, "event_url": url or "added"}
    await db.commit()
    await db.refresh(message)
    return message
