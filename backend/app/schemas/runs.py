"""Request/response models for the runs endpoints."""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class RunResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    kind: str
    status: str = Field(description="queued | pending | running | awaiting_input | completed | failed | cancelled")
    user_id: uuid.UUID = Field(description="Who started it (on a shared Lace, which cofounder)")
    owner_id: uuid.UUID | None = Field(default=None, description="Set when it works in that member's private chat")
    workspace_id: uuid.UUID | None = None
    lace_id: uuid.UUID | None = None
    progress: dict | None = None
    error: str | None = None
    created_at: datetime
    started_at: datetime | None = None
    finished_at: datetime | None = None


class RunStepResponse(BaseModel):
    """One progress step a run reported, oldest first."""

    id: int = Field(description="Cursor: pass the last one as `after` to get only newer steps")
    text: str
    created_at: datetime

