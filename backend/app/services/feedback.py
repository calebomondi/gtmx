"""Feedback a user sends from the app: kept with where they were, for the
team to read in the admin dashboard."""

import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.database import models
from backend.app.services import lace_members
from backend.app.services.errors import InvalidInputError, RateLimitedError

# Far above anyone writing to us in earnest; stops a stuck client filling the table.
MAX_PER_DAY = 20


async def submit(db: AsyncSession, user_id: uuid.UUID, email: str | None, text: str, path: str | None,
                 lace_id: uuid.UUID | None) -> models.Feedback:
    text = text.strip()
    if not text:
        raise InvalidInputError("Write something first.")
    since = datetime.now(UTC) - timedelta(days=1)
    sent = await db.scalar(select(func.count()).select_from(models.Feedback).where(
        models.Feedback.user_id == user_id, models.Feedback.created_at >= since))
    if (sent or 0) >= MAX_PER_DAY:
        raise RateLimitedError("That's a lot of feedback for one day. Thank you! Send more tomorrow.")
    if lace_id is not None and await lace_members.membership(db, lace_id, user_id) is None:
        lace_id = None  # only a Lace of theirs is kept with it
    row = models.Feedback(user_id=user_id, email=email, lace_id=lace_id, path=path, text=text)
    db.add(row)
    await db.commit()
    return row
