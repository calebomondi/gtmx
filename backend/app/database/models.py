from __future__ import annotations
import uuid

from datetime import datetime, UTC

from sqlalchemy import BigInteger, Boolean, DateTime, ForeignKey, Integer, String, Text, UUID, UniqueConstraint, false, func
from sqlalchemy.dialects.postgresql import JSONB as JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.app.database.connect import Base


class Workspace(Base):
    __tablename__ = "workspaces"

    # Metadata
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    # Supabase Auth user id (no local users table — Supabase owns identity).
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        nullable=False,
        index=True,
    )

    # User-owned label, seeded with the product/service name at creation time
    # (product_profile.product_name stays the agent's own understanding).
    name: Mapped[str | None] = mapped_column(String(100))
    pinned: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default=false(),
    )

    # Optional grouping: NULL = ungrouped. Membership is preserved on archive
    # so restoring a workspace brings it back into the same project.
    project_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="RESTRICT"),
        nullable=True,
        index=True,
    )
    archived: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default=false(),
    )
    archived_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    # Dates
    date_created: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        server_default=func.now(),
    )
    last_activity: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        server_default=func.now(),
    )

    # Relationships
    project: Mapped["Project | None"] = relationship(back_populates="workspaces")
    product_profile: Mapped["ProductProfile | None"] = relationship(
        back_populates="workspace",
        uselist=False,
        cascade="all, delete-orphan",
    )
    # Tracked competitors accumulate across runs, so this is a plain collection
    # (no uselist=False) and is NOT cascade-deleted from the workspace side --
    # the FK's ondelete="CASCADE" handles it at the database level. The list
    # grows as the competitor agent is re-run, which is the point of a separate
    # table: product_profiles.insights is one JSON blob replaced wholesale and so
    # structurally cannot accumulate.
    competitors: Mapped[list["Competitor"]] = relationship(
        back_populates="workspace",
        cascade="all, delete-orphan",
    )

    @property
    def product_name(self) -> str | None:
        """Agent-derived product/service name for list responses (requires the
        product_profile relationship to be eagerly loaded)."""
        return self.product_profile.product_name if self.product_profile else None


class Project(Base):
    """A user-owned grouping of workspaces (e.g. every product/service from one
    company). Live projects are grouped on /projects into 'Priority' and
    'Other' buckets; archived projects (with their workspaces) live in
    /archive. A project can only be deleted once it has no member workspaces,
    archived or not."""

    __tablename__ = "projects"
    __table_args__ = (
        UniqueConstraint("user_id", "name_key", name="uq_projects_user_name"),
    )

    # Metadata
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    # Supabase Auth user id (no local users table — Supabase owns identity).
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        nullable=False,
        index=True,
    )

    # User-facing label. Always stored Title Case; `name_key` is its lowercased
    # twin so "Acme Corp" / "acme corp" collide on (user_id, name_key).
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    name_key: Mapped[str] = mapped_column(String(100), nullable=False)

    # Priority bucket + order within that bucket. Driven by drag-to-order on
    # /projects (drag across columns flips priority).
    priority: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default=false(),
    )
    position: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default="0",
    )

    archived: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default=false(),
    )
    archived_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    # Dates
    date_created: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        server_default=func.now(),
    )
    last_activity: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        server_default=func.now(),
    )

    # Relationships
    workspaces: Mapped[list[Workspace]] = relationship(back_populates="project")

    @property
    def workspace_count(self) -> int:
        """Live member workspaces (requires workspaces to be loaded)."""
        return sum(1 for w in (self.workspaces or []) if not w.archived)

    @property
    def archived_workspace_count(self) -> int:
        """Archived member workspaces (requires workspaces to be loaded)."""
        return sum(1 for w in (self.workspaces or []) if w.archived)


