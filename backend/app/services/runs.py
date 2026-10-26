"""Run rows: status bookkeeping and the queries the API needs."""

import uuid
from sqlalchemy import or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.database import models
from backend.app.database.connect import AsyncSessionLocal
from backend.app.services import lace_members
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


def _visible_to(user_id: uuid.UUID):
    """Runs the user started, and every run of a Lace they are on (a
    cofounder's turn, the scheduled brief)."""
    return or_(models.Run.user_id == user_id, models.Run.lace_id.in_(lace_members.lace_ids_of(user_id)))


async def get_visible(db: AsyncSession, user_id: uuid.UUID, run_id: uuid.UUID) -> models.Run:
    run = await db.scalar(select(models.Run).where(models.Run.id == run_id, _visible_to(user_id)))
    if run is None:
        raise NotFoundError("Run not found")
    return run


async def list_steps(db: AsyncSession, user_id: uuid.UUID, run_id: uuid.UUID,
                     after: int, limit: int) -> list[models.RunEvent]:
    """A visible run's progress steps after the `after` cursor, oldest first."""
    await get_visible(db, user_id, run_id)
    result = await db.execute(
        select(models.RunEvent)
        .where(models.RunEvent.run_id == run_id, models.RunEvent.type == "step", models.RunEvent.id > after)
        .order_by(models.RunEvent.id)
        .limit(limit)
    )
    return list(result.scalars().all())


async def list_active(db: AsyncSession, user_id: uuid.UUID) -> list[models.Run]:
    """The runs the user can see that are not finished, newest first -- what a
    reloaded client reattaches to."""
    result = await db.execute(
        select(models.Run)
        .where(_visible_to(user_id), models.Run.status.not_in(TERMINAL_STATUSES))
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


async def waiting_messages(db: AsyncSession, lace_id: uuid.UUID) -> list[dict]:
    """The Lace's messages waiting for it to be free, oldest first, as the
    conversation shows them (answers to its questions are left out)."""
    runs = (await db.scalars(select(models.Run).where(
        models.Run.lace_id == lace_id, models.Run.kind == "lace_turn", models.Run.status == "queued",
    ).order_by(models.Run.created_at))).all()
    return [{"role": "founder", "content": run.input.get("text", ""), "author": run.input.get("author"),
             "queued": True, **({"documents": run.input["documents"]} if run.input.get("documents") else {})}
            for run in runs if run.input and not run.input.get("answer")]
