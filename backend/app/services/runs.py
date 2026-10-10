"""Run rows: status bookkeeping and the queries the API needs."""

import uuid
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.database import models
from backend.app.database.connect import AsyncSessionLocal
from backend.app.services.errors import NotFoundError


TERMINAL_STATUSES = ("completed", "failed", "cancelled")


async def set_run_fields(model: type[models.Run], run_id: uuid.UUID, **fields) -> models.Run | None:
    """Write run fields in their own short-lived session.

    One session per transition, not one held across the run: a run takes
    minutes of network and LLM time, and a session checked out that long sits
    idle on a pooled connection. Returns None when the run is gone (its
    workspace was deleted mid-flight), so the caller can stop.
    """
    async with AsyncSessionLocal() as db:
        async with db.begin():
            run = await db.get(model, run_id)
            if run is None:
                return None
            for field, value in fields.items():
                setattr(run, field, value)
            return run


async def get_owned(db: AsyncSession, owner_id: uuid.UUID, run_id: uuid.UUID) -> models.Run:
    run = await db.scalar(
        select(models.Run).where(models.Run.id == run_id, models.Run.user_id == owner_id)
    )
    if run is None:
        raise NotFoundError("Run not found")
    return run


async def list_active(db: AsyncSession, owner_id: uuid.UUID) -> list[models.Run]:
    """The user's runs that are not finished, newest first -- what a reloaded
    client reattaches to."""
    result = await db.execute(
        select(models.Run)
        .where(models.Run.user_id == owner_id, models.Run.status.not_in(TERMINAL_STATUSES))
        .order_by(models.Run.created_at.desc())
    )
    return list(result.scalars().all())


async def claim_for_resume(db: AsyncSession, owner_id: uuid.UUID, run_id: uuid.UUID) -> bool:
    """Atomically move an owned run from awaiting_input to running. False if it
    was not waiting -- so two concurrent answers can't both resume it."""
    result = await db.execute(
        update(models.Run)
        .where(models.Run.id == run_id, models.Run.user_id == owner_id, models.Run.status == "awaiting_input")
        .values(status="running")
        .returning(models.Run.id)
    )
    await db.commit()
    return result.first() is not None
