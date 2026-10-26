"""Users' feedback as the team reads it: newest first, new or read. Marking
one read (or new again) writes an admin_audit_log row."""

import uuid
from datetime import UTC, datetime

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.database import models
from backend.app.database.lace_models import Lace
from backend.app.schemas.admin import Page
from backend.app.schemas.feedback import AdminFeedbackRow, FeedbackStatus
from backend.app.services.admin import record_audit
from backend.app.services.errors import NotFoundError

_F = models.Feedback


def _row(feedback: models.Feedback, lace_name: str | None) -> AdminFeedbackRow:
    return AdminFeedbackRow.model_validate(feedback).model_copy(update={"lace_name": lace_name})


async def list_feedback(db: AsyncSession, page: int, per_page: int, status: FeedbackStatus | None = None,
                        q: str | None = None) -> Page[AdminFeedbackRow]:
    filters = []
    if status:
        filters.append(_F.status == status)
    if q and q.strip():
        needle = f"%{q.strip()}%"
        filters.append(or_(_F.text.ilike(needle), _F.email.ilike(needle)))
    total = await db.scalar(select(func.count()).select_from(_F).where(*filters))
    rows = (await db.execute(
        select(_F, Lace.name).outerjoin(Lace, Lace.id == _F.lace_id).where(*filters)
        .order_by(_F.created_at.desc()).offset((page - 1) * per_page).limit(per_page)
    )).all()
    return Page(items=[_row(f, name) for f, name in rows], total=total or 0, page=page, per_page=per_page)


async def set_status(db: AsyncSession, actor, feedback_id: uuid.UUID, status: FeedbackStatus) -> AdminFeedbackRow:
    feedback = await db.get(_F, feedback_id)
    if feedback is None:
        raise NotFoundError("Feedback not found.")
    before = feedback.status
    feedback.status = status
    feedback.read_at = datetime.now(UTC) if status == "read" else None
    await record_audit(db, actor_id=actor.id, actor_email=actor.email, action="feedback.status",
                       target_type="feedback", target_id=str(feedback_id), before={"status": before},
                       after={"status": status})
    await db.commit()
    lace = await db.get(Lace, feedback.lace_id) if feedback.lace_id else None
    return _row(feedback, lace.name if lace else None)
