"""Request/response models for the public waitlist and its admin views."""

import uuid
from datetime import date, datetime
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field

Stage = Literal["idea", "pre_revenue", "revenue", "scaling"]
SellsTo = Literal["b2b", "b2c", "both"]
WaitlistStatus = Literal["new", "contacted", "invited", "onboarded"]

EXPECTATIONS_MAX_CHARS = 500
MAX_COUNTRIES = 12


class WaitlistSource(BaseModel):
    """Where the visitor came from: the landing page's UTM tags and referrer."""

    utm_source: str | None = Field(default=None, max_length=100)
    utm_medium: str | None = Field(default=None, max_length=100)
    utm_campaign: str | None = Field(default=None, max_length=100)
    referrer: str | None = Field(default=None, max_length=300)


class WaitlistJoin(BaseModel):
    email: EmailStr = Field(max_length=320)
    consent: Literal[True] = Field(description="Agreed to be contacted about Thalace and to the privacy note")
    source: WaitlistSource = Field(default_factory=WaitlistSource)
    # A field people never see. Bots fill every input; a filled one is a bot.
    nickname: str | None = Field(default=None, max_length=200)


class WaitlistJoined(BaseModel):
    token: str = Field(description="Lets this browser add the optional details; keep it private")
    pilot_spots_left: int


class WaitlistDetails(BaseModel):
    """The optional second step. Fields left out are not changed."""

    name: str | None = Field(default=None, max_length=120)
    company: str | None = Field(default=None, max_length=200)
    role: str | None = Field(default=None, max_length=120)
    stage: Stage | None = None
    sells_to: SellsTo | None = None
    countries: list[Annotated[str, Field(max_length=60)]] | None = Field(default=None, max_length=MAX_COUNTRIES)
    wants_pilot: bool | None = None
    expectations: str | None = Field(default=None, max_length=EXPECTATIONS_MAX_CHARS)
    website: str | None = Field(default=None, max_length=500, description="Their startup's website; a bare host is fine")


class WaitlistSaved(BaseModel):
    wants_pilot: bool
    pilot_spots_left: int


class PilotSpots(BaseModel):
    total: int
    taken: int
    left: int
    starts_on: date = Field(description="When the current pilot cohort starts")


class WaitlistSignupRow(BaseModel):
    """One signup as the admin dashboard sees it."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: str
    name: str | None
    company: str | None
    role: str | None
    stage: Stage | None
    sells_to: SellsTo | None
    countries: list[str]
    wants_pilot: bool
    expectations: str | None
    website: str | None = None
    source: dict
    status: WaitlistStatus
    confirmation_sent_at: datetime | None
    created_at: datetime
    updated_at: datetime


class WaitlistStatusUpdate(BaseModel):
    status: WaitlistStatus


class SignupsOnDay(BaseModel):
    day: date
    signups: int


class WaitlistStats(BaseModel):
    total: int
    last_7_days: int
    pilot: PilotSpots
    by_day: list[SignupsOnDay] = Field(description="Signups per day, oldest first, days without signups included")
    by_stage: dict[str, int] = Field(description="Signups per stage; 'unknown' for those who didn't say")
    by_sells_to: dict[str, int]

