"""Request/response models for the Lace endpoints."""

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from agents.schemas.lace import AccountStatus, CompetitorOrigin, CompetitorStatus, Confidence, FactOrigin, FactTopic


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


class CompetitorResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    website: str
    summary: str | None = None
    origin: CompetitorOrigin
    status: CompetitorStatus
    first_seen_at: datetime
    last_seen_at: datetime


class CompetitorUpdateRequest(BaseModel):
    status: CompetitorStatus = Field(description="tracked, or dismissed to stop tracking it (a later hunt won't bring it back)")


class AccountTrigger(BaseModel):
    event: str
    source: str | None = None


class AccountCase(BaseModel):
    need: str
    capability: str
    payoff: str
    angle: str | None = None
    strength: str


class AccountResponse(BaseModel):
    id: uuid.UUID
    name: str
    account_type: str
    website: str | None
    geo: str | None
    summary: str | None
    trigger: AccountTrigger | None
    case: AccountCase | None = Field(description="Why this startup suits this account now; none if it could not be made")
    status: AccountStatus
    first_seen_at: datetime
    last_seen_at: datetime


class AccountUpdateRequest(BaseModel):
    status: AccountStatus = Field(description="target, or dismissed to drop it (a later search won't bring it back)")
