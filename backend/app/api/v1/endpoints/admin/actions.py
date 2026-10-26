"""Admin writes. Each goes through a service that records an audit row."""

import uuid

from fastapi import APIRouter

from backend.app.api.deps import AdminUser, DbSession
from backend.app.api.v1.endpoints.admin.entities import PageNo, PerPage
from backend.app.schemas.admin import (
    AdminLaceDetail, AdminRunDetail, AdminUserRow, AuditRow, Page, QuotaRow, QuotaUpdate, SuspendRequest,
)
from backend.app.services import admin as admin_service
from backend.app.services import admin_actions, admin_directory, admin_lace_actions, admin_laces, admin_runs

router = APIRouter()


async def _user_row(db, user_id: uuid.UUID) -> AdminUserRow:
    user = await admin_directory.get_supabase_user(user_id)
    return admin_directory.user_row(user, await admin_directory.user_activity(db, user_id))


@router.post("/users/{user_id}/admin", response_model=AdminUserRow)
async def grant_admin(user_id: uuid.UUID, actor: AdminUser, db: DbSession):
    await admin_directory.get_supabase_user(user_id)  # 404 before any write
    await admin_service.grant_admin(db, actor, user_id)
    return await _user_row(db, user_id)


@router.delete("/users/{user_id}/admin", response_model=AdminUserRow)
async def revoke_admin(user_id: uuid.UUID, actor: AdminUser, db: DbSession):
    await admin_directory.get_supabase_user(user_id)
    await admin_service.revoke_admin(db, actor, user_id)
    return await _user_row(db, user_id)


@router.post("/users/{user_id}/suspend", response_model=AdminUserRow)
async def suspend_user(user_id: uuid.UUID, payload: SuspendRequest, actor: AdminUser, db: DbSession):
    await admin_directory.get_supabase_user(user_id)
    await admin_actions.suspend_user(db, actor, user_id, payload.reason)
    return await _user_row(db, user_id)


@router.post("/users/{user_id}/reactivate", response_model=AdminUserRow)
async def reactivate_user(user_id: uuid.UUID, actor: AdminUser, db: DbSession):
    await admin_directory.get_supabase_user(user_id)
    await admin_actions.reactivate_user(db, actor, user_id)
    return await _user_row(db, user_id)


@router.get("/users/{user_id}/quotas", response_model=list[QuotaRow])
async def get_quotas(user_id: uuid.UUID, db: DbSession):
    return await admin_actions.quotas(db, user_id)


@router.put("/users/{user_id}/quotas", response_model=list[QuotaRow])
async def set_quota(user_id: uuid.UUID, payload: QuotaUpdate, actor: AdminUser, db: DbSession):
    await admin_directory.get_supabase_user(user_id)
    return await admin_actions.set_quota(db, actor, user_id, payload.kind, payload.daily_cap)


@router.post("/runs/{run_id}/cancel", response_model=AdminRunDetail)
async def cancel_run(run_id: uuid.UUID, actor: AdminUser, db: DbSession):
    await admin_actions.cancel_run(db, actor, run_id)
    db.expire_all()
    return await admin_runs.get_run(db, run_id)


@router.post("/laces/{lace_id}/fold", response_model=AdminLaceDetail)
async def fold_lace(lace_id: uuid.UUID, actor: AdminUser, db: DbSession):
    """A duplicate's people join the Lace holding its domain; it is archived."""
    await admin_lace_actions.fold(db, actor, lace_id)
    return await admin_laces.get_lace(db, lace_id)


@router.post("/laces/{lace_id}/take-domain", response_model=AdminLaceDetail)
async def take_lace_domain(lace_id: uuid.UUID, actor: AdminUser, db: DbSession):
    """A duplicate becomes the startup's Lace, in place of the one holding its domain."""
    await admin_lace_actions.take_domain(db, actor, lace_id)
    return await admin_laces.get_lace(db, lace_id)


@router.get("/audit-log", response_model=Page[AuditRow])
async def audit_log(db: DbSession, page: int = PageNo, per_page: int = PerPage,
                    action: str | None = None, target_id: str | None = None):
    rows, total = await admin_service.list_audit(db, page, per_page, action, target_id)
    return Page(items=[AuditRow.model_validate(r) for r in rows], total=total, page=page, per_page=per_page)
