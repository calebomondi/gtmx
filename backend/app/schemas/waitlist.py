"""Request/response models for the public waitlist."""

from typing import Annotated, Literal

from pydantic import BaseModel, EmailStr, Field

Stage = Literal["idea", "pre_revenue", "revenue", "scaling"]
SellsTo = Literal["b2b", "b2c", "both"]

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
    consent: Literal[True] = Field(description="Agreed to be contacted about GTMX and to the privacy note")
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


class WaitlistSaved(BaseModel):
    wants_pilot: bool
    pilot_spots_left: int


class PilotSpots(BaseModel):
    total: int
    taken: int
    left: int
