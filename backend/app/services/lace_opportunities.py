"""A Lace's opportunities: what its searches found, one per source page."""

import re
import uuid
from datetime import UTC, date, datetime, timedelta

from sqlalchemy import func, or_, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from agents.schemas.opportunities import Opportunity, OpportunitySummary
from backend.app.database import models
from backend.app.database.lace_models import Lace, LaceOpportunity
from backend.app.services.errors import NotFoundError
from backend.app.services.runs import TERMINAL_STATUSES

_SCHEME = re.compile(r"^https?://(www\.)?", re.I)


def url_key(url: str) -> str:
    return _SCHEME.sub("", url.strip()).rstrip("/").lower()[:1024]


def _date(value: str | None) -> date | None:
    try:
        return date.fromisoformat(value[:10]) if value else None
    except ValueError:
        return None


def summary(row: LaceOpportunity) -> OpportunitySummary:
    return OpportunitySummary(
        id=str(row.id), kind=row.kind, title=row.title, organiser=row.organiser, url=row.url,
        deadline=row.deadline.isoformat() if row.deadline else None,
        date=row.event_date.isoformat() if row.event_date else None, location=row.location,
        why_it_fits=row.why_it_fits, how_to_act=row.how_to_act,
    )


async def list_for_lace(db: AsyncSession, lace_id: uuid.UUID, status: str, limit: int,
                        today: date | None = None) -> list[LaceOpportunity]:
    """Open or suggested ones only while they have not closed; the soonest
    deadline first."""
    query = select(LaceOpportunity).where(LaceOpportunity.lace_id == lace_id, LaceOpportunity.status == status)
    if status != "dismissed":
        today = today or datetime.now(UTC).date()
        query = query.where(or_(LaceOpportunity.deadline.is_(None), LaceOpportunity.deadline >= today),
                            or_(LaceOpportunity.event_date.is_(None), LaceOpportunity.event_date >= today))
    order = func.coalesce(LaceOpportunity.deadline, LaceOpportunity.event_date)
    return list((await db.scalars(query.order_by(order.asc().nulls_last(), LaceOpportunity.last_seen_at.desc())
                                  .limit(limit))).all())


async def set_status(db: AsyncSession, lace_id: uuid.UUID, opportunity_id: uuid.UUID, status: str) -> LaceOpportunity:
    """404 for an opportunity that is not this Lace's."""
    row = await db.scalar(select(LaceOpportunity).where(LaceOpportunity.id == opportunity_id,
                                                        LaceOpportunity.lace_id == lace_id))
    if row is None:
        raise NotFoundError("Opportunity not found")
    row.status = status
    await db.commit()
    return row


async def upsert_found(db: AsyncSession, lace_id: uuid.UUID, run_id: uuid.UUID,
                       found: list[Opportunity]) -> tuple[int, int]:
    """Save a search's opportunities. A new one is a suggestion until the
    founder saves it. One already on file is refreshed and keeps its status,
    so a dismissed one stays dismissed. Returns (new, refreshed)."""
    keys = [url_key(o.url) for o in found]
    known = set((await db.scalars(select(LaceOpportunity.url_key).where(
        LaceOpportunity.lace_id == lace_id, LaceOpportunity.url_key.in_(keys)))).all())
    now = datetime.now(UTC)
    for o, key in zip(found, keys):
        stmt = insert(LaceOpportunity).values(
            id=uuid.uuid4(), lace_id=lace_id, kind=o.kind, title=o.title[:500], organiser=(o.organiser or None)
            and o.organiser[:255], url=o.url, url_key=key, deadline=_date(o.deadline), event_date=_date(o.date),
            location=(o.location or None) and o.location[:255], why_it_fits=o.why_it_fits, how_to_act=o.how_to_act,
            found_by_run_id=run_id, last_seen_at=now, status="suggested",
        )
        refresh = {c: stmt.excluded[c] for c in ("kind", "title", "organiser", "url", "deadline", "event_date",
                                                 "location", "why_it_fits", "how_to_act", "found_by_run_id",
                                                 "last_seen_at")}
        await db.execute(stmt.on_conflict_do_update(constraint="uq_lace_opportunities_lace_id_url_key", set_=refresh))
    refreshed = len(set(keys) & known)
    return len(set(keys)) - refreshed, refreshed


async def laces_due_for_scan(db: AsyncSession, every: timedelta) -> list[tuple[uuid.UUID, uuid.UUID]]:
    """(lace_id, user_id) of active Laces with an ICP whose last opportunity
    search is older than `every` (or never ran) and none is running."""
    recent = select(models.Run.lace_id).where(
        models.Run.kind == "lace_opportunities", models.Run.lace_id.is_not(None),
        or_(models.Run.status.not_in(TERMINAL_STATUSES), models.Run.created_at >= datetime.now(UTC) - every))
    rows = await db.execute(select(Lace.id, Lace.user_id).where(
        Lace.status == "active", Lace.icp.is_not(None), Lace.id.not_in(recent)))
    return [(lace_id, user_id) for lace_id, user_id in rows.all()]