class ProductProfile(Base):
    __tablename__ = "product_profiles"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    workspace_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )

    product_name: Mapped[str | None] = mapped_column(String(255))
    product_url: Mapped[str | None] = mapped_column(String(2048))
    product_description: Mapped[str | None] = mapped_column(Text)
    intent: Mapped[str | None] = mapped_column(Text)
    problem_solved: Mapped[str | None] = mapped_column(Text)
    how_it_works: Mapped[str | None] = mapped_column(Text)

    target_geo: Mapped[list[str]] = mapped_column(
        JSON,
        nullable=False,
        default=list,
    )

    confirmed: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default=false(),
    )

    # Final agent-run insights (domain/market/competition/ICP/team + offer
    # snapshot) persisted when the discovery run completes, so workspace tabs
    # can render real data after a refresh.
    insights: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    # Relationships
    workspace: Mapped["Workspace"] = relationship(
        back_populates="product_profile"
    )
    features: Mapped[list["ProductFeature"]] = relationship(
        back_populates="product_profile",
        cascade="all, delete-orphan",
    )


class ProductFeature(Base):
    __tablename__ = "product_features"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    product_profile_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("product_profiles.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    differentiator: Mapped[str | None] = mapped_column(Text)

    # Relationships
    product_profile: Mapped["ProductProfile"] = relationship(
        back_populates="features"
    )


class CompetitorRun(Base):
    """DEPRECATED: superseded by `Run` (kind="competitors"); no code reads or
    writes it. The table is dropped by a later migration (expand -> contract).

One invocation of the standalone competitor agent for a workspace.

    A run is a separate entity from its results because the agent is re-runnable
    and each invocation is worth auditing on its own: what it found, when, and
    -- the part that matters most -- how many candidates it DROPPED and why. A
    run that reports 3 competitors from 40 candidates is not a thinner answer,
    it is the agent doing its job, and the UI needs to be able to say so rather
    than showing an empty list and implying failure.
    """

    __tablename__ = "competitor_runs"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    workspace_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # pending -> running -> completed | failed. The agent is triggered by POST
    # and polled, so this is the whole progress surface the client has.
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="pending",
    )
    # Human-readable failure text. Nullable: a completed run has none.
    error: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Counts, written as the run progresses. candidates_seen is how many firms
    # the agent identified before the website check; found is how many survived
    # it; dropped is found's complement. Kept as columns rather than derived so
    # a failed run can still report what it had seen so far.
    candidates_seen: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    found: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    dropped: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    # Why candidates were dropped, as {reason: count}. The dominant reason is
    # expected to be "no public website" -- that is the brief's own filter, not a
    # defect -- so surfacing it prevents a healthy run reading as a lossy one.
    dropped_reasons: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    # Which archetypes from the ideal profile this run hunted with, and the
    # profile's own confidence. Stored so a run stays interpretable after the
    # profile is regenerated by a later discovery run.
    profile_confidence: Mapped[str | None] = mapped_column(String(20), nullable=True)
    archetypes_targeted: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    finished_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        server_default=func.now(),
        nullable=False,
    )

    # Relationships


