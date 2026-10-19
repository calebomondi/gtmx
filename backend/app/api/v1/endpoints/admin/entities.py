"""Read-only admin views: users, workspaces, Laces, runs (with timelines), signals."""

import uuid

from fastapi import APIRouter, Query

from backend.app.api.deps import DbSession
from backend.app.schemas.admin import (
    AdminLaceDetail, AdminLaceRow, AdminRunDetail, AdminRunRow, AdminSignalRow, AdminUserDetail, AdminUserRow, AdminWorkspaceRow, Page,
)
from backend.app.services import admin_directory, admin_engagement, admin_laces, admin_runs

router = APIRouter()

PageNo = Query(default=1, ge=1)
PerPage = Query(default=25, ge=1, le=100)
RECENT_RUNS = 20


@router.get("/users", response_model=Page[AdminUserRow])
async def list_users(db: DbSession, page: int = PageNo, per_page: int = PerPage, q: str | None = None):
    return await admin_directory.list_users(db, page, per_page, q)


@router.get("/users/{user_id}", response_model=AdminUserDetail)
async def get_user(user_id: uuid.UUID, db: DbSession):
    user = await admin_directory.get_supabase_user(user_id)
    row = admin_directory.user_row(user, await admin_directory.user_activity(db, user_id))
    engagement = await admin_engagement.user_engagement(db, user_id)
    return AdminUserDetail(
        **(row.model_dump() | {"connections": engagement.pop("connections")}),
        **engagement,
        spend_usd=await admin_runs.user_spend(db, user_id),
        recent_runs=(await admin_runs.list_runs(db, 1, RECENT_RUNS, user_id=user_id)).items,
        workspace_list=(await admin_directory.list_workspaces(db, 1, 100, user_id=user_id)).items,
    )


@router.get("/workspaces", response_model=Page[AdminWorkspaceRow])
async def list_workspaces(db: DbSession, page: int = PageNo, per_page: int = PerPage, q: str | None = None):
    return await admin_directory.list_workspaces(db, page, per_page, q)


@router.get("/laces", response_model=Page[AdminLaceRow])
async def list_laces(db: DbSession, page: int = PageNo, per_page: int = PerPage, q: str | None = None,
                     user_id: uuid.UUID | None = None):
    """Every Lace, most recently active first; `q` matches name, website or startup."""
    return await admin_laces.list_laces(db, page, per_page, q, user_id)


@router.get("/laces/{lace_id}", response_model=AdminLaceDetail)
async def get_lace(lace_id: uuid.UUID, db: DbSession):
    return await admin_laces.get_lace(db, lace_id)


@router.get("/runs", response_model=Page[AdminRunRow])
async def list_runs(
    db: DbSession, page: int = PageNo, per_page: int = PerPage, status: str | None = None,
    kind: str | None = None, user_id: uuid.UUID | None = None, workspace_id: uuid.UUID | None = None,
    lace_id: uuid.UUID | None = None,
):
    return await admin_runs.list_runs(db, page, per_page, status=status, kind=kind,
                                      user_id=user_id, workspace_id=workspace_id, lace_id=lace_id)


@router.get("/runs/{run_id}", response_model=AdminRunDetail)
async def get_run(run_id: uuid.UUID, db: DbSession):
    return await admin_runs.get_run(db, run_id)


@router.get("/signals", response_model=Page[AdminSignalRow])
async def list_signals(
    db: DbSession, page: int = PageNo, per_page: int = PerPage, user_id: uuid.UUID | None = None,
    category: str | None = None,
):
    return await admin_runs.list_signals(db, page, per_page, user_id=user_id, category=category)
