"""A Lace's outreach: the drafts it writes and what becomes of them. The Lace
only drafts; changing or deleting is the founder's, while still a draft."""

import asyncio
import re
import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import exists, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.database.lace_models import LaceAccount, LaceOutreach
from backend.app.services import connections as connection_service
from backend.app.services import outreach as outreach_service
from backend.app.services.errors import ConflictError, InvalidInputError, NotFoundError
from utils.log import logger
from backend.app.services.lace_accounts import BY_FIT

_X_LOOKUP = "TWITTER_USER_LOOKUP_BY_USERNAME"  # verified against the live Composio catalog
_X_SEND = "TWITTER_SEND_A_NEW_MESSAGE_TO_A_USER"
_X_PROFILE = re.compile(r"^https?://(www\.)?(x|twitter)\.com/(?P<handle>[A-Za-z0-9_]{1,15})/?$", re.I)
# What to do on channels whose APIs cannot start a conversation (docs/lace-plan.md, Channels).
_HANDOFF = {
    "linkedin": "LinkedIn messages are sent by you: copy the message, send it on LinkedIn, then mark it sent.",
    "instagram": "Instagram doesn't let apps start a conversation: copy the message, send it on Instagram, "
                 "then mark it sent.",
    "facebook": "Facebook only lets a Page reply to people who wrote first: copy the message, send it on "
                "Facebook, then mark it sent.",
    "tiktok": "TikTok has no messaging for apps: copy the message, send it on TikTok, then mark it sent.",
}

# What the founder may change on a message that is still theirs to change.
EDITABLE_FIELDS = ("subject", "body", "recipient_address", "recipient_name")
_EDITABLE_STATUSES = ("draft", "failed")


async def list_for_lace(db: AsyncSession, lace_id: uuid.UUID, limit: int) -> list[LaceOutreach]:
    rows = await db.scalars(select(LaceOutreach).where(LaceOutreach.lace_id == lace_id)
                            .order_by(LaceOutreach.created_at.desc()).limit(limit))
    return list(rows.all())


async def get_in_lace(db: AsyncSession, lace_id: uuid.UUID, message_id: uuid.UUID) -> LaceOutreach:
    """404 for a message that is not this Lace's."""
    row = await db.scalar(select(LaceOutreach).where(LaceOutreach.id == message_id, LaceOutreach.lace_id == lace_id))
    if row is None:
        raise NotFoundError("Message not found")
    return row


async def update(db: AsyncSession, message: LaceOutreach, changes: dict[str, Any]) -> LaceOutreach:
    if message.direction != "outbound" or message.status not in _EDITABLE_STATUSES:
        raise ConflictError("Only an unsent draft can be changed.")
    for field in EDITABLE_FIELDS:
        if field in changes:
            setattr(message, field, changes[field])
    await db.commit()
    return message


async def delete(db: AsyncSession, message: LaceOutreach) -> None:
    if message.direction != "outbound" or message.status not in _EDITABLE_STATUSES:
        raise ConflictError("Only an unsent draft can be deleted.")
    await db.delete(message)
    await db.commit()


async def send(db: AsyncSession, message: LaceOutreach) -> LaceOutreach:
    """Send a draft from the founder's own account: only ever on the founder's
    click, which is their approval. Email goes through Gmail and X through X;
    the other channels cannot start a conversation through their APIs, so
    those the founder sends by hand and marks sent."""
    if message.account_id and (account := await db.get(LaceAccount, message.account_id)) and account.do_not_contact:
        raise ConflictError(f"{account.name} asked not to be contacted.")
    if message.channel == "email":
        return await outreach_service.send_email(db, message)
    if message.channel == "x":
        return await _send_x(db, message)
    raise ConflictError(_HANDOFF[message.channel])


