"""A Lace's standing instructions: how its team wants it to work. The Lace
keeps them from the chat; the team sees, adds, edits and removes them here."""

import uuid

from fastapi import APIRouter, Query, status

from backend.app.api.deps import CurrentUser, DbSession, MemberLace
from backend.app.schemas.lace_instructions import InstructionCreate, InstructionResponse, InstructionUpdate
from backend.app.services import lace_instructions

router = APIRouter()

MAX_INSTRUCTIONS_PER_PAGE = 100


@router.get("/{lace_id}/instructions", response_model=list[InstructionResponse])
async def list_instructions(lace: MemberLace, db: DbSession,
                            limit: int = Query(default=50, ge=1, le=MAX_INSTRUCTIONS_PER_PAGE)):
    return await lace_instructions.list_for_lace(db, lace.id, limit)


@router.post("/{lace_id}/instructions", response_model=InstructionResponse, status_code=status.HTTP_201_CREATED)
async def add_instruction(lace: MemberLace, payload: InstructionCreate, user: CurrentUser, db: DbSession):
    return await lace_instructions.add_from_api(db, lace.id, payload.text, payload.applies_to, user.id)


@router.patch("/{lace_id}/instructions/{instruction_id}", response_model=InstructionResponse)
async def edit_instruction(lace: MemberLace, instruction_id: uuid.UUID, payload: InstructionUpdate, db: DbSession):
    return await lace_instructions.edit(db, lace.id, instruction_id, payload.text, payload.applies_to)


@router.delete("/{lace_id}/instructions/{instruction_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_instruction(lace: MemberLace, instruction_id: uuid.UUID, db: DbSession):
    await lace_instructions.remove(db, lace.id, instruction_id)
