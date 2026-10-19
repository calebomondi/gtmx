"""Request/response models for the Lace endpoints."""

import uuid
from datetime import date, datetime
from zoneinfo import available_timezones
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from agents.schemas.opportunities import OpportunityKind, OpportunityStatus
from agents.schemas.lace import AccountStatus, BriefFrequency, CompetitorOrigin, ContactStatus, InboxPlatform, OutreachChannel, CompetitorStatus, Confidence, FactOrigin, FactTopic


def known_zone(value: str | None) -> str | None:
    if value is not None and value not in available_timezones():
        raise ValueError(f"Unknown timezone: {value}")
    return value


class LaceCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=60, description="What the founder calls their Lace")
    website: str = Field(min_length=3, max_length=2048, description="The startup's website; a bare host is fine")
    timezone: str | None = Field(default=None, max_length=64,
                                 description="The founder's IANA timezone, for the brief; UTC when absent")

    @field_validator("timezone")
    @classmethod
    def _known_zone(cls, value: str | None) -> str | None:
        return known_zone(value)


class LaceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    website: str
    startup_name: str | None = None
    status: str = Field(description="onboarding | active | archived")
    pinned: bool = False
    created_at: datetime


# What a Lace's mascot shows in the sidebar, when something is actually going
# on: working (a turn or job running), or waiting on the founder.
LaceMood = Literal["thinking", "alert"]


class LaceListItem(LaceResponse):
    mood: LaceMood | None = Field(default=None, description="thinking: working now; alert: needs the founder")
    last_active_at: datetime = Field(description="The Lace's latest run, or its creation; the list is newest first")


class LaceUpdate(BaseModel):
    pinned: bool | None = None


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


class AccountContact(BaseModel):
    name: str | None = None
    title: str | None = None
    email: str | None = None
    linkedin: str | None = None


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
    contact_status: ContactStatus | None = Field(
        description="person: someone named is reachable; organisation: only its own channels; none: nothing found")
    contacts: list[AccountContact]
    channels: dict[str, str] = Field(description="The organisation's own pages by platform")
    contacts_checked_at: datetime | None
    first_seen_at: datetime
    last_seen_at: datetime


class AccountUpdateRequest(BaseModel):
    status: AccountStatus = Field(description="target, or dismissed to drop it (a later search won't bring it back)")


class OutreachResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    account_id: uuid.UUID | None
    channel: OutreachChannel
    direction: Literal["outbound", "inbound"]
    status: str = Field(description="draft | sending | sent | failed | bounced | received")
    recipient_name: str | None
    recipient_company: str
    recipient_address: str | None = Field(description="An email address, or a LinkedIn profile URL")
    subject: str | None
    body: str
    thread_id: str | None = Field(description="Set on sent emails, replies and answers in their thread")
    intent: str | None = Field(description="inbound only: how the reply was read, e.g. interested, question")
    error: str | None
    sent_at: datetime | None
    created_at: datetime


class OutreachUpdateRequest(BaseModel):
    subject: str | None = Field(default=None, max_length=255)
    body: str | None = Field(default=None, min_length=1, max_length=20_000)
    recipient_address: str | None = Field(default=None, max_length=2048)
    recipient_name: str | None = Field(default=None, max_length=255)


class ChannelResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    platform: InboxPlatform
    account_id: str
    account_name: str
    synced_until: datetime | None
    created_at: datetime


class ChannelAccount(BaseModel):
    """A business account (Instagram) or Page (Facebook) the founder's connection manages."""
    id: str
    name: str


class ChannelLinkRequest(BaseModel):
    platform: InboxPlatform
    account_id: str = Field(min_length=1, max_length=64)


class OpportunityResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    kind: OpportunityKind
    title: str
    organiser: str | None
    url: str
    deadline: date | None
    event_date: date | None
    location: str | None
    why_it_fits: str
    how_to_act: str
    status: OpportunityStatus
    first_seen_at: datetime


class OpportunityUpdateRequest(BaseModel):
    status: OpportunityStatus


class QuietHours(BaseModel):
    start: int = Field(ge=0, le=23, description="Local hour quiet hours begin")
    end: int = Field(ge=0, le=23, description="Local hour they end (exclusive); may be before start, wrapping midnight")

    @model_validator(mode="after")
    def _not_empty(self) -> "QuietHours":
        if self.start == self.end:
            raise ValueError("Quiet hours must start and end at different hours.")
        return self


class BriefSettings(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    brief_frequency: BriefFrequency
    brief_hour: int = Field(ge=0, le=23, description="Local hour the brief is posted")
    timezone: str = Field(description="IANA timezone name, e.g. Africa/Nairobi")
    brief_email: bool = Field(description="Also email each brief to the founder")
    quiet_hours: QuietHours | None = Field(default=None, description="Local hours in which nothing is emailed")
    email_available: bool = Field(default=False, description="Whether this server can send email at all")
    last_brief_at: datetime | None = None


class BriefSettingsUpdate(BaseModel):
    brief_frequency: BriefFrequency | None = None
    brief_hour: int | None = Field(default=None, ge=0, le=23)
    timezone: str | None = Field(default=None, max_length=64)
    brief_email: bool | None = None
    quiet_hours: QuietHours | None = Field(default=None, description="Quiet hours; null removes them")

    @field_validator("timezone")
    @classmethod
    def _known_zone(cls, value: str | None) -> str | None:
        return known_zone(value)
