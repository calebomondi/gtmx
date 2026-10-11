"""Admin engagement metrics: growth, time in the app, what people create and
which features they use. Identity (sign-ups) comes from Supabase; everything
else from our own tables. Time in app comes from customer-app heartbeats
(services/activity.py), so it starts on the day tracking shipped."""

import uuid
from datetime import UTC, date, datetime, timedelta

from sqlalchemy import distinct, func, select, union
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.database import models
from backend.app.schemas.admin import ActivityDay, EngagementDay, EngagementMetrics, TopWorkspace, UserConnection
from backend.app.services import admin as admin_service
from backend.app.services import connections as connection_service
from backend.app.services.admin_connections import COMPOSIO_UNAVAILABLE, sends_by_platform
from backend.app.services.admin_directory import emails_by_id
from backend.app.services.admin_time import utc_day, window
from utils.log import logger

TOP_WORKSPACES = 10
USER_DETAIL_DAYS = 30
USER_TOP_WORKSPACES = 5
WEEK, MONTH = 7, 30


def _signup_day(user) -> date | None:
    created = getattr(user, "created_at", None)
    if isinstance(created, str):
        created = datetime.fromisoformat(created.replace("Z", "+00:00"))
    return created.astimezone(UTC).date() if created else None


def active_days(user_ids: list[uuid.UUID]):
    """(user_id, day) for every UTC day one of `user_ids` used the app or
    started a run. Limited to existing accounts: rows of deleted users would
    otherwise count people who aren't in the user total."""
    s, r = models.AppSession, models.Run
    return union(
        select(s.user_id, utc_day(s.started_at).label("day")).where(s.user_id.in_(user_ids)),
        select(s.user_id, utc_day(s.last_seen_at).label("day")).where(s.user_id.in_(user_ids)),
        select(r.user_id, utc_day(r.created_at).label("day")).where(r.user_id.in_(user_ids)),
    ).subquery()


async def _retention(db: AsyncSession, user_ids: list[uuid.UUID]) -> dict:
    today = datetime.now(UTC).date()
    days = active_days(user_ids)

    async def distinct_users(since: date) -> int:
        return await db.scalar(select(func.count(distinct(days.c.user_id))).where(days.c.day >= since)) or 0

    week_start, month_start = today - timedelta(days=WEEK - 1), today - timedelta(days=MONTH - 1)
    mau = await distinct_users(month_start)
    daily_total = await db.scalar(select(func.count()).select_from(days).where(days.c.day >= month_start)) or 0
    per_user = (
        select(days.c.user_id).where(days.c.day >= week_start)
        .group_by(days.c.user_id).having(func.count(distinct(days.c.day)) >= 2)
    ).subquery()
    return {
        "weekly_active_users": await distinct_users(week_start),
        "monthly_active_users": mau,
        "stickiness": round(daily_total / MONTH / mau, 3) if mau else None,
        "returning_users": await db.scalar(select(func.count()).select_from(per_user)) or 0,
    }


async def _time_in_app(
    db: AsyncSession, since: datetime, series: dict[date, EngagementDay], user_ids: list[uuid.UUID],
) -> dict:
    s = models.AppSession
    sessions, users, seconds = (await db.execute(
        select(func.count(), func.count(distinct(s.user_id)), func.coalesce(func.sum(s.active_seconds), 0))
        .where(s.started_at >= since)
    )).one()
    for day, day_seconds in (await db.execute(
        select(utc_day(s.started_at), func.sum(s.active_seconds)).where(s.started_at >= since)
        .group_by(utc_day(s.started_at))
    )).all():
        if day in series:
            series[day].active_seconds = int(day_seconds or 0)
    days = active_days(user_ids)
    for day, n in (await db.execute(
        select(days.c.day, func.count(distinct(days.c.user_id))).where(days.c.day >= since.date())
        .group_by(days.c.day)
    )).all():
        if day in series:
            series[day].active_users = n
    wa = models.WorkspaceActivity
    for day, n in (await db.execute(
        select(wa.day, func.count(distinct(wa.workspace_id))).where(wa.day >= since.date()).group_by(wa.day)
    )).all():
        if day in series:
            series[day].workspaces_interacted = n
    return {
        "sessions": sessions,
        "active_time_users": users,
        "total_active_seconds": int(seconds),
        "avg_active_seconds_per_user": round(seconds / users, 1) if users else None,
        "avg_session_seconds": round(seconds / sessions, 1) if sessions else None,
    }


async def _per_day(db: AsyncSession, series: dict[date, EngagementDay], since: datetime, field: str, column, *where):
    for day, n in (await db.execute(
        select(utc_day(column), func.count()).where(column >= since, *where).group_by(utc_day(column))
    )).all():
        if day in series:
            setattr(series[day], field, n)


