"""The closed pilot: whether it is invite-only, and its guest list for admins."""

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field

PilotSource = Literal["admin", "waitlist"]
MAX_EMAILS_PER_ADD = 100


class PilotStatus(BaseModel):
    invite_only: bool = Field(description="Only people let in may use the app")


class PilotAccessRow(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: str
    source: PilotSource
    granted_by_email: str | None
    created_at: datetime
    signed_up: bool = Field(default=False, description="An account exists for this email")


class PilotAccessAdd(BaseModel):
    emails: list[EmailStr] = Field(min_length=1, max_length=MAX_EMAILS_PER_ADD)


class PilotAccessAdded(BaseModel):
    added: int = Field(description="New emails; ones already let in are skipped")
