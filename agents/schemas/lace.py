"""Models for the Lace agent: what it knows, and what its tools return.

The Lace keeps its knowledge in the database. These are the shapes that cross
the boundary between the agent and the store the backend implements.
"""

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

from agents.schemas.coercion import LenientModel
from agents.schemas.competition import ProfileSkeleton
from agents.schemas.opportunities import OpportunitySummary

FactTopic = Literal[
    "company",      # who the startup is: name, location, team, stage
    "offer",        # what it sells, features, how it works
    "pricing",
    "customers",    # who buys today, named customers, case studies
    "market",
    "competition",
    "icp",
    "positioning",  # claims, differentiators, messaging
]
FACT_TOPICS: tuple[str, ...] = FactTopic.__args__

FactOrigin = Literal["crawl", "research", "user", "monitor"]
FACT_ORIGINS: tuple[str, ...] = FactOrigin.__args__
Confidence = Literal["high", "medium", "low"]
CONFIDENCES: tuple[str, ...] = Confidence.__args__


class NewFact(BaseModel):
    topic: FactTopic
    claim: str = Field(description="One self-contained sentence")
    source_url: str | None = Field(default=None, description="The page that states it; None for the founder's word")
    confidence: Confidence = "medium"
    origin: FactOrigin = "research"
    replaces_id: str | None = Field(default=None, description="A fact this one supersedes")


class Fact(NewFact):
    id: str
    recorded_at: datetime


class SourcePage(BaseModel):
    """A page the Lace read, kept so prompts can carry a summary instead."""
    url: str
    title: str = ""
    markdown: str


class LaceProfile(BaseModel):
    name: str
    website: str
    startup_name: str | None = None


class ToolResult(BaseModel):
    """What every Lace tool returns.

    `summary` is what the model reads first and must stand on its own; `data`
    carries the detail. A failure is a result too: the model reads the error
    and decides what to do, and the loop keeps running.
    """
    ok: bool
    summary: str
    data: Any = None
    error: str | None = None

    @classmethod
    def success(cls, summary: str, data: Any = None) -> "ToolResult":
        return cls(ok=True, summary=summary, data=data)

    @classmethod
    def failure(cls, error: str) -> "ToolResult":
        return cls(ok=False, summary=error, error=error)


class ExtractedFact(LenientModel):
    topic: FactTopic
    claim: str = Field(description="One self-contained sentence about the startup, in your own words")
    source_url: str = Field(description="The URL of the page above that states it, copied exactly")
    confidence: Confidence = Field(description="high when the page states it outright, low when you inferred it")


class SiteUnderstanding(LenientModel):
    """What onboarding pulls out of the startup's own pages."""
    # Required: models skip optional fields in structured output.
    startup_name: str = Field(description="The company's name as its site gives it")
    facts: list[ExtractedFact] = Field(default_factory=list)
    open_questions: list[str] = Field(
        default_factory=list,
        description="Up to 3 short questions for the founder about what the site leaves unclear",
    )


class OnboardingResult(BaseModel):
    startup_name: str | None
    pages_read: list[str]
    pages_failed: list[str]
    facts_recorded: int
    open_questions: list[str]

    @property
    def site_unreadable(self) -> bool:
        return not self.pages_read


class PagePick(LenientModel):
    urls: list[str] = Field(default_factory=list, description="The chosen URLs, copied exactly, most useful first")


class CompetitorHuntBrief(LenientModel):
    """What the competitor hunt needs, drawn from the Lace's facts: the v1 hunt
    is shaped by competitor archetypes, which a Lace has to sketch first."""
    offer_summary: str = Field(description="Two or three sentences: what the startup sells and to whom")
    target_geographies: list[str] = Field(
        default_factory=list, description="Countries or regions it sells in, when the facts say; else empty")
    profile: ProfileSkeleton = Field(description="The kinds of company that compete for this startup's buyers")


# suggested: found by a search, waiting for the founder to save (tracked) or dismiss it.
CompetitorStatus = Literal["suggested", "tracked", "dismissed"]
COMPETITOR_STATUSES: tuple[str, ...] = CompetitorStatus.__args__
CompetitorOrigin = Literal["found", "founder"]
COMPETITOR_ORIGINS: tuple[str, ...] = CompetitorOrigin.__args__


class CompetitorSummary(BaseModel):
    id: str
    name: str
    website: str
    summary: str | None = None
    origin: CompetitorOrigin
    status: CompetitorStatus



# suggested: found by a search, waiting for the founder to save (target) or dismiss it.
AccountStatus = Literal["suggested", "target", "dismissed"]
ACCOUNT_STATUSES: tuple[str, ...] = AccountStatus.__args__


class AccountSummary(BaseModel):
    id: str
    name: str
    account_type: str
    website: str | None = None
    geo: str | None = None
    trigger: str | None = None
    need: str | None = None
    angle: str | None = None
    fit_strength: str | None = None
    contact_status: str | None = Field(default=None, description="person | organisation | none; unset until contacts were looked for")
    contacts: list[dict] = Field(default_factory=list, description="People to reach: name, title, email, linkedin")
    channels: dict[str, str] = Field(default_factory=dict, description="The organisation's own pages by platform")

class Suggestions(BaseModel):
    """What searches found that the founder has not saved or dismissed yet."""
    competitors: list[CompetitorSummary] = Field(default_factory=list)
    accounts: list[AccountSummary] = Field(default_factory=list)
    opportunities: list[OpportunitySummary] = Field(default_factory=list)

    @property
    def empty(self) -> bool:
        return not (self.competitors or self.accounts or self.opportunities)


class DraftSummary(BaseModel):
    """A message the Lace drafted that waits for the founder to send."""
    id: str
    channel: str
    recipient: str = Field(description="The person's name, else their address")
    company: str
    subject: str | None = None
    body: str


ContactStatus = Literal["person", "organisation", "none"]
CONTACT_STATUSES: tuple[str, ...] = ContactStatus.__args__

OutreachChannel = Literal["email", "linkedin", "x", "instagram", "facebook", "tiktok"]
OUTREACH_CHANNELS: tuple[str, ...] = OutreachChannel.__args__

# Business accounts whose inbound DMs a Lace reads (docs/lace-plan.md, Channels).
InboxPlatform = Literal["instagram", "facebook"]
INBOX_PLATFORMS: tuple[str, ...] = InboxPlatform.__args__

BriefFrequency = Literal["off", "daily", "weekly"]
BRIEF_FREQUENCIES: tuple[str, ...] = BriefFrequency.__args__

# Where a contact came from: the account search's own sources, or a contact search.
ContactSource = Literal["discovery", "contact_search"]
CONTACT_SOURCES: tuple[str, ...] = ContactSource.__args__

# What a Lace's Feed shows the founder it did (docs/lace-ui-plan.md, Feed).
ActivityKind = Literal[
    "brief", "competitors_found", "competitor_moves", "accounts_found", "contacts_found",
    "drafts_ready", "reply_received", "opportunities_found", "job_failed",
]
ACTIVITY_KINDS: tuple[str, ...] = ActivityKind.__args__
# What an activity is about, when it is one thing the founder can open.
ActivityRef = Literal["brief", "outreach"]
ACTIVITY_REFS: tuple[str, ...] = ActivityRef.__args__
