"""Admin engagement metrics: growth, time in the app, the Laces people create
and what they use them for. Identity (sign-ups) comes from Supabase; everything
else from our own tables. Time in app comes from customer-app heartbeats
(services/activity.py), so it starts on the day tracking shipped."""

import uuid
from datetime import UTC, date, datetime, timedelta

from sqlalchemy import distinct, func, select, union
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.database import models
from backend.app.database.lace_models import Lace, LaceActivity, LaceOutreach
from backend.app.schemas.admin import ActivityDay, EngagementDay, EngagementMetrics, TopLace, UserConnection
from backend.app.services import admin as admin_service
from backend.app.services import connections as connection_service
from backend.app.services.admin_connections import COMPOSIO_UNAVAILABLE, sends_by_platform
from backend.app.services.admin_directory import emails_by_id
from backend.app.services.admin_time import utc_day, window
from utils.log import logger

TOP_LACES = 10
USER_DETAIL_DAYS = 30
USER_TOP_LACES = 5
COMPETITOR_RUN_KINDS = ("lace_competitors", "lace_monitor")
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
    r = models.Run
    for day, n in (await db.execute(
        select(utc_day(r.created_at), func.count(distinct(r.lace_id)))
        .where(r.created_at >= since, r.lace_id.is_not(None)).group_by(utc_day(r.created_at))
    )).all():
        if day in series:
            series[day].laces_active = n
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
    r = models.Run
    onboarding = r.kind == "lace_onboarding"
    await _per_day(db, series, since, "laces_created", Lace.created_at)
    await _per_day(db, series, since, "onboardings_completed", r.finished_at, onboarding, r.status == "completed")
    await _per_day(db, series, since, "onboardings_failed", r.finished_at, onboarding, r.status == "failed")
    return {
        "laces_total": await db.scalar(select(func.count()).select_from(Lace)) or 0,
        "laces_created": await db.scalar(select(func.count()).where(Lace.created_at >= since)) or 0,
    }


async def _adoption(db: AsyncSession, since: datetime, series: dict[date, EngagementDay]) -> int:
    """Fills the per-day feature use; returns the questions asked in the window."""
    r, o = models.Run, LaceOutreach
    await _per_day(db, series, since, "questions", r.created_at, r.kind == "lace_turn")
    await _per_day(db, series, since, "competitor_runs", r.created_at, r.kind.in_(COMPETITOR_RUN_KINDS))
    await _per_day(db, series, since, "account_runs", r.created_at, r.kind == "lace_accounts")
    await _per_day(db, series, since, "outreach_drafted", o.created_at, o.direction == "outbound")
    await _per_day(db, series, since, "outreach_sent", o.sent_at, o.status == "sent")
    return sum(point.questions for point in series.values())


async def top_laces(db: AsyncSession, since: datetime, limit: int, user_id: uuid.UUID | None = None) -> list[TopLace]:
    """Laces with the most runs since `since`, then the most Feed items,
    optionally one user's. Time isn't tracked per Lace."""
    r, a = models.Run, LaceActivity
    runs = select(func.count()).where(r.lace_id == Lace.id, r.created_at >= since).scalar_subquery()
    activity = select(func.count()).where(a.lace_id == Lace.id, a.created_at >= since).scalar_subquery()
    rows = (await db.execute(
        select(Lace.id, Lace.name, Lace.user_id, runs.label("runs"), activity.label("activity"))
        .where(*([Lace.user_id == user_id] if user_id else []), (runs > 0) | (activity > 0))
        .order_by(runs.desc(), activity.desc(), Lace.name).limit(limit)
    )).all()
    emails = await emails_by_id() if rows else {}
    return [TopLace(id=lid, name=name, user_id=uid, user_email=emails.get(uid), runs=n_runs, activity=n_activity)
            for lid, name, uid, n_runs, n_activity in rows]


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
    questions = await _adoption(db, since, series)
    total_users = len(users)
    return EngagementMetrics(
        days=days,
        total_users=total_users,
        new_users=sum(point.new_users for point in series.values()),
        **await _retention(db, user_ids),
        **time_in_app,
        **creations,
        avg_laces_per_user=round(creations["laces_total"] / total_users, 2) if total_users else None,
        questions=questions,
        top_laces=await top_laces(db, since, TOP_LACES),
        series=list(series.values()),
    )


async def _user_connections(db: AsyncSession, user_id: uuid.UUID) -> dict:
    sends = await sends_by_platform(db, user_id=user_id)
    try:
        connections = await connection_service.list_for_user(db, user_id)
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
    """The user detail page's activity, top Laces and connected accounts."""
    since, dates = window(USER_DETAIL_DAYS)
    s = models.AppSession
    by_day = dict((await db.execute(
        select(utc_day(s.started_at), func.sum(s.active_seconds))
        .where(s.user_id == user_id, s.started_at >= since).group_by(utc_day(s.started_at))
    )).all())
    return {
        "activity": [ActivityDay(day=d, active_seconds=int(by_day.get(d) or 0)) for d in dates],
        "top_laces": await top_laces(db, since, USER_TOP_LACES, user_id),
        **await _user_connections(db, user_id),
    }