async def _creations(db: AsyncSession, since: datetime, series: dict[date, EngagementDay]) -> dict:
    w, p = models.Workspace, models.Project
    await _per_day(db, series, since, "workspaces_created", w.date_created)
    await _per_day(db, series, since, "products_created", w.date_created, w.offer_type == "product")
    await _per_day(db, series, since, "services_created", w.date_created, w.offer_type == "service")
    await _per_day(db, series, since, "projects_created", p.date_created)
    offer_types = {"product": 0, "service": 0, "unknown": 0}
    for offer_type, n in (await db.execute(select(w.offer_type, func.count()).group_by(w.offer_type))).all():
        offer_types[offer_type or "unknown"] += n
    return {
        "workspaces_total": sum(offer_types.values()),
        "workspaces_created": await db.scalar(select(func.count()).where(w.date_created >= since)) or 0,
        "projects_total": await db.scalar(select(func.count()).select_from(p)) or 0,
        "projects_created": await db.scalar(select(func.count()).where(p.date_created >= since)) or 0,
        "offer_types": offer_types,
    }


async def _adoption(db: AsyncSession, since: datetime, series: dict[date, EngagementDay]) -> None:
    r, o = models.Run, models.OutreachMessage
    await _per_day(db, series, since, "chat_messages", models.ChatMessage.created_at, models.ChatMessage.role == "user")
    await _per_day(db, series, since, "competitor_runs", r.created_at, r.kind.in_(["competitors", "competitor_research"]))
    await _per_day(db, series, since, "account_runs", r.created_at, r.kind == "accounts")
    await _per_day(db, series, since, "outreach_drafted", o.created_at)
    await _per_day(db, series, since, "outreach_sent", o.sent_at, o.status == "sent")


async def top_workspaces(
    db: AsyncSession, since: date, limit: int, user_id: uuid.UUID | None = None,
) -> list[TopWorkspace]:
    """Workspaces with the most active time since `since`, optionally one user's."""
    wa, w = models.WorkspaceActivity, models.Workspace
    seconds = func.sum(wa.active_seconds)
    rows = (await db.execute(
        select(w.id, w.name, w.user_id, w.offer_type, seconds, func.sum(wa.visits))
        .join(wa, wa.workspace_id == w.id)
        .where(wa.day >= since, *([w.user_id == user_id] if user_id else []))
        .group_by(w.id).order_by(seconds.desc()).limit(limit)
    )).all()
    emails = await emails_by_id() if rows else {}
    return [
        TopWorkspace(id=wid, name=name, user_id=uid, user_email=emails.get(uid), offer_type=offer_type,
                     active_seconds=int(secs or 0), visits=int(visits or 0))
        for wid, name, uid, offer_type, secs, visits in rows
    ]


async def engagement(db: AsyncSession, days: int) -> EngagementMetrics:
    since, dates = window(days)
    series = {d: EngagementDay(day=d) for d in dates}
    users = await admin_service.list_all_users()
    for user in users:
        day = _signup_day(user)
        if day in series:
            series[day].new_users += 1

    user_ids = [uuid.UUID(str(u.id)) for u in users]
    time_in_app = await _time_in_app(db, since, series, user_ids)
    creations = await _creations(db, since, series)
    await _adoption(db, since, series)
    total_users = len(users)
    return EngagementMetrics(
        days=days,
        total_users=total_users,
        new_users=sum(point.new_users for point in series.values()),
        **await _retention(db, user_ids),
        **time_in_app,
        **creations,
        avg_workspaces_per_user=round(creations["workspaces_total"] / total_users, 2) if total_users else None,
        avg_projects_per_user=round(creations["projects_total"] / total_users, 2) if total_users else None,
        top_workspaces=await top_workspaces(db, since.date(), TOP_WORKSPACES),
        series=list(series.values()),
    )


async def _user_connections(db: AsyncSession, user_id: uuid.UUID) -> dict:
    sends = await sends_by_platform(db, user_id=user_id)
    try:
        connections = await connection_service.list_for_user(user_id)
    except Exception:  # the SDK raises its own and httpx's error types
        logger.exception("Listing connected accounts from Composio failed", extra={"user_id": str(user_id)})
        return {"connection_list": [], "connections_error": COMPOSIO_UNAVAILABLE, "connections": None}
    rows = [
        UserConnection(platform=c.platform, status=c.status, display_name=c.display_name,
                       sends=sends.get(c.platform, (0, 0))[0])
        for c in connections
    ]
    return {"connection_list": rows, "connections": sum(c.status == "live" for c in connections)}


async def user_engagement(db: AsyncSession, user_id: uuid.UUID) -> dict:
    """The user detail page's activity, top workspaces and connected accounts."""
    since, dates = window(USER_DETAIL_DAYS)
    s = models.AppSession
    by_day = dict((await db.execute(
        select(utc_day(s.started_at), func.sum(s.active_seconds))
        .where(s.user_id == user_id, s.started_at >= since).group_by(utc_day(s.started_at))
    )).all())
    return {
        "activity": [ActivityDay(day=d, active_seconds=int(by_day.get(d) or 0)) for d in dates],
        "top_workspaces": await top_workspaces(db, since.date(), USER_TOP_WORKSPACES, user_id),
        **await _user_connections(db, user_id),
    }