class Competitor(Base):
    """One verified real company competing with the workspace's offer.

    THE EPISTEMIC INVERSE of IdealCompetitorProfile. The profile is a construct
    -- "the regional incumbent undercutting on price" -- and makes no claim that
    any firm exists, which is why it may be aggressive and needs no sourcing.
    Every row here is the opposite: a claim that a NAMED, REAL company exists and
    does these things. So:

      - `website` is NOT NULL. A firm without a findable public website is not
        tracked. This is enforced by the column, not by the caller, because it
        is the brief's hard filter and the cheapest place to make it unbypassable.
      - `evidence` records which retrieved source backs which field, and
        `unsourced_fields` names the fields research could NOT establish. The UI
        renders the latter as "not found" instead of an empty cell, so a gap is
        never mistaken for a finding. Inventing a plausible weakness is worse
        than admitting there was none, and the schema has to make admitting it
        the cheap option.

    Rows accumulate: re-running the agent appends newly found firms and refreshes
    the ones already known (see `domain_key`), so the list is a growing watch
    list rather than a per-run snapshot.
    """

    __tablename__ = "competitors"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    workspace_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    # Which run first found this competitor. Null for a manually added one, which
    # is exactly how the UI tells agent-found and user-added apart.
    run_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("runs.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    # NOT NULL, per the brief: a competitor must have a public website or not be
    # tracked at all.
    website: Mapped[str] = mapped_column(String(2048), nullable=False)
    # Normalised host (scheme/www stripped) -- the identity of the firm for
    # dedup purposes, because the same rival is reachable at several URLs and
    # under http and https. Unique per workspace, so re-running the agent updates
    # a known firm rather than duplicating it.
    domain_key: Mapped[str] = mapped_column(String(255), nullable=False)

    description: Mapped[str | None] = mapped_column(Text)
    offering: Mapped[str | None] = mapped_column(Text)
    positioning: Mapped[str | None] = mapped_column(Text)
    business_model: Mapped[str | None] = mapped_column(Text)
    pricing: Mapped[str | None] = mapped_column(Text)

    # Who they serve and where they are from. `geography_scope` is the
    # local-vs-foreign verdict the brief asks for and is the one field here that
    # mirrors an archetype's scope vocabulary, so a real firm can be filed
    # against the archetype it turned out to be.
    target_customers: Mapped[str | None] = mapped_column(Text)
    headquarters: Mapped[str | None] = mapped_column(String(255))
    geography_scope: Mapped[str | None] = mapped_column(String(20))

    # How the workspace's own offer compares. Not neutral copy: the point of
    # tracking a rival is the delta against us, so it is stored rather than
    # recomputed per render.
    comparison: Mapped[str | None] = mapped_column(Text)
    # Which archetype of the ideal profile this firm matched, by label. Nullable
    # and free text on purpose -- matching is a judgment, and recording it as a
    # foreign key to a profile that gets regenerated would break on the next run.
    matched_archetype: Mapped[str | None] = mapped_column(String(255))

    strengths: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    weaknesses: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    opportunities: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    notable_customers: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    # [{pain, evidence, source_url}] -- evidence is a quote or close paraphrase,
    # source_url the page it came from. A pain signal with neither is not a pain
    # signal, so both are required by the agent, not by the schema.
    pain_signals: Mapped[list[dict]] = mapped_column(JSON, nullable=False, default=list)
    # What customers actually say about them, in their words, with the same
    # evidence discipline. Separate from pain_signals because a competitor can be
    # well loved and still beat us on price.
    customer_sentiment: Mapped[list[dict]] = mapped_column(JSON, nullable=False, default=list)

    # [{kind, value}] -- kind is website|instagram|tiktok|x|linkedin|github|other.
    # A flat list rather than four nullable columns because these are the same
    # fact in four guises and the UI wants to render them as one row of chips,
    # and because adding a network later should not mean a migration.
    tracking_sources: Mapped[list[dict]] = mapped_column(JSON, nullable=False, default=list)

    # {field_name: [source_url, ...]} -- which retrieved page backs which claim.
    evidence: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    # Field names research could not establish, e.g. ["customer_sentiment",
    # "pricing"]. Present so the UI can say "not found" plainly instead of
    # rendering an empty string that reads as a finding.
    unsourced_fields: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)

    # Free text the USER wrote. Deliberately separate from every field above:
    # this one is not a researched claim and carries no sourcing obligation, and
    # an edit endpoint that could write the researched fields would quietly
    # replace sourced findings with unsourced ones.
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    # "agent" for rows the competitor agent found, "manual" for ones the user
    # added by URL. The agent never overwrites a manual row's provenance.
    source: Mapped[str] = mapped_column(String(20), nullable=False, default="agent")

    first_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        server_default=func.now(),
        nullable=False,
    )
    # Refreshed on every run that re-finds this firm, so the UI can show what is
    # stale. `deep_researched_at` is when the profile fields were last rebuilt,
    # which is the timestamp a monitoring feature would schedule against.
    last_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        server_default=func.now(),
        nullable=False,
    )
    deep_researched_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    # Relationships
    workspace: Mapped["Workspace"] = relationship(back_populates="competitors")

    __table_args__ = (
        # The dedup guarantee. Two runs finding acme.com and https://www.acme.com
        # must produce one row, and the second must update the first rather than
        # fail -- the agent treats a conflict as "already known", not as an error.
        UniqueConstraint("workspace_id", "domain_key", name="uq_competitors_workspace_domain"),
    )

