"""The closed pilot's guest list in the admin dashboard: who is let in, let
more in by email or from the waitlist, take them off (all audited)."""

import uuid

from fastapi import APIRouter, Query, status

from backend.app.api.deps import AdminUser, DbSession
from backend.app.schemas.admin import Page
from backend.app.schemas.pilot import PilotAccessAdd, PilotAccessAdded, PilotAccessRow, PilotStatus
from backend.app.schemas.waitlist import WaitlistSignupRow
from backend.app.services import admin_pilot, pilot

router = APIRouter()


@router.get("/pilot-access/status", response_model=PilotStatus)
async def pilot_status():
    return PilotStatus(invite_only=pilot.invite_only())


@router.get("/pilot-access", response_model=Page[PilotAccessRow])
async def list_pilot_access(
    db: DbSession, page: int = Query(default=1, ge=1), per_page: int = Query(default=25, ge=1, le=100),
    q: str | None = Query(default=None, max_length=200),
):
    return await admin_pilot.list_access(db, page, per_page, q)


@router.post("/pilot-access", response_model=PilotAccessAdded)
async def add_pilot_access(payload: PilotAccessAdd, actor: AdminUser, db: DbSession):
    """Let these emails into the pilot."""
    return PilotAccessAdded(added=await admin_pilot.add(db, actor, [str(e) for e in payload.emails]))


@router.delete("/pilot-access/{access_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_pilot_access(access_id: uuid.UUID, actor: AdminUser, db: DbSession):
    await admin_pilot.remove(db, actor, access_id)


@router.post("/waitlist/{signup_id}/approve", response_model=WaitlistSignupRow)
async def approve_waitlist_signup(signup_id: uuid.UUID, actor: AdminUser, db: DbSession):
    """Let a waitlist signup into the pilot, and mark them invited."""
    return WaitlistSignupRow.model_validate(await admin_pilot.approve_signup(db, actor, signup_id))
