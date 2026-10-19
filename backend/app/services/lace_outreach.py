"""A Lace's outreach: the drafts it writes and what becomes of them. The Lace
only drafts; changing or deleting is the founder's, while still a draft."""

import asyncio
import re
import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import exists, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.database.lace_models import LaceAccount, LaceChannel, LaceOutreach
from backend.app.services import connections as connection_service
from backend.app.services import lace_channels
from backend.app.services import outreach as outreach_service
from backend.app.services.errors import ConflictError, InvalidInputError, NotFoundError
from utils.log import logger
from backend.app.services.lace_accounts import BY_FIT

_X_LOOKUP = "TWITTER_USER_LOOKUP_BY_USERNAME"  # verified against the live Composio catalog
_X_SEND = "TWITTER_SEND_A_NEW_MESSAGE_TO_A_USER"
_X_PROFILE = re.compile(r"^https?://(www\.)?(x|twitter)\.com/(?P<handle>[A-Za-z0-9_]{1,15})/?$", re.I)
# Answering in an existing conversation on a linked account, inside Meta's
# reply window (docs/lace-plan.md, Channels): (account id, recipient, text) -> (tool, arguments).
_DM_SEND = {
    "instagram": lambda account, recipient, text: (
        "INSTAGRAM_SEND_TEXT_MESSAGE", {"ig_user_id": account, "recipient_id": recipient, "text": text}),
    "facebook": lambda account, recipient, text: (
        "FACEBOOK_SEND_MESSAGE", {"page_id": account, "recipient_id": recipient, "message_text": text,
                                  "messaging_type": "RESPONSE"}),
}
# How Meta reports a message outside its window: Instagram's error subcode
# 2534022 (per the action's docs), Facebook's 2018278, or the words themselves.
_WINDOW_MARKERS = ("2534022", "2018278", "outside of allowed window", "messaging window", "24 hour")

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


async def drafts(db: AsyncSession, lace_id: uuid.UUID, limit: int) -> list[LaceOutreach]:
    """Outbound messages waiting for the founder to send, newest first."""
    return list((await db.scalars(select(LaceOutreach).where(
        LaceOutreach.lace_id == lace_id, LaceOutreach.direction == "outbound", LaceOutreach.status == "draft",
    ).order_by(LaceOutreach.created_at.desc()).limit(limit))).all())


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
    if message.channel in _DM_SEND and message.thread_id:
        channel = await db.scalar(select(LaceChannel).where(
            LaceChannel.lace_id == message.lace_id, LaceChannel.platform == message.channel))
        if channel is not None:
            return await _answer_dm(db, message, channel)
    raise ConflictError(_HANDOFF[message.channel])


async def _answer_dm(db: AsyncSession, message: LaceOutreach, channel: LaceChannel) -> LaceOutreach:
    """Answer someone who messaged the founder's linked account, in that
    conversation. Meta allows it only inside its reply window."""
    if message.direction != "outbound" or message.status not in _EDITABLE_STATUSES:
        raise ConflictError("This message was already sent.")
    if not message.recipient_address or not (message.body or "").strip():
        raise InvalidInputError("Write a message before sending.")
    connection = await lace_channels.live_connection(db, message.user_id, channel.platform)

    # Claim the message before the network call, so a double click can't send twice.
    message.status, message.error = "sending", None
    await db.commit()
    tool, arguments = _DM_SEND[message.channel](channel.account_id, message.recipient_address, message.body)
    label = lace_channels.LABELS[message.channel]
    try:
        result = await asyncio.to_thread(connection_service.execute_tool, message.user_id, tool, arguments,
                                         connection.id)
        error = str(result.get("error") or "")
        message.provider_log_id = result.get("log_id")
        if error:
            message.status = "failed"
            message.error = (f"This conversation is outside {label}'s reply window: answer on {label} directly, "
                             f"then mark it sent." if _outside_window(error)
                             else f"{label} refused the message. Try again, or answer on {label} directly.")
        else:
            message.provider_message_id = _response_field(result.get("data"), "message_id")
            message.status, message.sent_at = "sent", datetime.now(UTC)
    except Exception:  # noqa: BLE001 -- an expected outcome: recorded on the message
        logger.exception("%s answer failed for message %s", label, message.id)
        message.status, message.error = "failed", f"Couldn't reach {label}. Please try again."
    finally:
        await db.commit()
        await db.refresh(message)
    return message


def _outside_window(error: str) -> bool:
    return any(marker in error.lower() for marker in _WINDOW_MARKERS)


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
        user = _response_field(found.get("data"), "id")
        if found.get("error") or not user:
            message.status, message.error = "failed", f"Couldn't find @{handle.group('handle')} on X."
        else:
            result = await asyncio.to_thread(connection_service.execute_tool, message.user_id, _X_SEND,
                                             {"participant_id": user, "text": message.body}, x.id)
            failed = bool(result.get("error"))
            message.provider_log_id = result.get("log_id")
            message.provider_message_id = _response_field(result.get("data"), "dm_event_id")
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


def _response_field(data, field: str) -> str | None:
    """A field of a platform API response, which Composio may or may not wrap in `data`."""
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
    the answer as a draft in its thread, on its channel, to whoever wrote.
    Returns the draft."""
    reply.intent = intent
    if intent == "unsubscribe" and reply.account_id and (account := await db.get(LaceAccount, reply.account_id)):
        account.do_not_contact = True
    draft = None
    if draft_body:
        draft = LaceOutreach(lace_id=reply.lace_id, user_id=reply.user_id, account_id=reply.account_id, run_id=run_id,
                             channel=reply.channel, recipient_name=reply.recipient_name,
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


# Reply intents that count as a lead warming up.
_INTERESTED = ("interested", "meeting_request")


async def funnel(db: AsyncSession, lace_id: uuid.UUID) -> dict[str, int]:
    """How far the Lace's target accounts have come: on file, written to,
    replied, and interested (keen, or asking to meet). Distinct accounts."""
    def accounts_where(*conditions):
        return select(func.count(func.distinct(LaceOutreach.account_id))).where(
            LaceOutreach.lace_id == lace_id, LaceOutreach.account_id.is_not(None), *conditions)

    targets = await db.scalar(select(func.count()).select_from(LaceAccount).where(
        LaceAccount.lace_id == lace_id, LaceAccount.status == "target"))
    contacted = await db.scalar(accounts_where(LaceOutreach.direction == "outbound", LaceOutreach.status == "sent"))
    replied = await db.scalar(accounts_where(LaceOutreach.direction == "inbound"))
    interested = await db.scalar(accounts_where(LaceOutreach.direction == "inbound",
                                                LaceOutreach.intent.in_(_INTERESTED)))
    return {"accounts": targets or 0, "contacted": contacted or 0, "replied": replied or 0,
            "interested": interested or 0}
