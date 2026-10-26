"""Response model for customer-app activity heartbeats."""

from pydantic import BaseModel, Field


class HeartbeatResponse(BaseModel):
    next_beat_s: int = Field(description="Seconds until the client should ping again")