class AccountRun(Base):
    """DEPRECATED: superseded by `Run` (kind="accounts"); no code reads or
    writes it. The table is dropped by a later migration (expand -> contract).

One invocation of the account-discovery agent for a workspace.

    Mirrors CompetitorRun: each run is a separate row so the user can audit why a
    run failed (or why one filled the list and another didn't), and the UI can
    show progress for the in-flight run."""

    __tablename__ = "account_runs"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    workspace_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="pending",
    )
    error: Mapped[str | None] = mapped_column(Text, nullable=True)

    candidates_seen: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    found: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True,
    )
    finished_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC),
        server_default=func.now(),
        nullable=False,
    )



class Account(Base):
    """A target account discovered by the account-discovery agent for outreach.

    A company, or — for consumer offers — a venue/community/event/creator where
    the ICP congregates. `selected` is a user-driven choice to keep this account
    for outreach drafting later; everything else is agent output."""

    __tablename__ = "accounts"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4,
    )
    workspace_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    run_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("runs.id", ondelete="SET NULL"),
        nullable=True, index=True,
    )

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    account_type: Mapped[str] = mapped_column(String(20), nullable=False, default="company")
    website: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    domain: Mapped[str | None] = mapped_column(String(255), nullable=True)
    platform: Mapped[str | None] = mapped_column(String(100), nullable=True)
    venue: Mapped[str | None] = mapped_column(String(255), nullable=True)
    event_date: Mapped[str | None] = mapped_column(String(255), nullable=True)
    member_size: Mapped[str | None] = mapped_column(String(255), nullable=True)

    industry: Mapped[str | None] = mapped_column(String(255), nullable=True)
    size: Mapped[str | None] = mapped_column(String(100), nullable=True)
    geo: Mapped[str | None] = mapped_column(String(255), nullable=True)

    tech_stack: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    recent_news: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    key_contacts: Mapped[list[dict]] = mapped_column(JSON, nullable=False, default=list)
    pain_signals: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    hiring_signals: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    sources: Mapped[list[dict]] = mapped_column(JSON, nullable=False, default=list)
    source_queries: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)

    score: Mapped[float | None] = mapped_column(nullable=True)
    score_breakdown: Mapped[str | None] = mapped_column(Text, nullable=True)
    why_selected: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    why_reach_out: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    trigger_event: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    selected: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=false(),
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC),
        server_default=func.now(),
        nullable=False,
    )

    workspace: Mapped["Workspace"] = relationship()

    __table_args__ = (
        # Same dedup posture as competitors: re-running the agent refreshes a
        # known account instead of doubling it.
        UniqueConstraint("workspace_id", "name", name="uq_accounts_workspace_name"),
    )


class AdminAuditLog(Base):
    """Append-only record of every admin write: who did what to which target,
    with the before/after values. `actor_id` is null for system actions (the
    startup admin bootstrap)."""

    __tablename__ = "admin_audit_log"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    actor_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True, index=True)
    actor_email: Mapped[str | None] = mapped_column(String(320), nullable=True)
    # e.g. "admin.grant", "admin.revoke", "user.suspend", "run.cancel"
    action: Mapped[str] = mapped_column(String(64), nullable=False)
    target_type: Mapped[str] = mapped_column(String(32), nullable=False)
    target_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    before: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    after: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        server_default=func.now(),
        nullable=False,
        index=True,
    )


class Run(Base):
    """One agent run, owned by the server rather than by any connection.

    Discovery runs pause in `awaiting_input` with NO task alive: the LangGraph
    checkpoint holds their state, and an answer resumes them -- even after a
    server restart. Every frame a client should see is appended to run_events,
    so a client that reconnects replays what it missed from its last event id.
    """

    __tablename__ = "runs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    # Discovery creates its workspace mid-run, so this starts null for it.
    workspace_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("workspaces.id", ondelete="SET NULL"), nullable=True, index=True,
    )
    # discovery | competitors | accounts | ... (backend.app.runs.kinds.RunKind)
    kind: Mapped[str] = mapped_column(String(32), nullable=False)
    # pending | running | awaiting_input | completed | failed | cancelled
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending", index=True)
    # The request that started the run, kept for resume and for the admin view.
    input: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    # Kind-specific progress that must survive between segments (e.g. which
    # discovery phases are done) and the final result summary.
    progress: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    # Shown to the user. Never a raw traceback; that goes to the logs.
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), server_default=func.now(), nullable=False,
    )
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), server_default=func.now(),
        onupdate=lambda: datetime.now(UTC), nullable=False,
    )


