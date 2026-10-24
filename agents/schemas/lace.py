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
    capability: str | None = Field(default=None, description="How we meet their need")
    payoff: str | None = Field(default=None, description="What it gets them")
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


class DocumentSummary(BaseModel):
    """A document the founder shared with the Lace; its text is read with read_document."""
    id: str
    filename: str
    chars: int = Field(description="Length of its extracted text")
    truncated: bool = Field(default=False, description="Only the start of a very long document was kept")


class DraftSummary(BaseModel):
    """A message the Lace drafted that waits for the founder to send."""
    id: str
    channel: str
    recipient: str = Field(description="The person's name, else their address")
    company: str
    subject: str | None = None
    body: str


# What the Lace can save or remove for the founder.
SavedKind = Literal["competitor", "account", "opportunity"]
SAVED_KINDS: tuple[str, ...] = SavedKind.__args__
SavedVerdict = Literal["save", "remove"]


class NamedItem(BaseModel):
    id: str
    name: str


class ItemsChanged(BaseModel):
    """What a change touched, and the ids that matched nothing of the Lace's."""
    changed: list[NamedItem] = Field(default_factory=list)
    missing: list[str] = Field(default_factory=list)


class ContactSummary(BaseModel):
    """A person at one of the Lace's target accounts."""
    id: str
    name: str | None = None
    title: str | None = None
    email: str | None = None
    linkedin: str | None = None
    x: str | None = None
    instagram: str | None = None
    facebook: str | None = None
    tiktok: str | None = None
    company: str
    account_id: str
    approved: bool


class NewContact(BaseModel):
    """A person the founder asked the Lace to add, at a company by name."""
    company: str = Field(min_length=1, max_length=255)
    name: str = Field(min_length=1, max_length=200)
    email: str | None = Field(default=None, max_length=320)
    title: str | None = Field(default=None, max_length=200)
    linkedin: str | None = Field(default=None, max_length=500)
    x: str | None = Field(default=None, max_length=500)
    instagram: str | None = Field(default=None, max_length=500)
    facebook: str | None = Field(default=None, max_length=500)
    tiktok: str | None = Field(default=None, max_length=500)
    website: str | None = Field(default=None, max_length=500)


ContactStatus = Literal["person", "organisation", "none"]
CONTACT_STATUSES: tuple[str, ...] = ContactStatus.__args__

OutreachChannel = Literal["email", "linkedin", "x", "instagram", "facebook", "tiktok"]
OUTREACH_CHANNELS: tuple[str, ...] = OutreachChannel.__args__

# Business accounts whose inbound DMs a Lace reads (docs/lace-plan.md, Channels).
InboxPlatform = Literal["instagram", "facebook"]
INBOX_PLATFORMS: tuple[str, ...] = InboxPlatform.__args__

BriefFrequency = Literal["off", "daily", "weekly"]
BRIEF_FREQUENCIES: tuple[str, ...] = BriefFrequency.__args__
# How often a Lace looks for new opportunities and competitor moves, in hours.
WatchEvery = Literal[6, 12, 24, 168]
WATCH_EVERY_H: tuple[int, ...] = WatchEvery.__args__
DEFAULT_WATCH_EVERY_H = 6

# Something the Lace proposed doing in one of the founder's apps (post, reply,
# add a lead): it waits for the founder's click, then runs or is declined.
AppActionStatus = Literal["proposed", "running", "done", "failed", "declined"]
APP_ACTION_STATUSES: tuple[str, ...] = AppActionStatus.__args__


class ProposedAction(BaseModel):
    """An action in one of the founder's apps, proposed by the Lace for the
    founder to approve. Nothing runs until they do."""
    app: str = Field(max_length=32, description="The app it runs in, e.g. linkedin")
    action: str = Field(max_length=48, description="What it does there, e.g. publish_post")
    title: str = Field(min_length=1, max_length=200, description="What will happen, for the founder: 'Post on LinkedIn'")
    preview: str = Field(default="", max_length=4000, description="What will be posted or written, as the founder sees it")
    arguments: dict = Field(default_factory=dict, description="What the action needs to run")


# Where a contact came from: the account search's own sources, or a contact search.
ContactSource = Literal["discovery", "contact_search", "founder"]
CONTACT_SOURCES: tuple[str, ...] = ContactSource.__args__

# What a Lace's Feed shows the founder it did (docs/lace-ui-plan.md, Feed).
ActivityKind = Literal[
    "brief", "competitors_found", "competitor_moves", "accounts_found", "contacts_found",
    "drafts_ready", "reply_received", "opportunities_found", "job_failed", "app_action",
]
ACTIVITY_KINDS: tuple[str, ...] = ActivityKind.__args__
# What an activity is about, when it is one thing the founder can open.
ActivityRef = Literal["brief", "outreach", "app_action"]
ACTIVITY_REFS: tuple[str, ...] = ActivityRef.__args__
