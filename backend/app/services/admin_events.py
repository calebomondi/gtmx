"""The event log as admins read it: what is used most (and by how many
people) over a window, per day, and one user's or Lace's events in order."""

import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import distinct, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.database import models
from backend.app.database.lace_models import Lace
from backend.app.schemas.admin import Page
from backend.app.schemas.events import AdminEventRow, EventCount, EventDay, EventSummary
from backend.app.services.admin_directory import emails_by_id
from backend.app.services.admin_time import utc_day

_E = models.UserEvent


def _filters(user_id: uuid.UUID | None, lace_id: uuid.UUID | None, name: str | None = None) -> list:
    return [c == v for c, v in ((_E.user_id, user_id), (_E.lace_id, lace_id), (_E.name, name)) if v is not None]


async def summary(db: AsyncSession, days: int, user_id: uuid.UUID | None = None,
                  lace_id: uuid.UUID | None = None) -> EventSummary:
    where = [_E.created_at >= datetime.now(UTC) - timedelta(days=days), *_filters(user_id, lace_id)]
    totals = (await db.execute(
        select(_E.name, _E.detail, func.count(), func.count(distinct(_E.user_id))).where(*where)
        .group_by(_E.name, _E.detail).order_by(func.count().desc())
    )).all()
    day = utc_day(_E.created_at)
    per_day = (await db.execute(
        select(day, func.count(), func.count(distinct(_E.user_id))).where(*where).group_by(day).order_by(day)
    )).all()
    people = await db.scalar(select(func.count(distinct(_E.user_id))).where(*where)) or 0
    return EventSummary(days=days, people=people, totals=[EventCount(name=n, detail=d, count=c, users=u) for n, d, c, u in totals],
                        per_day=[EventDay(day=d, count=c, users=u) for d, c, u in per_day])


async def list_events(db: AsyncSession, page: int, per_page: int, user_id: uuid.UUID | None = None,
                      lace_id: uuid.UUID | None = None, name: str | None = None) -> Page[AdminEventRow]:
    """Newest first."""
    where = _filters(user_id, lace_id, name)
    total = await db.scalar(select(func.count()).select_from(_E).where(*where))
    rows = (await db.execute(
        select(_E, Lace.name).outerjoin(Lace, Lace.id == _E.lace_id).where(*where)
        .order_by(_E.created_at.desc(), _E.id.desc()).offset((page - 1) * per_page).limit(per_page)
    )).all()
    emails = await emails_by_id() if rows else {}
    return Page(items=[AdminEventRow.model_validate(e).model_copy(update={"lace_name": n, "user_email": emails.get(e.user_id)})
                       for e, n in rows], total=total or 0, page=page, per_page=per_page)
