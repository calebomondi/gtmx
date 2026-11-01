"""Where a Lace's startup is registered and operates, and the laws,
regulations, bills and filing obligations found there."""

import uuid
from datetime import date, datetime
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

from agents.schemas.regulations import JURISDICTION_PATTERN, BillStage, RegulationKind, RegulationStatus
from backend.app.services.lace_regulations import MAX_PLACES

Code = Annotated[str, StringConstraints(pattern=JURISDICTION_PATTERN)]


class JurisdictionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    registered_in: str | None
    operates_in: list[str]
    # When a founder confirmed it; nothing is searched until then.
    jurisdiction_confirmed_at: datetime | None


class JurisdictionUpdate(BaseModel):
    registered_in: Code | None = Field(default=None,
                                       description="Where the company is registered, as an ISO 3166 code")
    operates_in: list[Code] = Field(default_factory=list, max_length=MAX_PLACES,
                                   description="Where it has staff, an office or customers, as ISO 3166 codes")


class RegulationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    kind: RegulationKind
    title: str
    authority: str | None
    jurisdiction: str
    url: str
    stage: BillStage | None
    stage_changed_at: datetime | None
    in_force_on: date | None
    next_date: date | None
    why_it_applies: str
    what_to_do: str
    status: RegulationStatus
    first_seen_at: datetime
    last_checked_at: datetime | None


class RegulationUpdateRequest(BaseModel):
    status: Literal["tracked", "dismissed"] = Field(description="tracked to watch it, or dismissed: not for us")
