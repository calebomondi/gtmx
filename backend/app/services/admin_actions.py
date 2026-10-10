"""Admin writes other than roles: suspend/reactivate a user, cancel a run,
override a user's daily quota. Every one writes an admin_audit_log row."""

import uuid

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app import supabase_admin
from backend.app.database import models
from backend.app.runs import manager
from backend.app.runs.kinds import RUN_KINDS
from backend.app.schemas.admin import QuotaRow
from backend.app.services import limits
from backend.app.services.admin import record_audit
from backend.app.services.errors import ConflictError, InvalidInputError, NotFoundError
from backend.app.services.runs import TERMINAL_STATUSES

# Supabase has no "forever"; a century is the documented way to ban indefinitely.
_SUSPEND_DURATION = "876000h"


async def _audit(db: AsyncSession, actor, action: str, target_type: str, target_id, before, after) -> None:
    await record_audit(db, actor_id=actor.id, actor_email=actor.email, action=action,
                       target_type=target_type, target_id=str(target_id), before=before, after=after)
    await db.commit()


async def suspend_user(db: AsyncSession, actor, user_id: uuid.UUID, reason: str):
    """Block sign-in and API access, and stop the user's in-flight runs."""
    if actor.id == user_id:
        raise ConflictError("You can't suspend yourself.")
    client = await supabase_admin.get_client()
    target = (await client.auth.admin.get_user_by_id(str(user_id))).user
    if supabase_admin.is_admin(target.app_metadata):
        raise ConflictError("Revoke this user's admin role before suspending them.")
    await client.auth.admin.update_user_by_id(str(user_id), {"ban_duration": _SUSPEND_DURATION})
    active = (await db.execute(select(models.Run.id).where(
        models.Run.user_id == user_id, models.Run.status.not_in(TERMINAL_STATUSES),
    ))).scalars().all()
    for run_id in active:
        await manager.cancel_any(run_id, "Run stopped: this account was suspended.")
    await _audit(db, actor, "user.suspend", "user", user_id, {"suspended": False},
                 {"suspended": True, "reason": reason, "runs_cancelled": len(active)})
    return (await client.auth.admin.get_user_by_id(str(user_id))).user


async def reactivate_user(db: AsyncSession, actor, user_id: uuid.UUID):
    client = await supabase_admin.get_client()
    await client.auth.admin.update_user_by_id(str(user_id), {"ban_duration": "none"})
    await _audit(db, actor, "user.reactivate", "user", user_id, {"suspended": True}, {"suspended": False})
    return (await client.auth.admin.get_user_by_id(str(user_id))).user


async def cancel_run(db: AsyncSession, actor, run_id: uuid.UUID) -> None:
    run = await db.get(models.Run, run_id)
    if run is None:
        raise NotFoundError("Run not found.")
    if run.status in TERMINAL_STATUSES:
        raise ConflictError(f"This run already {run.status}.")
    before = run.status
    await manager.cancel_any(run_id, "Run cancelled by an administrator.")
    await _audit(db, actor, "run.cancel", "run", run_id, {"status": before}, {"status": "cancelled"})


async def quotas(db: AsyncSession, user_id: uuid.UUID) -> list[QuotaRow]:
    overrides = dict((await db.execute(
        select(models.UserQuota.kind, models.UserQuota.daily_cap).where(models.UserQuota.user_id == user_id)
    )).all())
    return [QuotaRow(kind=k, default_cap=limits.default_daily_cap(k), override=overrides.get(k)) for k in RUN_KINDS]


async def set_quota(db: AsyncSession, actor, user_id: uuid.UUID, kind: str, daily_cap: int | None) -> list[QuotaRow]:
    """`daily_cap=None` removes the override (back to the default)."""
    if kind not in RUN_KINDS:
        raise InvalidInputError(f"Unknown run kind: {kind}")
    row = await db.scalar(select(models.UserQuota).where(
        models.UserQuota.user_id == user_id, models.UserQuota.kind == kind,
    ))
    before = row.daily_cap if row else None
    if daily_cap is None:
        await db.execute(delete(models.UserQuota).where(
            models.UserQuota.user_id == user_id, models.UserQuota.kind == kind,
        ))
    elif row is None:
        db.add(models.UserQuota(user_id=user_id, kind=kind, daily_cap=daily_cap))
    else:
        row.daily_cap = daily_cap
    await _audit(db, actor, "quota.set", "user", user_id, {"kind": kind, "daily_cap": before},
                 {"kind": kind, "daily_cap": daily_cap})
    return await quotas(db, user_id)
