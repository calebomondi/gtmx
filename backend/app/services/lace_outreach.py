"""A Lace's outreach: the drafts it writes and what becomes of them. The Lace
only drafts; changing or deleting is the founder's, while still a draft."""

import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import exists, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.database.lace_models import LaceAccount, LaceOutreach
from backend.app.services import outreach as outreach_service
from backend.app.services.errors import ConflictError, NotFoundError
from backend.app.services.lace_accounts import BY_FIT

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
    """Send an email draft through the founder's Gmail: only ever on the
    founder's own click, which is their approval."""
    if message.account_id and (account := await db.get(LaceAccount, message.account_id)) and account.do_not_contact:
        raise ConflictError(f"{account.name} asked not to be contacted.")
    return await outreach_service.send_email(db, message)


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
    """Record a LinkedIn message the founder sent by hand."""
    if message.channel != "linkedin":
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
