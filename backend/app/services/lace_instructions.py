"""A Lace's standing instructions: how its team wants it to work, kept so
they hold in every chat and every job they apply to. The Lace keeps them
when the founder says them (remember_instruction); the team sees, edits
and removes them in the Lace's settings."""

import uuid
from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from agents.lace.prompts import render_instructions
from agents.lace.store import InstructionsFull
from agents.schemas.lace import INSTRUCTION_CHARS, Instruction, InstructionScope
from backend.app.database.lace_models import LaceInstruction
from backend.app.services.errors import ConflictError, InvalidInputError, NotFoundError
from config import settings


def summary(row: LaceInstruction) -> Instruction:
    return Instruction(id=str(row.id), text=row.text, applies_to=row.applies_to)


def _clean(text: str) -> str:
    """One line, within the cap. InvalidInputError when empty or too long."""
    text = " ".join(text.split())
    if not text:
        raise InvalidInputError("Write the instruction in a sentence.")
    if len(text) > INSTRUCTION_CHARS:
        raise InvalidInputError(f"Keep an instruction under {INSTRUCTION_CHARS} characters.")
    return text


async def list_for_lace(db: AsyncSession, lace_id: uuid.UUID, limit: int) -> list[LaceInstruction]:
    """Oldest first: the order they were given in."""
    return list((await db.scalars(select(LaceInstruction).where(LaceInstruction.lace_id == lace_id)
                                  .order_by(LaceInstruction.created_at).limit(limit))).all())


async def add(db: AsyncSession, lace_id: uuid.UUID, text: str, applies_to: InstructionScope,
              created_by: uuid.UUID | None) -> LaceInstruction:
    """Keep one. InvalidInputError for an empty or long one; InstructionsFull
    at the cap (the API says it as a conflict)."""
    text = _clean(text)
    held = await db.scalar(select(func.count()).select_from(LaceInstruction)
                           .where(LaceInstruction.lace_id == lace_id))
    if held >= settings.max_instructions_per_lace:
        raise InstructionsFull(f"This Lace keeps up to {settings.max_instructions_per_lace} standing instructions. "
                               "Remove one in its settings first.")
    row = LaceInstruction(lace_id=lace_id, text=text, applies_to=applies_to, created_by=created_by)
    db.add(row)
    await db.commit()
    return row


async def add_from_api(db: AsyncSession, lace_id: uuid.UUID, text: str, applies_to: InstructionScope,
                       created_by: uuid.UUID) -> LaceInstruction:
    try:
        return await add(db, lace_id, text, applies_to, created_by)
    except InstructionsFull as exc:
        raise ConflictError(str(exc)) from None


async def get_in_lace(db: AsyncSession, lace_id: uuid.UUID, instruction_id: uuid.UUID) -> LaceInstruction:
    row = await db.scalar(select(LaceInstruction).where(LaceInstruction.id == instruction_id,
                                                        LaceInstruction.lace_id == lace_id))
    if row is None:
        raise NotFoundError("Instruction not found")
    return row


async def edit(db: AsyncSession, lace_id: uuid.UUID, instruction_id: uuid.UUID, text: str | None,
               applies_to: InstructionScope | None) -> LaceInstruction:
    row = await get_in_lace(db, lace_id, instruction_id)
    if text is not None:
        row.text = _clean(text)
    if applies_to is not None:
        row.applies_to = applies_to
    row.updated_at = datetime.now(UTC)
    await db.commit()
    return row


async def remove(db: AsyncSession, lace_id: uuid.UUID, instruction_id: uuid.UUID) -> LaceInstruction:
    row = await get_in_lace(db, lace_id, instruction_id)
    await db.delete(row)
    await db.commit()
    return row


async def for_job(db: AsyncSession, lace_id: uuid.UUID, scope: InstructionScope) -> str:
    """The instructions a job of this kind follows, as lines; "" when none."""
    rows = await list_for_lace(db, lace_id, settings.max_instructions_per_lace)
    return render_instructions([summary(r) for r in rows], scope)
