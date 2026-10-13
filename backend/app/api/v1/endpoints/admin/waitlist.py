"""The waitlist in the admin dashboard: browse and search signups, see the
numbers, export them, and move people through the pilot funnel (audited)."""

import uuid

from fastapi import APIRouter, Query
from fastapi.responses import Response

from backend.app.api.deps import AdminUser, DbSession
from backend.app.schemas.admin import Page
from backend.app.schemas.waitlist import WaitlistSignupRow, WaitlistStats, WaitlistStatus, WaitlistStatusUpdate
from backend.app.services import admin_waitlist

router = APIRouter(prefix="/waitlist")


@router.get("", response_model=Page[WaitlistSignupRow])
async def list_waitlist(
    db: DbSession, page: int = Query(default=1, ge=1), per_page: int = Query(default=25, ge=1, le=100),
    q: str | None = Query(default=None, max_length=200), pilot: bool | None = None, status: WaitlistStatus | None = None,
):
    return await admin_waitlist.list_signups(db, page, per_page, q, pilot, status)


@router.get("/stats", response_model=WaitlistStats)
async def waitlist_stats(db: DbSession):
    return await admin_waitlist.stats(db)


@router.get("/export.csv", response_class=Response, responses={200: {"content": {"text/csv": {}}}})
async def export_waitlist(db: DbSession, pilot: bool | None = None, status: WaitlistStatus | None = None):
    return Response(
        content=await admin_waitlist.export_csv(db, pilot, status), media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{admin_waitlist.export_filename()}"'},
    )


@router.patch("/{signup_id}", response_model=WaitlistSignupRow)
async def update_waitlist_status(signup_id: uuid.UUID, payload: WaitlistStatusUpdate, actor: AdminUser, db: DbSession):
    return await admin_waitlist.set_status(db, actor, signup_id, payload.status)
