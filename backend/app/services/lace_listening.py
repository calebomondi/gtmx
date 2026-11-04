"""Which Laces are due a listen on their social accounts."""

import uuid
from datetime import timedelta

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.database import models
from backend.app.database.lace_models import Lace
from backend.app.services.runs import TERMINAL_STATUSES
from config import settings


async def laces_due(db: AsyncSession) -> list[tuple[uuid.UUID, uuid.UUID]]:
    """(lace_id, user_id) of active Laces with no listen running or started
    within the listening interval. The listen itself finds out which social
    accounts are on, and finishes quietly when none is."""
    recent = select(models.Run.id).where(
        models.Run.kind == "lace_listening", models.Run.lace_id == Lace.id,
        or_(models.Run.status.not_in(TERMINAL_STATUSES),
            models.Run.created_at >= func.now() - timedelta(hours=settings.listening_interval_h)))
    rows = await db.execute(select(Lace.id, Lace.user_id).where(Lace.status == "active", ~recent.exists()))
    return [(lace_id, user_id) for lace_id, user_id in rows.all()]
