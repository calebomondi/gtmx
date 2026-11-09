"""Follow-ups to first emails nobody answered (agents/prompts/playbooks/
follow-up.md): when one is due, and when the sequence stops.

- A first email sent in a thread with no reply in it gets a follow-up due
  FOLLOW_UP_FIRST_AFTER_DAYS later; that follow-up, once sent, gets the second
  one due FOLLOW_UP_SECOND_AFTER_DAYS later. Two at most.
- Drafting one clears the due date of the email it follows, so a follow-up the
  founder discards is not drafted again.
- The sequence stops at a reply, a bounce, an opt-out, a meeting or a sale (hot
  or customer), a lead the founder dropped, a later email in the thread, or a
  draft already waiting there. "Not now" waits until its date.

Each follow-up is a draft: the founder sends it.
"""

import uuid
from datetime import datetime, timedelta

from sqlalchemy import exists, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.database.lace_models import Lace, LaceAccount, LaceOutreach
from config import settings

LAST_STEP = 2


def _wait(step: int) -> timedelta:
    """How long after the email at `step` its follow-up is due."""
    days = settings.follow_up_first_after_days if step == 0 else settings.follow_up_second_after_days
    return timedelta(days=days)


async def schedule(db: AsyncSession, message: LaceOutreach) -> None:
    """Just sent: give a first email (or its first follow-up) a due date for
    the next follow-up, unless someone already wrote back in its thread. The
    caller commits."""
    if (message.channel != "email" or message.direction != "outbound" or message.status != "sent"
            or message.sent_at is None or message.sequence_step >= LAST_STEP or not message.thread_id):
        return
    answered = await db.scalar(select(exists().where(
        LaceOutreach.lace_id == message.lace_id, LaceOutreach.thread_id == message.thread_id,
        LaceOutreach.direction == "inbound")))
    if not answered:
        message.follow_up_due_at = message.sent_at + _wait(message.sequence_step)


async def laces_due(db: AsyncSession, now: datetime, limit: int) -> list[tuple[uuid.UUID, uuid.UUID]]:
    """(lace_id, owner user_id) of active Laces with a follow-up due, bounded."""
    rows = await db.execute(select(Lace.id, Lace.user_id).where(
        Lace.status == "active",
        exists().where(LaceOutreach.lace_id == Lace.id, LaceOutreach.follow_up_due_at <= now),
    ).limit(limit))
    return [(lace_id, user_id) for lace_id, user_id in rows.all()]


async def due(db: AsyncSession, lace_id: uuid.UUID, now: datetime, limit: int) -> list[LaceOutreach]:
    """The Lace's sent emails whose follow-up is due, the longest-waiting first."""
    return list((await db.scalars(select(LaceOutreach).where(
        LaceOutreach.lace_id == lace_id, LaceOutreach.follow_up_due_at <= now,
    ).order_by(LaceOutreach.follow_up_due_at).limit(limit))).all())


async def stop_reason(db: AsyncSession, message: LaceOutreach, account: LaceAccount | None) -> str | None:
    """Why this email gets no follow-up, or None when it should get one."""
    if message.status != "sent":
        return "it didn't go out (it bounced or failed)"
    if account is not None:
        if account.do_not_contact:
            return "they asked not to be contacted"
        if account.status == "dismissed":
            return "the founder dropped the lead"
        if account.temperature in ("hot", "customer"):
            return f"the lead is {account.temperature}"
    thread = list((await db.scalars(select(LaceOutreach).where(
        LaceOutreach.lace_id == message.lace_id, LaceOutreach.thread_id == message.thread_id,
        LaceOutreach.id != message.id))).all())
    if any(m.direction == "inbound" for m in thread):
        return "they replied"
    if any(m.direction == "outbound" and m.status not in ("sent", "failed") for m in thread):
        return "a draft is already waiting in the thread"
    if any(m.direction == "outbound" and m.sent_at and m.sent_at > message.sent_at for m in thread):
        return "a later email went in the thread"
    return None


def snoozed_until(account: LaceAccount | None, now: datetime) -> datetime | None:
    """When a lead that said "not now" may hear from the founder again."""
    if account is not None and account.snoozed_until and account.snoozed_until > now:
        return account.snoozed_until
    return None


async def earlier_bodies(db: AsyncSession, message: LaceOutreach) -> list[str]:
    """The founder's sent emails in the thread, oldest first, for the writer."""
    return list((await db.scalars(select(LaceOutreach.body).where(
        LaceOutreach.lace_id == message.lace_id, LaceOutreach.thread_id == message.thread_id,
        LaceOutreach.direction == "outbound", LaceOutreach.status == "sent",
    ).order_by(LaceOutreach.sent_at))).all())


def follow_up_draft(message: LaceOutreach, body: str, run_id: uuid.UUID) -> LaceOutreach:
    """The follow-up, as a draft in the same thread, mailbox and recipient,
    one step further on."""
    return LaceOutreach(id=uuid.uuid4(), lace_id=message.lace_id, user_id=message.user_id,
                        account_id=message.account_id, run_id=run_id, channel="email",
                        thread_id=message.thread_id, mailbox=message.mailbox, recipient_name=message.recipient_name,
                        recipient_company=message.recipient_company, recipient_address=message.recipient_address,
                        subject=message.subject, body=body, sequence_step=message.sequence_step + 1)
