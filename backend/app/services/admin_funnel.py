"""Where users drop off: the activation funnel from sign-up to a reply, Lace
onboardings, and why runs fail."""

import uuid
from datetime import datetime

from sqlalchemy import distinct, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.database import models
from backend.app.database.lace_models import Lace, LaceAccount, LaceContact, LaceOutreach
from backend.app.schemas.admin import FailureReason, FunnelMetrics, FunnelStep
from backend.app.services import admin as admin_service
from backend.app.services.admin_time import window

TOP_FAILURES = 8


async def _steps(db: AsyncSession) -> list[FunnelStep]:
    """Counted over existing accounts only, so no step exceeds sign-ups."""
    user_ids = [uuid.UUID(str(u.id)) for u in await admin_service.list_all_users()]

    async def _users_where(user_id, *where) -> int:
        return await db.scalar(
            select(func.count(distinct(user_id))).where(user_id.in_(user_ids), *where)
        ) or 0

    async def _lace_users_where(model, *where) -> int:
        return await _users_where(Lace.user_id, Lace.id == model.lace_id, *where)

    r, o = models.Run, LaceOutreach
    counts = [
        ("signed_up", "Signed up", len(user_ids)),
        ("created_lace", "Created a Lace", await _users_where(Lace.user_id)),
        ("onboarded", "Finished onboarding",
         await _users_where(r.user_id, r.kind == "lace_onboarding", r.status == "completed")),
        ("saved_account", "Saved an account", await _lace_users_where(LaceAccount, LaceAccount.status == "target")),
        ("approved_contact", "Approved a contact",
         await _lace_users_where(LaceContact, LaceContact.approved_at.is_not(None))),
        ("sent_outreach", "Sent outreach", await _users_where(o.user_id, o.status == "sent")),
        ("got_reply", "Got a reply", await _users_where(o.user_id, o.direction == "inbound")),
    ]
    return [FunnelStep(key=key, label=label, users=users) for key, label, users in counts]


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
    onboardings = (r.kind == "lace_onboarding", r.created_at >= since)
    return FunnelMetrics(
        days=days,
        steps=await _steps(db),
        laces_created=await db.scalar(select(func.count()).where(Lace.created_at >= since)) or 0,
        onboardings_completed=await db.scalar(select(func.count()).where(*onboardings, r.status == "completed")) or 0,
        onboardings_failed=await db.scalar(select(func.count()).where(*onboardings, r.status == "failed")) or 0,
        failure_reasons=await _failure_reasons(db, since),
    )
