"""The brief's schedule and its digest: what happened for a Lace since its
last brief, assembled from the database, so the Lace writes from facts."""

import uuid
from datetime import UTC, date, datetime, timedelta
from typing import Literal
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.database.lace_models import (
    Lace,
    LaceAccount,
    LaceActivity,
    LaceBrief,
    LaceCompetitor,
    LaceFact,
    LaceOpportunity,
    LaceOutreach,
    LaceRegulation,
)

# Lines per digest section; the rest is summarised as a count.
SECTION_LINES = 5
# Opportunities closing within this many days are flagged as coming up.
CLOSING_SOON_DAYS = 7
# How far back a first brief looks.
FIRST_BRIEF_LOOKBACK = timedelta(days=1)
# A brief that could not be posted within this long is dropped for the next one.
PENDING_MAX_AGE = timedelta(hours=12)
# Shown on the Feed while being written, once written, or never written in time.
BriefState = Literal["writing", "posted", "missed"]


def zone(name: str) -> ZoneInfo:
    try:
        return ZoneInfo(name)
    except (ZoneInfoNotFoundError, ValueError):
        return ZoneInfo("UTC")


def is_due(lace: Lace, now: datetime) -> bool:
    """Due at or after the founder's chosen local hour, once per day (daily)
    or at least seven days apart (weekly)."""
    if lace.brief_frequency == "off" or lace.status != "active":
        return False
    tz = zone(lace.timezone)
    local = now.astimezone(tz)
    if local.hour < lace.brief_hour:
        return False
    if lace.last_brief_at is None:
        return True
    last = lace.last_brief_at.astimezone(tz).date()
    gap = 7 if lace.brief_frequency == "weekly" else 1
    return (local.date() - last).days >= gap


async def due_laces(db: AsyncSession, now: datetime) -> list[Lace]:
    rows = await db.scalars(select(Lace).where(Lace.status == "active", Lace.brief_frequency != "off"))
    return [lace for lace in rows.all() if is_due(lace, now)]


def _section(title: str, lines: list[str], total: int | None = None) -> str:
    if not lines:
        return ""
    more = (total or len(lines)) - len(lines)
    tail = [f"- and {more} more"] if more > 0 else []
    return f"{title}:\n" + "\n".join(f"- {line}" for line in lines) + ("\n" + tail[0] if tail else "")


async def _rows(db: AsyncSession, query, limit: int = SECTION_LINES) -> tuple[list, int]:
    total = int(await db.scalar(select(func.count()).select_from(query.subquery())) or 0)
    return list((await db.scalars(query.limit(limit))).all()), total


