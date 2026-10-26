"""Time in the app, from client heartbeats.

The client pings only while its tab is visible and the user has recently
done something. The server, not the client, decides how much time a ping is
worth: the gap since the user's previous ping, capped. Two open tabs share
one session, so their pings don't double-count.
"""

import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.database import models
from config import settings


async def _current_session(db: AsyncSession, user_id: uuid.UUID, now: datetime) -> models.AppSession | None:
    cutoff = now - timedelta(seconds=settings.activity_session_gap_s)
    return await db.scalar(
        select(models.AppSession)
        .where(models.AppSession.user_id == user_id, models.AppSession.last_seen_at >= cutoff)
        .order_by(models.AppSession.last_seen_at.desc())
        .limit(1)
    )


async def record_heartbeat(db: AsyncSession, user_id: uuid.UUID, now: datetime | None = None) -> None:
    """Credit active time to the user's session."""
    now = now or datetime.now(UTC)
    # Pings from two tabs (or a page load plus a route change) arrive together.
    # Without this they'd each open a session.
    await db.execute(select(func.pg_advisory_xact_lock(func.hashtext(f"activity:{user_id}"))))

    session = await _current_session(db, user_id, now)
    if session is None:
        session = models.AppSession(user_id=user_id, started_at=now, last_seen_at=now, active_seconds=0)
        db.add(session)
    else:
        elapsed = (now - session.last_seen_at).total_seconds()
        session.active_seconds += int(min(max(elapsed, 0), settings.activity_max_credit_s))
        session.last_seen_at = now
    await db.commit()