class RunEvent(Base):
    """An append-only frame emitted by a run. `id` is a global, monotonically
    increasing cursor: a client resumes with "everything after id N"."""

    __tablename__ = "run_events"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    run_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("runs.id", ondelete="CASCADE"), nullable=False, index=True,
    )
    type: Mapped[str] = mapped_column(String(32), nullable=False)
    payload: Mapped[dict] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), server_default=func.now(), nullable=False,
    )


class LlmCall(Base):
    """One LLM call attempt: what it cost and what it was for. Failed attempts
    are recorded too -- they spend tokens. `run_id` is null for calls made
    outside a run. The admin dashboard aggregates this for cost per day/run."""

    __tablename__ = "llm_calls"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    run_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("runs.id", ondelete="SET NULL"), nullable=True, index=True,
    )
    log_label: Mapped[str] = mapped_column(String(120), nullable=False)
    provider: Mapped[str] = mapped_column(String(32), nullable=False)
    model: Mapped[str] = mapped_column(String(100), nullable=False)
    input_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    output_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    seconds: Mapped[float] = mapped_column(nullable=False, default=0.0)
    ok: Mapped[bool] = mapped_column(Boolean, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), server_default=func.now(),
        nullable=False, index=True,
    )


class Signal(Base):
    """One item in a user's feed: something an agent found or did that the user
    should know about (a new competitor, a target account, a finished or failed
    run). Emitted server-side by runs; the user only reads, pins or dismisses."""

    __tablename__ = "signals"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    workspace_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False, index=True,
    )
    run_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("runs.id", ondelete="SET NULL"), nullable=True, index=True,
    )
    # competitor | opportunity | product | market | agent | inbound | outbound
    category: Mapped[str] = mapped_column(String(20), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    entity: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    summary: Mapped[str] = mapped_column(Text, nullable=False, default="")
    body: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Why the user is seeing this.
    reason: Mapped[str] = mapped_column(Text, nullable=False, default="")
    source_url: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    hot: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default=false())
    read: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default=false())
    pinned: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default=false())
    dismissed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default=false())
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), server_default=func.now(),
        nullable=False, index=True,
    )

    workspace: Mapped["Workspace"] = relationship()


class ChatMessage(Base):
    """One turn of a workspace's conversation with its agent team. An
    assistant message is written by the `chat` run that produced it."""

    __tablename__ = "chat_messages"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    workspace_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False, index=True,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    # user | assistant
    role: Mapped[str] = mapped_column(String(16), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    run_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("runs.id", ondelete="SET NULL"), nullable=True, index=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), server_default=func.now(),
        nullable=False, index=True,
    )


class OutreachMessage(Base):
    """One outreach message to a target account: drafted by the agent, edited
    by the user, and sent only on the user's explicit action."""

    __tablename__ = "outreach_messages"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    workspace_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False, index=True,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    account_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("accounts.id", ondelete="SET NULL"), nullable=True, index=True,
    )
    run_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("runs.id", ondelete="SET NULL"), nullable=True, index=True,
    )
    # email | linkedin
    channel: Mapped[str] = mapped_column(String(16), nullable=False)
    recipient_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    recipient_company: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    # The email address for email; null for LinkedIn (sent by the user by hand).
    recipient_address: Mapped[str | None] = mapped_column(String(320), nullable=True)
    subject: Mapped[str | None] = mapped_column(String(255), nullable=True)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    # draft | sending | sent | failed
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="draft", index=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Composio log id of the send, for support/debugging.
    provider_log_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), server_default=func.now(), nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), server_default=func.now(),
        onupdate=lambda: datetime.now(UTC), nullable=False,
    )
