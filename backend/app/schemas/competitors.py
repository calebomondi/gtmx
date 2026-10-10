import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


# A tracking source is one reachable identity for a competitor: their site, or
# one of the socials the brief asks for. A flat tagged union rather than four
# nullable columns so the UI renders them as one set of chips and adding a
# network later is not a schema migration.
TrackingSourceKind = str


class TrackingSource(BaseModel):
    kind: str = Field(
        description="website | instagram | tiktok | x | linkedin | github | other"
    )
    value: str = Field(description="The URL or handle on that network")
    # The agent grades every handle it finds, and the grade is the difference
    # between "read off this company's own site" and "a handle that sat next to
    # its name in a directory". Without it in the response the UI would render
    # both as an equally certain link, which is the one distinction that stops a
    # user following the wrong company. Nullable rather than defaulted: a row
    # written before the field existed has none, and inventing a default would
    # present that absence as a medium-confidence guess.
    confidence: str | None = Field(
        default=None, description="high | medium | low, when known"
    )


class SourcedClaim(BaseModel):
    """One evidenced claim about a real company.

    Used for strengths, weaknesses, pain signals and customer sentiment alike,
    rather than one type per category. The categories differ in what the agent is
    allowed to do with them, not in how a claim is stored: all four are factual
    assertions about a named business and all four need the same quote and the
    same page.

    `evidence` and `source_url` are the point of the type. A claim without them is
    a guess, and the brief forbids guesses -- so rather than leaving them nullable
    and relying on a prompt, the agent's own `SourcedFinding` requires `evidence`
    and makes an unsourced claim unrepresentable before it can reach here. That
    requirement is inherited, not re-checked: a row written by hand would still
    pass, which is why `unsourced_fields` exists alongside it.
    """

    text: str = Field(description="The claim, in one line")
    evidence: str = Field(
        description="A quote or close paraphrase from a retrieved source showing "
        "the claim is real"
    )
    source_url: str | None = Field(
        default=None,
        description="The page the evidence came from; null only when the "
        "source could not be linked",
    )


class CompetitorResponse(BaseModel):
    """A verified real company tracked against this workspace's offer.

    The inverse of the ideal competitor profile: where an archetype is a
    construct that names nobody, every field here is a claim about a real firm.
    `unsourced_fields` is the honesty mechanism -- it names what research could
    not establish, so the UI renders "not found" instead of an empty cell that
    would read as a finding.
    """

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    workspace_id: uuid.UUID
    run_id: uuid.UUID | None = Field(
        default=None,
        description="The run that first found this competitor; null when the "
        "user added it by hand",
    )

    name: str
    website: str
    domain_key: str = Field(
        description="Normalised host, the firm's identity for deduplication"
    )

    description: str | None = None
    offering: str | None = None
    positioning: str | None = None
    business_model: str | None = None
    pricing: str | None = None

    target_customers: str | None = Field(
        default=None, description="Whom they serve"
    )
    headquarters: str | None = None
    geography_scope: str | None = Field(
        default=None,
        description="local | regional | global | any -- the local-vs-foreign verdict",
    )

    comparison: str | None = Field(
        default=None, description="How the workspace's own offer compares"
    )
    matched_archetype: str | None = Field(
        default=None,
        description="Which ideal-profile archetype this firm turned out to be",
    )

    strengths: list[SourcedClaim] = Field(default_factory=list)
    weaknesses: list[SourcedClaim] = Field(default_factory=list)
    # Plain strings, unlike the four above, and deliberately so. An opportunity
    # is a claim about US ("we could beat them on price") derived from cited facts
    # about them, not a quote from anyone -- so there is nothing to evidence and
    # typing it as one would ask for a source that does not exist.
    opportunities: list[str] = Field(default_factory=list)
    notable_customers: list[str] = Field(default_factory=list)
    pain_signals: list[SourcedClaim] = Field(
        default_factory=list,
        description="Specific, evidenced complaints. Empty is a legitimate and "
        "common outcome -- it is NOT the same as 'they have no problems'",
    )
    customer_sentiment: list[SourcedClaim] = Field(
        default_factory=list,
        description="What customers say about them overall. Separate from pain "
        "signals because a well-liked firm can still beat us on price",
    )
    tracking_sources: list[TrackingSource] = Field(default_factory=list)

    evidence: dict | None = Field(
        default=None, description="{field_name: [source_url, ...]}"
    )
    unsourced_fields: list[str] = Field(default_factory=list)

    notes: str | None = Field(
        default=None,
        description="Free text the user wrote. Not a researched claim, so it "
        "carries no sourcing obligation",
    )

    source: str = Field(
        default="agent", description="agent | manual"
    )
    first_seen_at: datetime
    last_seen_at: datetime
    deep_researched_at: datetime | None = None