async def _send_x(db: AsyncSession, message: LaceOutreach) -> LaceOutreach:
    if message.direction != "outbound" or message.status not in _EDITABLE_STATUSES:
        raise ConflictError("This message was already sent.")
    handle = _X_PROFILE.match(message.recipient_address or "")
    if handle is None:
        raise InvalidInputError("Add the recipient's X profile URL (x.com/handle) before sending.")
    if not (message.body or "").strip():
        raise InvalidInputError("Write a message before sending.")
    outreach_service.ensure_under_daily_cap(await outreach_service.sends_today(db, message.user_id))
    x = next((c for c in await connection_service.list_for_user(db, message.user_id)
              if c.platform == "x" and c.status == "live"), None)
    if x is None:
        raise ConflictError("Connect your X account (Accounts page) to send from here, "
                            "or copy the message, send it on X and mark it sent.")

    # Claim the message before the network calls, so a double click can't send twice.
    message.status, message.error = "sending", None
    await db.commit()
    try:
        found = await asyncio.to_thread(connection_service.execute_tool, message.user_id, _X_LOOKUP,
                                        {"username": handle.group("handle")}, x.id)
        user = _x_field(found.get("data"), "id")
        if found.get("error") or not user:
            message.status, message.error = "failed", f"Couldn't find @{handle.group('handle')} on X."
        else:
            result = await asyncio.to_thread(connection_service.execute_tool, message.user_id, _X_SEND,
                                             {"participant_id": user, "text": message.body}, x.id)
            failed = bool(result.get("error"))
            message.provider_log_id = result.get("log_id")
            message.provider_message_id = _x_field(result.get("data"), "dm_event_id")
            message.status = "failed" if failed else "sent"
            message.error = "X refused the message: they may not accept DMs from you." if failed else None
            message.sent_at = None if failed else datetime.now(UTC)
    except Exception:  # noqa: BLE001 -- an expected outcome: recorded on the message
        logger.exception("X send failed for message %s", message.id)
        message.status, message.error = "failed", "Couldn't reach X. Please try again."
    finally:
        await db.commit()
        await db.refresh(message)
    return message


def _x_field(data, field: str) -> str | None:
    """A field of an X API response, which Composio may or may not wrap in `data`."""
    if not isinstance(data, dict):
        return None
    inner = data.get("data") if isinstance(data.get("data"), dict) else data
    return inner.get(field)


async def unhandled_replies(db: AsyncSession, lace_id: uuid.UUID, limit: int) -> list[LaceOutreach]:
    """Replies that came in and were not read yet, oldest first."""
    return list((await db.scalars(select(LaceOutreach).where(
        LaceOutreach.lace_id == lace_id, LaceOutreach.direction == "inbound", LaceOutreach.status == "received",
        LaceOutreach.intent.is_(None),
    ).order_by(LaceOutreach.sent_at).limit(limit))).all())


async def thread(db: AsyncSession, message: LaceOutreach) -> list[LaceOutreach]:
    """The message's conversation, oldest first."""
    return list((await db.scalars(select(LaceOutreach).where(
        LaceOutreach.lace_id == message.lace_id, LaceOutreach.thread_id == message.thread_id,
    ).order_by(func.coalesce(LaceOutreach.sent_at, LaceOutreach.created_at)))).all())


async def record_reading(db: AsyncSession, reply: LaceOutreach, intent: str, draft_body: str | None,
                         run_id: uuid.UUID) -> LaceOutreach | None:
    """Store how a reply was read, stop all contact when they asked, and add
    the answer as a draft in its thread, to whoever wrote. Returns the draft."""
    reply.intent = intent
    if intent == "unsubscribe" and reply.account_id and (account := await db.get(LaceAccount, reply.account_id)):
        account.do_not_contact = True
    draft = None
    if draft_body:
        draft = LaceOutreach(lace_id=reply.lace_id, user_id=reply.user_id, account_id=reply.account_id, run_id=run_id,
                             channel="email", recipient_name=reply.recipient_name,
                             recipient_company=reply.recipient_company, recipient_address=reply.recipient_address,
                             thread_id=reply.thread_id, body=draft_body)
        db.add(draft)
    return draft


async def mark_sent(db: AsyncSession, message: LaceOutreach) -> LaceOutreach:
    """Record a message the founder sent by hand on its platform."""
    if message.channel == "email":
        raise ConflictError("Emails are sent from here, not marked as sent.")
    if message.direction != "outbound" or message.status not in _EDITABLE_STATUSES:
        raise ConflictError("This message was already sent.")
    message.status, message.sent_at, message.error = "sent", datetime.now(UTC), None
    await db.commit()
    return message


async def accounts_to_draft(db: AsyncSession, lace_id: uuid.UUID, ids: list[uuid.UUID] | None,
                            limit: int) -> list[LaceAccount]:
    """The accounts named, else the strongest-fit targets that nothing was
    written to yet. Whether someone there can be reached is the caller's check."""
    query = select(LaceAccount).where(LaceAccount.lace_id == lace_id, LaceAccount.status == "target")
    if ids:
        query = query.where(LaceAccount.id.in_(ids))
    else:
        written = exists().where(LaceOutreach.account_id == LaceAccount.id, LaceOutreach.direction == "outbound")
        query = query.where(~written, LaceAccount.contact_status.in_(("person", "organisation")))
    query = query.where(LaceAccount.do_not_contact.is_(False))
    return list((await db.scalars(query.order_by(BY_FIT, LaceAccount.score.desc().nulls_last()).limit(limit))).all())
