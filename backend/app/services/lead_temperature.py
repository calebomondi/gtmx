"""A lead's temperature (cold, warm, hot, customer): set here, in code, from
what the lead did, never by the model. Each signal is kept
(lace_account_signals), so the badge always has a reason. The rules are the
lead-temperature playbook's (agents/prompts/playbooks/lead-temperature.md).

- A reply moves it by its intent (REPLY_SIGNALS); "not now" also snoozes it.
- A meeting on the founder's calendar with someone there makes it hot.
- The founder can mark it a customer, or take that back.
- An opt-out is recorded; do_not_contact itself is set where the reply is read.
- Quiet leads cool (cool_quiet_leads): hot to warm, warm to cold.

`temperature_changed_at` is the lead's last activity: a signal at or below
its temperature refreshes it, so an engaged lead doesn't cool.
"""

import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from agents.schemas.lace import LeadTemperature, TemperatureSignal
from backend.app.database.lace_models import LaceAccount, LaceAccountSignal, LaceContact
from config import settings

_RANK: dict[str, int] = {"cold": 0, "warm": 1, "hot": 2, "customer": 3}

# Reply intent -> (the temperature it means, the reason shown). Intents not
# here (out of office, other) change nothing; unsubscribe is an opt-out.
REPLY_SIGNALS: dict[str, tuple[LeadTemperature, str]] = {
    "meeting_request": ("hot", "Asked for a meeting"),
    "interested": ("warm", "Replied with interest"),
    "question": ("warm", "Replied with a question"),
    "objection": ("warm", "Replied with an objection"),
    "referral": ("warm", "Pointed you to someone else"),
    "not_now": ("warm", "Said not now"),
}


def _keep(db: AsyncSession, account: LaceAccount, kind: TemperatureSignal, detail: str, before: str,
          now: datetime, outreach_id: uuid.UUID | None) -> None:
    db.add(LaceAccountSignal(lace_id=account.lace_id, account_id=account.id, kind=kind, detail=detail,
                             outreach_id=outreach_id, before=before, after=account.temperature, at=now))


async def _signal(db: AsyncSession, account: LaceAccount, kind: TemperatureSignal, detail: str,
                  to: LeadTemperature, now: datetime, outreach_id: uuid.UUID | None = None) -> None:
    """Something the lead did: `to` at or above its temperature moves it there
    with this reason; below, it still counts as activity (a warm reply keeps a
    hot lead hot, and refreshes it)."""
    before = account.temperature
    if _RANK[to] >= _RANK[before]:
        account.temperature, account.temperature_reason = to, detail
    account.temperature_changed_at = now
    _keep(db, account, kind, detail, before, now, outreach_id)


def _move(db: AsyncSession, account: LaceAccount, kind: TemperatureSignal, detail: str, to: LeadTemperature,
          now: datetime) -> None:
    """Set the temperature outright, down as well as up: cooling, or the
    founder taking back "customer"."""
    before = account.temperature
    account.temperature, account.temperature_reason, account.temperature_changed_at = to, detail, now
    _keep(db, account, kind, detail, before, now, None)


async def on_reply(db: AsyncSession, account: LaceAccount, intent: str, outreach_id: uuid.UUID,
                   now: datetime | None = None) -> None:
    """A reply from someone at the lead, read as `intent`. The caller commits."""
    now = now or datetime.now(UTC)
    if intent == "unsubscribe":
        await _signal(db, account, "opt_out", "Asked not to be contacted", account.temperature, now, outreach_id)
        return
    if intent not in REPLY_SIGNALS:
        return
    to, reason = REPLY_SIGNALS[intent]
    await _signal(db, account, "reply", reason, to, now, outreach_id)
    if intent == "not_now":
        account.snoozed_until = now + timedelta(days=settings.lead_snooze_days)


async def on_meeting(db: AsyncSession, lace_id: uuid.UUID, attendees: list[str], title: str,
                     now: datetime | None = None) -> list[LaceAccount]:
    """A meeting the founder approved on their calendar: every lead with one of
    its guests on file is hot. Returns them. The caller commits."""
    emails = {e.strip().lower() for e in attendees if e and "@" in e}
    if not emails:
        return []
    now = now or datetime.now(UTC)
    accounts = (await db.scalars(select(LaceAccount).join(LaceContact, LaceContact.account_id == LaceAccount.id).where(
        LaceAccount.lace_id == lace_id, LaceContact.email.in_(emails)).distinct())).all()
    for account in accounts:
        await _signal(db, account, "meeting", f"Meeting booked: {title}"[:200], "hot", now)
    return list(accounts)



async def on_crm(db: AsyncSession, account: LaceAccount, crm_status: str, stage: str | None,
                 now: datetime | None = None) -> None:
    """Where the founder's CRM says the lead stands: a customer there is a
    customer here, and an open deal is at least warm. A lead or a record only
    on file says nothing about warmth. The caller commits."""
    now = now or datetime.now(UTC)
    if crm_status == "customer" and account.temperature != "customer":
        await _signal(db, account, "crm", "A customer in your CRM", "customer", now)
    elif crm_status == "open_deal" and account.temperature == "cold":
        detail = f"Open deal in your CRM ({stage})" if stage else "Open deal in your CRM"
        await _signal(db, account, "crm", detail[:200], "warm", now)

async def set_customer(db: AsyncSession, account: LaceAccount, is_customer: bool,
                       now: datetime | None = None) -> None:
    """The founder says the lead bought, or takes that back (it goes back to
    cold until it engages again). The caller commits."""
    now = now or datetime.now(UTC)
    if is_customer:
        await _signal(db, account, "customer", "Marked as a customer", "customer", now)
    elif account.temperature == "customer":
        _move(db, account, "customer", "No longer marked as a customer", "cold", now)


async def cool_quiet_leads(db: AsyncSession, now: datetime | None = None) -> int:
    """Leads quiet for the cooling period drop one step: hot to warm, warm to
    cold. Customers never cool, and a snoozed lead waits out its snooze.
    Returns how many cooled. The caller commits."""
    now = now or datetime.now(UTC)
    quiet_since = now - timedelta(days=settings.lead_cooling_days)
    rows = (await db.scalars(select(LaceAccount).where(
        LaceAccount.temperature.in_(("warm", "hot")), LaceAccount.temperature_changed_at < quiet_since,
        or_(LaceAccount.snoozed_until.is_(None), LaceAccount.snoozed_until < now)))).all()
    for account in rows:
        to: LeadTemperature = "warm" if account.temperature == "hot" else "cold"
        _move(db, account, "cooled", f"No activity for {settings.lead_cooling_days} days", to, now)
    return len(rows)

