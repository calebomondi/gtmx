"""The app's event log: batches of named events from the customer app, kept
for the admin dashboard's view of how the app is used."""

import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.database import models
from backend.app.database.lace_models import LaceMember
from backend.app.schemas.events import EventIn

# Far above anyone clicking around all day; stops a runaway client filling the table.
MAX_PER_DAY = 5000
# A browser's clock (and a batch held back while offline) can be off; times
# outside this window are taken as now.
MAX_CLOCK_SKEW = timedelta(hours=1)


def _when(at: datetime | None, now: datetime) -> datetime:
    if at is None or at.tzinfo is None or abs(now - at) > MAX_CLOCK_SKEW:
        return now
    return at


async def record(db: AsyncSession, user_id: uuid.UUID, events: list[EventIn]) -> int:
    """Keep these events, up to the user's daily cap; a Lace id is kept only
    for a Lace they are on. Returns how many were kept."""
    now = datetime.now(UTC)
    today = await db.scalar(select(func.count()).select_from(models.UserEvent).where(
        models.UserEvent.user_id == user_id, models.UserEvent.created_at >= now - timedelta(days=1))) or 0
    kept = events[:max(0, MAX_PER_DAY - today)]
    if not kept:
        return 0
    asked = {e.lace_id for e in kept if e.lace_id}
    theirs = set((await db.scalars(select(LaceMember.lace_id).where(
        LaceMember.user_id == user_id, LaceMember.lace_id.in_(asked)))).all()) if asked else set()
    db.add_all(models.UserEvent(user_id=user_id, lace_id=e.lace_id if e.lace_id in theirs else None, name=e.name,
                                detail=e.detail, created_at=_when(e.at, now)) for e in kept)
    await db.commit()
    return len(kept)
