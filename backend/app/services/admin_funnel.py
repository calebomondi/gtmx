"""Where users drop off: the activation funnel, abandoned discovery
interviews, and why runs fail."""

import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import distinct, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.database import models
from backend.app.schemas.admin import FailureReason, FunnelMetrics, FunnelStep, InterviewDropOff
from backend.app.services import admin as admin_service
from backend.app.services.admin_time import window

TOP_FAILURES = 8
# A discovery still waiting for an answer after this long has been abandoned.
STALE_INTERVIEW = timedelta(hours=24)
RESEARCH_KINDS = ("competitors", "competitor_research", "accounts")


async def _steps(db: AsyncSession) -> list[FunnelStep]:
    """Counted over existing accounts only, so no step exceeds sign-ups."""
    user_ids = [uuid.UUID(str(u.id)) for u in await admin_service.list_all_users()]

    async def _users_where(model, *where) -> int:
        return await db.scalar(
            select(func.count(distinct(model.user_id))).where(model.user_id.in_(user_ids), *where)
        ) or 0

    r, o = models.Run, models.OutreachMessage
    counts = [
        ("signed_up", "Signed up", len(user_ids)),
        ("started_discovery", "Started a discovery", await _users_where(r, r.kind == "discovery")),
        ("completed_discovery", "Finished a discovery",
         await _users_where(r, r.kind == "discovery", r.status == "completed")),
        ("ran_research", "Researched competitors or accounts", await _users_where(r, r.kind.in_(RESEARCH_KINDS))),
        ("drafted_outreach", "Drafted outreach", await _users_where(o)),
        ("sent_outreach", "Sent outreach", await _users_where(o, o.status == "sent")),
    ]
    return [FunnelStep(key=key, label=label, users=users) for key, label, users in counts]


async def _interview_dropoffs(db: AsyncSession, since: datetime) -> list[InterviewDropOff]:
    """Discoveries the user walked away from mid-interview, by the question
    they stopped at: cancelled, or left waiting for an answer."""
    r, e = models.Run, models.RunEvent
    stale = datetime.now(UTC) - STALE_INTERVIEW
    abandoned = (r.status == "cancelled") | ((r.status == "awaiting_input") & (r.updated_at < stale))
    last_question = (
        select(e.run_id, e.payload["interrupt_type"].astext.label("question"))
        .join(r, r.id == e.run_id)
        .where(e.type == "interrupt", r.kind == "discovery", r.created_at >= since, abandoned)
        .distinct(e.run_id).order_by(e.run_id, e.id.desc())
    ).subquery()
    rows = (await db.execute(
        select(last_question.c.question, func.count()).group_by(last_question.c.question)
        .order_by(func.count().desc())
    )).all()
    return [InterviewDropOff(question=question or "unknown", runs=n) for question, n in rows]


async def _failure_reasons(db: AsyncSession, since: datetime) -> list[FailureReason]:
    r = models.Run
    rows = (await db.execute(
        select(r.error, func.count(), func.max(r.updated_at))
        .where(r.status == "failed", r.created_at >= since, r.error.is_not(None))
        .group_by(r.error).order_by(func.count().desc()).limit(TOP_FAILURES)
    )).all()
    return [FailureReason(message=message, runs=n, last_at=last) for message, n, last in rows]


async def funnel(db: AsyncSession, days: int) -> FunnelMetrics:
    since, _ = window(days)
    r = models.Run
    discoveries = (r.kind == "discovery", r.created_at >= since)
    return FunnelMetrics(
        days=days,
        steps=await _steps(db),
        discoveries_started=await db.scalar(select(func.count()).where(*discoveries)) or 0,
        discoveries_completed=await db.scalar(select(func.count()).where(*discoveries, r.status == "completed")) or 0,
        interview_dropoffs=await _interview_dropoffs(db, since),
        failure_reasons=await _failure_reasons(db, since),
    )
