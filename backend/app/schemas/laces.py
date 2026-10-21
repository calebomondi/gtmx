"""Request/response models for the Lace endpoints."""

import uuid
from datetime import date, datetime
from zoneinfo import available_timezones
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from agents.schemas.lace_ui import BlockAnswer, UiBlock
from agents.schemas.monitor import MoveImportance, MoveKind
from agents.schemas.opportunities import OpportunityKind, OpportunityStatus
from agents.schemas.lace import AccountStatus, ActivityKind, ActivityRef, ContactSource, BriefFrequency, CompetitorOrigin, ContactStatus, InboxPlatform, OutreachChannel, CompetitorStatus, Confidence, FactOrigin, FactTopic


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
    confirmed_at: datetime | None = Field(default=None, description="When the founder confirmed it")


# The founder's verdict on a fact the Lace recorded.
FactVerdict = Literal["confirmed", "retracted"]


class FactReview(BaseModel):
    verdict: FactVerdict


class FactCorrection(BaseModel):
    claim: str = Field(min_length=1, max_length=500, description="The fact as it should read")


class Attachment(BaseModel):
    id: uuid.UUID
    filename: str


class LaceMessage(BaseModel):
    role: Literal["founder", "lace"]
    content: str
    ui: list[UiBlock] | None = Field(default=None, description="Cards and questions shown under a Lace reply")
    documents: list[Attachment] | None = Field(default=None, description="What the founder attached to the message")
    answer: BlockAnswer | None = Field(default=None, description="The question this founder message answered")


class LaceMessageRequest(BaseModel):
    text: str = Field(default="", max_length=8000)
    document_ids: list[uuid.UUID] = Field(default_factory=list, description="Documents uploaded to the Lace first")
    answer: BlockAnswer | None = Field(default=None, description="An answer to a question under the latest reply, "
                                                                 "sent instead of text")

    @model_validator(mode="after")
    def _says_something(self) -> "LaceMessageRequest":
        if self.answer is not None:
            if self.text.strip() or self.document_ids:
                raise ValueError("Send an answer on its own.")
            return self
        if not self.text.strip() and not self.document_ids:
            raise ValueError("Write a message or attach a document.")
        return self


class DocumentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    filename: str
    content_type: str
    size_bytes: int
    truncated: bool = Field(description="Only the start of a very long document was kept")
    created_at: datetime


class JobStartedResponse(BaseModel):
    run_id: uuid.UUID = Field(description="The background job: the Lace reports back when it is done")


class LaceTurnResponse(BaseModel):
    run_id: uuid.UUID = Field(description="The turn: follow it at /runs/{run_id}/events")


class MoveResponse(BaseModel):
    """A material move a tracked competitor made, as the monitor found it."""
    id: uuid.UUID
    competitor_id: uuid.UUID
    competitor_name: str
    kind: MoveKind
    importance: MoveImportance
    title: str
    summary: str
    implication: str | None = Field(default=None, description="What it means for the startup")
    counter_move: str | None = Field(default=None, description="The move to make in response")
    sources: list[str]
    detected_at: datetime


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
    status: Literal["tracked", "dismissed"] = Field(
        description="tracked to save it, or dismissed to drop it (a later hunt won't bring it back)")


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
    status: Literal["target", "dismissed"] = Field(
        description="target to save it, or dismissed to drop it (a later search won't bring it back)")


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
    status: Literal["open", "dismissed"] = Field(description="open to save it, or dismissed: not for us")


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


class BriefResponse(BaseModel):
    """A Lace's latest brief, for the top of its Feed."""
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    created_at: datetime
    posted_at: datetime | None = None
    body: str | None = Field(default=None, description="The Lace's brief, once written")
    state: Literal["writing", "posted", "missed"]


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


class ActivityResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    kind: ActivityKind
    title: str
    summary: str | None = None
    ref_type: ActivityRef | None = None
    ref_id: uuid.UUID | None = None
    created_at: datetime
    read_at: datetime | None = None


class ActivityReadResponse(BaseModel):
    marked: int = Field(description="How many items were unread")


class LaceActivityItem(ActivityResponse):
    """An activity in the feed across all the founder's Laces."""
    lace_id: uuid.UUID
    lace_name: str


class FunnelResponse(BaseModel):
    accounts: int = Field(description="Target accounts on file")
    contacted: int = Field(description="Accounts written to (a message sent)")
    replied: int = Field(description="Accounts that wrote back")
    interested: int = Field(description="Accounts that replied keen, or asking to meet")


class ContactResponse(BaseModel):
    id: uuid.UUID
    account_id: uuid.UUID
    account_name: str
    name: str | None = None
    title: str | None = None
    email: str | None = None
    linkedin: str | None = None
    source: ContactSource
    approved_at: datetime | None = Field(default=None, description="When the founder cleared them for outreach")
    first_seen_at: datetime


class ContactDraftRequest(BaseModel):
    channel: Literal["email", "linkedin"] = Field(description="Write to their email, or a LinkedIn message")
    note: str | None = Field(default=None, max_length=500, description="What the founder wants the message to say")


class ContactApproval(BaseModel):
    approved: bool = Field(description="Clear this person for outreach, or take it back")


class AccountApprovalResponse(BaseModel):
    approved: int = Field(description="How many people at the account were waiting")


# What a search across Laces can find; each opens in its own Lace.
LaceSearchKind = Literal["lace", "fact", "competitor", "account", "contact", "opportunity", "conversation"]


class LaceSearchHit(BaseModel):
    kind: LaceSearchKind
    id: uuid.UUID
    title: str
    subtitle: str | None = None
    lace_id: uuid.UUID
    lace_name: str
