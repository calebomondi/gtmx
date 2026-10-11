"""Time in the app, from client heartbeats.

The client pings only while its tab is visible and the user has recently
done something. The server, not the client, decides how much time a ping is
worth: the gap since the user's previous ping, capped. Two open tabs share
one session, so their pings don't double-count.
"""

import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.database import models
from backend.app.services import workspaces as workspace_service
from config import settings


async def _current_session(db: AsyncSession, user_id: uuid.UUID, now: datetime) -> models.AppSession | None:
    cutoff = now - timedelta(seconds=settings.activity_session_gap_s)
    return await db.scalar(
        select(models.AppSession)
        .where(models.AppSession.user_id == user_id, models.AppSession.last_seen_at >= cutoff)
        .order_by(models.AppSession.last_seen_at.desc())
        .limit(1)
    )


async def _credit_workspace(
    db: AsyncSession, user_id: uuid.UUID, workspace_id: uuid.UUID, seconds: int, new_visit: bool, now: datetime,
) -> None:
    table = models.WorkspaceActivity.__table__
    stmt = insert(table).values(
        user_id=user_id, workspace_id=workspace_id, day=now.date(),
        active_seconds=seconds, visits=1 if new_visit else 0, last_seen_at=now,
    )
    await db.execute(stmt.on_conflict_do_update(
        constraint="uq_workspace_activity_workspace_day",
        set_={
            "active_seconds": table.c.active_seconds + stmt.excluded.active_seconds,
            "visits": table.c.visits + stmt.excluded.visits,
            "last_seen_at": stmt.excluded.last_seen_at,
        },
    ))


async def record_heartbeat(
    db: AsyncSession, user_id: uuid.UUID, workspace_id: uuid.UUID | None, now: datetime | None = None,
) -> None:
    """Credit active time to the user's session and, if one is on screen, to
    the workspace (which must be theirs: NotFoundError otherwise)."""
    now = now or datetime.now(UTC)
    # Pings from two tabs (or a page load plus a route change) arrive together.
    # Without this they'd each open a session and each count the visit.
    await db.execute(select(func.pg_advisory_xact_lock(func.hashtext(f"activity:{user_id}"))))
    workspace = await workspace_service.get_owned(db, user_id, workspace_id) if workspace_id else None

    session = await _current_session(db, user_id, now)
    if session is None:
        session = models.AppSession(user_id=user_id, started_at=now, last_seen_at=now, active_seconds=0)
        db.add(session)
        seconds = 0
    else:
        elapsed = (now - session.last_seen_at).total_seconds()
        seconds = int(min(max(elapsed, 0), settings.activity_max_credit_s))
        session.active_seconds += seconds
        session.last_seen_at = now

    if workspace is not None:
        await _credit_workspace(db, user_id, workspace.id, seconds, session.last_workspace_id != workspace.id, now)
        workspace.last_activity = now
    session.last_workspace_id = workspace.id if workspace else None
    await db.commit()
