"""Connected accounts across users (live from Composio) and how much each
platform is actually used to send outreach (from our own table)."""

import uuid
from datetime import datetime

from sqlalchemy import distinct, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.database.lace_models import LaceOutreach
from backend.app.schemas.admin import ConnectionMetrics, PlatformUsage
from backend.app.services import admin as admin_service
from backend.app.services import connections as connection_service
from backend.app.services.admin_time import window
from backend.app.services.outreach import CHANNEL_PLATFORM
from utils.log import logger

COMPOSIO_UNAVAILABLE = "Couldn't read connected accounts from Composio; see the API logs."


async def live_connections(db: AsyncSession) -> tuple[dict[uuid.UUID, set[str]] | None, str | None]:
    """Every user's live platforms, or (None, reason) when Composio fails, so
    a Composio outage degrades the page instead of breaking it."""
    try:
        return await connection_service.live_by_user(db), None
    except Exception:  # the SDK raises its own and httpx's error types
        logger.exception("Listing connected accounts from Composio failed")
        return None, COMPOSIO_UNAVAILABLE


async def sends_by_platform(
    db: AsyncSession, *, since: datetime | None = None, user_id: uuid.UUID | None = None,
) -> dict[str, tuple[int, int]]:
    """platform -> (messages sent, distinct senders)."""
    o = LaceOutreach
    where = [o.status == "sent"]
    if since:
        where.append(o.sent_at >= since)
    if user_id:
        where.append(o.user_id == user_id)
    rows = (await db.execute(
        select(o.channel, func.count(), func.count(distinct(o.user_id))).where(*where).group_by(o.channel)
    )).all()
    return {CHANNEL_PLATFORM.get(channel, channel): (sent, senders) for channel, sent, senders in rows}


async def connection_metrics(db: AsyncSession, days: int) -> ConnectionMetrics:
    since, _ = window(days)
    live, error = await live_connections(db)
    live = live or {}
    sends = await sends_by_platform(db, since=since)
    total_users = len(await admin_service.list_all_users())
    platforms = [
        PlatformUsage(
            platform=platform,
            connected_users=sum(platform in platforms for platforms in live.values()),
            sends=sends.get(platform, (0, 0))[0],
            senders=sends.get(platform, (0, 0))[1],
        )
        for platform in connection_service.TOOLKITS
    ]
    connections = sum(len(platforms) for platforms in live.values())
    return ConnectionMetrics(
        days=days,
        error=error,
        users_with_connections=sum(1 for platforms in live.values() if platforms),
        avg_connections_per_user=round(connections / total_users, 2) if total_users and not error else None,
        platforms=sorted(platforms, key=lambda p: (-p.connected_users, -p.sends)),
    )
