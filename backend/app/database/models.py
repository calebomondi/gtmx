from __future__ import annotations
import uuid

from datetime import datetime, UTC

from sqlalchemy import BigInteger, Boolean, CheckConstraint, DateTime, ForeignKey, Index, Integer, String, Text, UUID, UniqueConstraint, false, func, text
from sqlalchemy.dialects.postgresql import JSONB as JSON
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.database.connect import Base


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


class UserQuota(Base):
    """An admin's per-user override of one run kind's daily cap. No row means
    the default from settings applies."""

    __tablename__ = "user_quotas"
    __table_args__ = (UniqueConstraint("user_id", "kind", name="uq_user_quotas_user_id_kind"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    kind: Mapped[str] = mapped_column(String(32), nullable=False)
    daily_cap: Mapped[int] = mapped_column(Integer, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), server_default=func.now(),
        onupdate=lambda: datetime.now(UTC), nullable=False,
    )


class Run(Base):
    """One agent run, owned by the server rather than by any connection.

    Discovery runs pause in `awaiting_input` with NO task alive: the LangGraph
    checkpoint holds their state, and an answer resumes them -- even after a
    server restart. Every frame a client should see is appended to run_events,
    so a client that reconnects replays what it missed from its last event id.
    """

    __tablename__ = "runs"
    __table_args__ = (
        # A Lace's conversation is one checkpoint thread, which takes one writer
        # at a time: at most one unfinished conversation run per Lace, enforced
        # here so two simultaneous messages cannot both start a turn. Background
        # jobs (a competitor hunt) run alongside and are not counted.
        Index("uq_runs_one_active_per_lace", "lace_id", unique=True,
              postgresql_where=text("lace_id IS NOT NULL AND kind IN ('lace_onboarding', 'lace_turn')"
                                    " AND status IN ('pending', 'running', 'awaiting_input')")),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    # v1's workspace, for runs from before Laces. The workspaces table is
    # gone, so no FK; the column goes in a later migration.
    workspace_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True, index=True)
    # Set for Lace runs. SET NULL, not CASCADE: a run is also the billing
    # record of its LLM and API calls, kept after the Lace is gone.
    lace_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("laces.id", ondelete="SET NULL"), nullable=True, index=True,
    )
    # backend.app.runs.kinds.RunKind
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


class ApiCall(Base):
    """One paid external API call (Exa search/contents, a Bright Data scrape).
    Priced per call from settings.api_call_prices in the admin metrics."""

    __tablename__ = "api_calls"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    run_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("runs.id", ondelete="SET NULL"), nullable=True, index=True,
    )
    provider: Mapped[str] = mapped_column(String(32), nullable=False)
    operation: Mapped[str] = mapped_column(String(64), nullable=False)
    seconds: Mapped[float] = mapped_column(nullable=False, default=0.0)
    ok: Mapped[bool] = mapped_column(Boolean, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), server_default=func.now(),
        nullable=False, index=True,
    )


class AppSession(Base):
    """A stretch of active use of the customer app, built from client
    heartbeats. A gap longer than settings.activity_session_gap_s starts a
    new session. Durations only: nothing about what the user looked at."""

    __tablename__ = "app_sessions"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    active_seconds: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    # No longer written, and no FK since the workspaces table is gone; the
    # column goes in a later migration.
    last_workspace_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True, index=True)


class ConnectionIdentity(Base):
    """Who a connected channel account is (an email, a name, an @handle), read
    once from the provider through Composio. Composio holds the tokens and the
    connection itself; this is only the label shown for it."""

    __tablename__ = "connection_identities"

    # Composio's connected-account id.
    connection_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    platform: Mapped[str] = mapped_column(String(32), nullable=False)
    label: Mapped[str] = mapped_column(String(255), nullable=False)
    fetched_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC), server_default=func.now(),
    )


class WaitlistSignup(Base):
    """A person who joined the waitlist on the public landing page. Not a
    Supabase user: they have no account until invited to the pilot."""

    __tablename__ = "waitlist_signups"
    __table_args__ = (
        CheckConstraint("stage IS NULL OR stage IN ('idea', 'pre_revenue', 'revenue', 'scaling')",
                        name="ck_waitlist_signups_stage"),
        CheckConstraint("sells_to IS NULL OR sells_to IN ('b2b', 'b2c', 'both')", name="ck_waitlist_signups_sells_to"),
        CheckConstraint("status IN ('new', 'contacted', 'invited', 'onboarded')", name="ck_waitlist_signups_status"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    # Lowercased; the natural key, so signing up twice updates the same row.
    email: Mapped[str] = mapped_column(String(320), nullable=False, unique=True)
    name: Mapped[str | None] = mapped_column(String(120), nullable=True)
    company: Mapped[str | None] = mapped_column(String(200), nullable=True)
    role: Mapped[str | None] = mapped_column(String(120), nullable=True)
    stage: Mapped[str | None] = mapped_column(String(16), nullable=True)
    sells_to: Mapped[str | None] = mapped_column(String(8), nullable=True)
    countries: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list, server_default="[]")
    wants_pilot: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default=false(), index=True)
    expectations: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Where they came from: utm_source/medium/campaign and the referrer.
    source: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict, server_default="{}")
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="new", server_default="new", index=True)
    # sha256 of a random token returned at signup; lets that browser add the
    # optional details without an account.
    update_token_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    # Salted hash of the signup IP, only for the per-IP rate limit.
    ip_hash: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    consent_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    confirmation_sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), server_default=func.now(), nullable=False, index=True,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), onupdate=lambda: datetime.now(UTC),
        server_default=func.now(), nullable=False,
    )



# Registered with the rest so Base.metadata (migrations, test cleanup) sees them.
from backend.app.database.lace_models import Lace, LaceAccount, LaceActivity, LaceBrief, LaceChannel, LaceCompetitor, LaceContact, LaceDocument, LaceEvent, LaceFact, LaceOpportunity, LaceOutreach, LaceSource  # noqa: E402,F401
