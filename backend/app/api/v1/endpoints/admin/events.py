"""The event log in the admin dashboard: what's used most, per day, and one
user's or Lace's events in order."""

import uuid

from fastapi import APIRouter, Query

from backend.app.api.deps import DbSession
from backend.app.schemas.admin import Page
from backend.app.schemas.events import AdminEventRow, EventName, EventSummary
from backend.app.services import admin_events

router = APIRouter(prefix="/events")


@router.get("/summary", response_model=EventSummary)
async def event_summary(db: DbSession, days: int = Query(default=30, ge=1, le=90), user_id: uuid.UUID | None = None,
                        lace_id: uuid.UUID | None = None):
    return await admin_events.summary(db, days, user_id, lace_id)


@router.get("", response_model=Page[AdminEventRow])
async def list_events(db: DbSession, page: int = Query(default=1, ge=1),
                      per_page: int = Query(default=50, ge=1, le=200), user_id: uuid.UUID | None = None,
                      lace_id: uuid.UUID | None = None, name: EventName | None = None):
    """Newest first."""
    return await admin_events.list_events(db, page, per_page, user_id, lace_id, name)
