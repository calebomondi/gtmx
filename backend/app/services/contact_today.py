"""Who the founder should contact today: one ranking, computed in code from
what is on file, most urgent first. Each lead appears once, in its most
urgent group:

1. send_reply: an answer to someone's reply is drafted and waiting.
2. hot: the lead wants to talk (a meeting asked for or booked).
3. warm: the lead engaged within the last few days.
4. send_follow_up: a follow-up is drafted and waiting.
5. first_email: a new lead with a strong fit, a current trigger and someone
   to reach, never written to, and not a customer or open deal in the CRM.

Used by the Lace's who_to_contact_today tool and by the daily brief.
"""

import uuid
from datetime import datetime, timedelta

from sqlalchemy import exists, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from agents.schemas.lace import TodayContact
from backend.app.database.lace_models import LaceAccount, LaceOutreach
from backend.app.services.lace_accounts import BY_FIT
from backend.app.services.lace_outreach import CRM_NO_COLD_EMAIL

# A warm lead counts as fresh this long after it last engaged.
FRESH_WARM = timedelta(days=7)
# Rows read per group: more than the list ever shows.
GROUP_READ = 20


def _who(message: LaceOutreach) -> str:
    return message.recipient_company or message.recipient_name or message.recipient_address or "someone"


async def today(db: AsyncSession, lace_id: uuid.UUID, now: datetime, limit: int) -> list[TodayContact]:
    """The founder's contacts for today, most urgent first, each lead once."""
    found: list[TodayContact] = []
    seen: set[str] = set()

    def add(key: str, item: TodayContact) -> None:
        if key not in seen:
            seen.add(key)
            found.append(item)

    drafts = (await db.scalars(select(LaceOutreach).where(
        LaceOutreach.lace_id == lace_id, LaceOutreach.direction == "outbound", LaceOutreach.status == "draft",
        LaceOutreach.thread_id.is_not(None)).order_by(LaceOutreach.created_at).limit(GROUP_READ))).all()
    threads_with_replies = set((await db.scalars(select(LaceOutreach.thread_id).where(
        LaceOutreach.lace_id == lace_id, LaceOutreach.direction == "inbound",
        LaceOutreach.thread_id.in_([d.thread_id for d in drafts])))).all()) if drafts else set()
    for d in drafts:
        if d.thread_id in threads_with_replies:
            add(str(d.account_id or d.id), TodayContact(
                account_id=str(d.account_id) if d.account_id else None, name=_who(d), action="send_reply",
                why=f"They replied; your answer to {d.recipient_name or _who(d)} is drafted: review and send it."))

    leads = select(LaceAccount).where(LaceAccount.lace_id == lace_id, LaceAccount.team(),
                                      LaceAccount.status == "target", LaceAccount.do_not_contact.is_(False))
    for a in (await db.scalars(leads.where(LaceAccount.temperature == "hot").order_by(
            LaceAccount.temperature_changed_at.desc().nulls_last()).limit(GROUP_READ))).all():
        add(str(a.id), TodayContact(account_id=str(a.id), name=a.name, action="hot",
                                    why=f"Hot: {a.temperature_reason or 'wants to talk'}. Confirm or book the meeting."))
    for a in (await db.scalars(leads.where(
            LaceAccount.temperature == "warm", LaceAccount.temperature_changed_at >= now - FRESH_WARM,
            or_(LaceAccount.snoozed_until.is_(None), LaceAccount.snoozed_until <= now)).order_by(
            LaceAccount.temperature_changed_at.desc()).limit(GROUP_READ))).all():
        add(str(a.id), TodayContact(account_id=str(a.id), name=a.name, action="warm",
                                    why=f"Warm: {a.temperature_reason or 'engaged recently'}. Keep the conversation going."))
    for d in drafts:
        if d.sequence_step > 0 and d.thread_id not in threads_with_replies:
            add(str(d.account_id or d.id), TodayContact(
                account_id=str(d.account_id) if d.account_id else None, name=_who(d), action="send_follow_up",
                why=f"Follow-up {d.sequence_step} to {d.recipient_name or _who(d)} is drafted: review and send it."))

    written = exists().where(LaceOutreach.account_id == LaceAccount.id, LaceOutreach.direction == "outbound")
    for a in (await db.scalars(leads.where(
            LaceAccount.temperature == "cold", LaceAccount.fit_strength == "strong",
            LaceAccount.contact_status == "person", ~written,
            or_(LaceAccount.crm_status.is_(None), LaceAccount.crm_status.not_in(CRM_NO_COLD_EMAIL)),
    ).order_by(BY_FIT, LaceAccount.score.desc().nulls_last()).limit(GROUP_READ))).all():
        trigger = ((a.record or {}).get("trigger_event") or {}).get("event")
        add(str(a.id), TodayContact(account_id=str(a.id), name=a.name, action="first_email",
                                    why="New strong lead" + (f" ({trigger})" if trigger else "")
                                        + ": worth a first email."))
    return found[:limit]
