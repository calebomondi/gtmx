"""Request/response models for the Lace endpoints."""

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from agents.schemas.lace import Confidence, FactOrigin, FactTopic


class LaceCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=60, description="What the founder calls their Lace")
    website: str = Field(min_length=3, max_length=2048, description="The startup's website; a bare host is fine")


class LaceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    website: str
    startup_name: str | None = None
    status: str = Field(description="onboarding | active | archived")
    created_at: datetime


class LaceCreateResponse(BaseModel):
    lace: LaceResponse
    run_id: uuid.UUID = Field(description="The onboarding run: follow it at /runs/{run_id}/events")


class FactResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    topic: FactTopic
    claim: str
    source_url: str | None
    confidence: Confidence
    origin: FactOrigin
    recorded_at: datetime


class LaceMessage(BaseModel):
    role: Literal["founder", "lace"]
    content: str


class LaceMessageRequest(BaseModel):
    text: str = Field(min_length=1, max_length=8000)


class LaceTurnResponse(BaseModel):
    run_id: uuid.UUID = Field(description="The turn: follow it at /runs/{run_id}/events")
