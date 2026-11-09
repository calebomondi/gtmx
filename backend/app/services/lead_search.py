"""Which Laces are due their scheduled lead search: once a day
(LEAD_SEARCH_EVERY_H), like the opportunity search but less often, as it reads
more and costs more. A Lace needs an ideal customer profile first, and gets
none on its first day (its first look handles that day)."""

import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.database import models
from backend.app.database.lace_models import Lace
from backend.app.services.lace_briefs import on_first_day
from backend.app.services.runs import TERMINAL_STATUSES
from config import settings


async def laces_due(db: AsyncSession, now: datetime | None = None) -> list[tuple[uuid.UUID, uuid.UUID]]:
    """(lace_id, owner user_id) of active Laces past their first day, with an
    ICP, whose last lead search (asked for or scheduled) is older than the
    interval, or never ran, and none is under way or waiting."""
    now = now or datetime.now(UTC)
    recent = select(models.Run.id).where(
        models.Run.kind == "lace_accounts", models.Run.lace_id == Lace.id,
        or_(models.Run.status.not_in(TERMINAL_STATUSES),
            models.Run.created_at >= now - timedelta(hours=settings.lead_search_every_h)))
    laces = (await db.scalars(select(Lace).where(
        Lace.status == "active", Lace.icp.is_not(None), ~recent.exists()))).all()
    return [(lace.id, lace.user_id) for lace in laces if not on_first_day(lace, now)]
