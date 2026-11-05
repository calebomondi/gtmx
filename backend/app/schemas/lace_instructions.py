"""Standing instructions from a Lace's team, as the API shows and takes them."""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from agents.schemas.lace import INSTRUCTION_CHARS, InstructionScope


class InstructionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    text: str
    applies_to: InstructionScope
    created_by: uuid.UUID | None
    created_at: datetime
    updated_at: datetime | None


class InstructionCreate(BaseModel):
    text: str = Field(min_length=1, max_length=INSTRUCTION_CHARS)
    applies_to: InstructionScope = "everything"


class InstructionUpdate(BaseModel):
    text: str | None = Field(default=None, min_length=1, max_length=INSTRUCTION_CHARS)
    applies_to: InstructionScope | None = None