class CompetitorCreateRequest(BaseModel):
    """Manual addition by URL.

    The brief's manual path: give a site, and the agent derives everything else
    (including socials). `name` is optional because the agent can read it off the
    page -- requiring it would push work back onto the user that the system is
    specifically meant to do.
    """

    website: str = Field(
        min_length=1,
        description="The competitor's public website. Required: a firm with no "
        "findable site is not tracked.",
    )
    name: str | None = Field(
        default=None, description="Optional; derived from the site when omitted"
    )
    # Let a user add a rival they know about but the agent has not found yet.
    # Without this the manual path could only ever add rows the agent already
    # agreed with, which defeats the purpose of adding one by hand.
    deep_research: bool = Field(
        default=True,
        description="Whether to run the agent over this site to derive the "
        "remaining fields. False records the row as-is for later research.",
    )


class CompetitorUpdateRequest(BaseModel):
    """A partial edit of user-editable fields.

    Explicitly NOT a full model: research-derived fields (strengths, weaknesses,
    pain signals, evidence) are the agent's to write, and accepting them here
    would let a UI edit quietly overwrite sourced research with something
    invented -- the one failure this whole feature is built to prevent.
    """

    model_config = ConfigDict(extra="forbid")

    name: str | None = None
    website: str | None = None
    target_customers: str | None = None
    headquarters: str | None = None
    geography_scope: str | None = None
    notes: str | None = Field(
        default=None, description="A free-text note kept alongside the profile"
    )


class CompetitorRunResponse(BaseModel):
    """Progress of one competitor-agent invocation.

    Exists because the agent is triggered by POST and polled, and because the
    counts are the honest part of the story: `found` alone would make a run that
    screened 40 firms down to 3 look broken. `dropped_reasons` is dominated by
    "no public website" -- the brief's own filter working as designed -- and the
    UI shows it so a healthy run does not read as a lossy one.
    """

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    workspace_id: uuid.UUID
    status: str = Field(
        description="pending | running | completed | failed"
    )
    error: str | None = None

    candidates_seen: int = 0
    found: int = 0
    dropped: int = 0
    dropped_reasons: dict | None = None

    profile_confidence: str | None = None
    archetypes_targeted: int = 0

    started_at: datetime | None = None
    finished_at: datetime | None = None
    created_at: datetime

    @classmethod
    def from_run(cls, run) -> "CompetitorRunResponse":
        """Built from a `runs` row; the counts live in its `progress`."""
        progress = run.progress or {}
        return cls(
            id=run.id, workspace_id=run.workspace_id, status=run.status, error=run.error,
            started_at=run.started_at, finished_at=run.finished_at, created_at=run.created_at,
            **{k: progress[k] for k in (
                "candidates_seen", "found", "dropped", "dropped_reasons",
                "profile_confidence", "archetypes_targeted",
            ) if progress.get(k) is not None},
        )


class CompetitorRunStartResponse(BaseModel):
    """What POSTing a run returns: the run to poll, plus the current count so
    the UI can say "3 already tracked" without a second request."""

    run: CompetitorRunResponse
    already_tracked: int = Field(
        default=0, description="Competitors on the list before this run"
    )


class CompetitorListResponse(BaseModel):
    competitors: list[CompetitorResponse]
    total: int = Field(description="Rows on the watch list, for pagination UI")
