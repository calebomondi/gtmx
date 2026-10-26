"""Users' feedback in the admin dashboard: read it, newest first, and mark
it read (audited)."""

import uuid

from fastapi import APIRouter, Query

from backend.app.api.deps import AdminUser, DbSession
from backend.app.schemas.admin import Page
from backend.app.schemas.feedback import AdminFeedbackRow, FeedbackStatus, FeedbackStatusUpdate
from backend.app.services import admin_feedback

router = APIRouter(prefix="/feedback")


@router.get("", response_model=Page[AdminFeedbackRow])
async def list_feedback(
    db: DbSession, page: int = Query(default=1, ge=1), per_page: int = Query(default=25, ge=1, le=100),
    status: FeedbackStatus | None = None, q: str | None = Query(default=None, max_length=200),
):
    """Newest first; `q` matches the text or the sender's email."""
    return await admin_feedback.list_feedback(db, page, per_page, status, q)


@router.patch("/{feedback_id}", response_model=AdminFeedbackRow)
async def update_feedback_status(feedback_id: uuid.UUID, payload: FeedbackStatusUpdate, actor: AdminUser,
                                 db: DbSession):
    return await admin_feedback.set_status(db, actor, feedback_id, payload.status)
