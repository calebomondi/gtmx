"""Request/response models for the runs endpoints."""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class RunResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    kind: str
    status: str = Field(description="pending | running | awaiting_input | completed | failed | cancelled")
    workspace_id: uuid.UUID | None = None
    progress: dict | None = None
    error: str | None = None
    created_at: datetime
    started_at: datetime | None = None
    finished_at: datetime | None = None


class RunAnswer(BaseModel):
    answer: str = Field(min_length=1)