async def digest(db: AsyncSession, lace_id: uuid.UUID, since: datetime, today: date) -> str:
    """What happened since `since`, and what is waiting on the founder. Empty
    when there is nothing to tell."""
    moves, n_moves = await _rows(db, select(LaceFact).where(
        LaceFact.lace_id == lace_id, LaceFact.origin == "monitor", LaceFact.recorded_at >= since,
        LaceFact.superseded_by_id.is_(None)).order_by(LaceFact.recorded_at.desc()))
    rivals, n_rivals = await _rows(db, select(LaceCompetitor).where(
        LaceCompetitor.lace_id == lace_id, LaceCompetitor.team(), LaceCompetitor.status != "dismissed",
        LaceCompetitor.first_seen_at >= since).order_by(LaceCompetitor.first_seen_at.desc()))
    accounts, n_accounts = await _rows(db, select(LaceAccount).where(
        LaceAccount.lace_id == lace_id, LaceAccount.team(), LaceAccount.status != "dismissed",
        LaceAccount.first_seen_at >= since).order_by(LaceAccount.first_seen_at.desc()))
    reached, n_reached = await _rows(db, select(LaceAccount).where(
        LaceAccount.lace_id == lace_id, LaceAccount.team(), LaceAccount.contact_status == "person",
        LaceAccount.contacts_checked_at >= since))
    replies, n_replies = await _rows(db, select(LaceOutreach).where(
        LaceOutreach.lace_id == lace_id, LaceOutreach.direction == "inbound", LaceOutreach.status == "received",
        LaceOutreach.sent_at >= since).order_by(LaceOutreach.sent_at.desc()))
    drafts, n_drafts = await _rows(db, select(LaceOutreach).where(
        LaceOutreach.lace_id == lace_id, LaceOutreach.direction == "outbound", LaceOutreach.status == "draft",
    ).order_by(LaceOutreach.created_at.desc()))
    new_opps, n_new_opps = await _rows(db, select(LaceOpportunity).where(
        LaceOpportunity.lace_id == lace_id, LaceOpportunity.team(), LaceOpportunity.status != "dismissed",
        LaceOpportunity.first_seen_at >= since).order_by(LaceOpportunity.first_seen_at.desc()))
    closing, n_closing = await _rows(db, select(LaceOpportunity).where(
        LaceOpportunity.lace_id == lace_id, LaceOpportunity.team(), LaceOpportunity.status != "dismissed",
        LaceOpportunity.deadline >= today, LaceOpportunity.deadline <= today + timedelta(days=CLOSING_SOON_DAYS),
    ).order_by(LaceOpportunity.deadline))
    bills, n_bills = await _rows(db, select(LaceActivity).where(
        LaceActivity.lace_id == lace_id, LaceActivity.kind == "bill_moved", LaceActivity.created_at >= since,
    ).order_by(LaceActivity.created_at.desc()))
    new_rules, n_new_rules = await _rows(db, select(LaceRegulation).where(
        LaceRegulation.lace_id == lace_id, LaceRegulation.team(), LaceRegulation.status != "dismissed",
        LaceRegulation.first_seen_at >= since).order_by(LaceRegulation.first_seen_at.desc()))
    due, n_due = await _rows(db, select(LaceRegulation).where(
        LaceRegulation.lace_id == lace_id, LaceRegulation.team(), LaceRegulation.status == "tracked",
        LaceRegulation.next_date >= today, LaceRegulation.next_date <= today + timedelta(days=CLOSING_SOON_DAYS),
    ).order_by(LaceRegulation.next_date))

    sections = [
        _section("Competitor moves", [m.claim + (f" ({m.source_url})" if m.source_url else "") for m in moves], n_moves),
        _section("New competitors found", [f"{c.name} ({c.website})" for c in rivals], n_rivals),
        _section("New leads", [a.name + (f", {a.geo}" if a.geo else "") for a in accounts], n_accounts),
        _section("Named contacts found at", [a.name for a in reached], n_reached),
        _section("Replies that came in", [f"{r.recipient_name or r.recipient_address} ({r.recipient_company or r.channel})"
                                          + (f": {r.intent}" if r.intent else "") for r in replies], n_replies),
        _section("Drafts waiting for the founder to review and send",
                 [f"{d.recipient_company or d.recipient_name or d.recipient_address} by {d.channel}" for d in drafts],
                 n_drafts),
        _section("New opportunities", [f"[{o.kind}] {o.title} ({o.url})" for o in new_opps], n_new_opps),
        _section("Opportunities closing within a week",
                 [f"{o.title}: closes {o.deadline.isoformat()} ({o.url})" for o in closing], n_closing),
        _section("Tracked bills that moved", [b.title for b in bills], n_bills),
        _section("New laws and regulations that apply", [f"[{r.kind}, {r.jurisdiction}] {r.title} ({r.url})"
                                                         for r in new_rules], n_new_rules),
        _section("Compliance dates within a week", [f"{r.title}: {r.next_date.isoformat()} ({r.what_to_do})"
                                                    for r in due], n_due),
    ]
    waiting = await suggestion_counts(db, lace_id)
    if any(waiting.values()):
        sections.append("Suggestions waiting for the founder to save or dismiss: "
                        + ", ".join(f"{n} {kind}" for kind, n in waiting.items() if n))
    return "\n\n".join(s for s in sections if s)


async def suggestion_counts(db: AsyncSession, lace_id: uuid.UUID) -> dict[str, int]:
    """How many of each kind of suggestion wait for the founder."""
    counts = {}
    for kind, model in (("competitors", LaceCompetitor), ("accounts", LaceAccount), ("opportunities", LaceOpportunity)):
        counts[kind] = int(await db.scalar(select(func.count()).select_from(model).where(
            model.lace_id == lace_id, model.team(), model.status == "suggested")) or 0)
    return counts


def since_for(lace: Lace, now: datetime) -> datetime:
    return lace.last_brief_at or now - FIRST_BRIEF_LOOKBACK


async def unposted(db: AsyncSession, lace_id: uuid.UUID) -> LaceBrief | None:
    return await db.scalar(select(LaceBrief).where(LaceBrief.lace_id == lace_id, LaceBrief.posted_at.is_(None))
                           .order_by(LaceBrief.created_at.desc()).limit(1))


async def latest(db: AsyncSession, lace_id: uuid.UUID) -> LaceBrief | None:
    return await db.scalar(select(LaceBrief).where(LaceBrief.lace_id == lace_id)
                           .order_by(LaceBrief.created_at.desc()).limit(1))


def state(brief: LaceBrief, now: datetime) -> BriefState:
    if brief.posted_at is not None:
        return "posted"
    return "missed" if brief.created_at < now - PENDING_MAX_AGE else "writing"


async def mark_posted(db: AsyncSession, brief_id: uuid.UUID, body: str) -> None:
    brief = await db.get(LaceBrief, brief_id)
    if brief is not None:
        brief.body, brief.posted_at = body, datetime.now(UTC)
