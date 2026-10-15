"""Request/response models for customer-app activity heartbeats."""

import uuid

from pydantic import BaseModel, Field


class HeartbeatRequest(BaseModel):
    workspace_id: uuid.UUID | None = Field(default=None, description="The workspace on screen, if any")


class HeartbeatResponse(BaseModel):
    next_beat_s: int = Field(description="Seconds until the client should ping again")
