"""Tables for the Lace agent: the Lace itself, what it knows, and what it read.

Lace v2 starts its own schema instead of reshaping the v1 workspace tables;
see docs/lace-plan.md. Tables for accounts, contacts, opportunities and
messages arrive with the phase whose tools first write them.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, String, Text, UUID, UniqueConstraint, func, text
from sqlalchemy.dialects.postgresql import JSONB as JSON
from sqlalchemy.orm import Mapped, mapped_column

from agents.schemas.lace import COMPETITOR_ORIGINS, COMPETITOR_STATUSES, CONFIDENCES, FACT_ORIGINS, FACT_TOPICS
from backend.app.database.connect import Base

LACE_STATUSES = ("onboarding", "active", "archived")


def _one_of(column: str, values: tuple[str, ...]) -> str:
    return f"{column} IN ({', '.join(repr(v) for v in values)})"


def _now() -> datetime:
    return datetime.now(UTC)


class Lace(Base):
    """One startup's agent. Its LangGraph thread id is its own id."""

    __tablename__ = "laces"
    __table_args__ = (CheckConstraint(_one_of("status", LACE_STATUSES), name="status"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    # Supabase owns users: indexed, no FK.
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(60), nullable=False)
    website: Mapped[str] = mapped_column(Text, nullable=False)
    # Learned at onboarding; NULL until then.
    startup_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="onboarding",
                                        server_default="onboarding", index=True)
    # The ideal customer profile (agents.schemas.icp.ICP): the Lace's own
    # judgment, so a blob rather than facts. NULL until first defined.
    icp: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    icp_updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False,
                                                 default=_now, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_now,
                                                 server_default=func.now(), onupdate=_now)


class LaceFact(Base):
    """One thing the Lace knows about its startup. A newer fact supersedes an
    old one (superseded_by_id) instead of overwriting it, so the history of
    what the Lace believed, and why, is kept."""

    __tablename__ = "lace_facts"
    __table_args__ = (
        CheckConstraint(_one_of("topic", FACT_TOPICS), name="topic"),
        CheckConstraint(_one_of("confidence", CONFIDENCES), name="confidence"),
        CheckConstraint(_one_of("origin", FACT_ORIGINS), name="origin"),
        # Only the founder's word stands without a page behind it.
        CheckConstraint("source_url IS NOT NULL OR origin = 'user'", name="sourced"),
        Index("ix_lace_facts_lace_id_topic", "lace_id", "topic"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    # Indexed by ix_lace_facts_lace_id_topic, which leads with it.
    lace_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("laces.id", ondelete="CASCADE"), nullable=False)
    topic: Mapped[str] = mapped_column(String(24), nullable=False)
    claim: Mapped[str] = mapped_column(Text, nullable=False)
    source_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    confidence: Mapped[str] = mapped_column(String(8), nullable=False)
    origin: Mapped[str] = mapped_column(String(12), nullable=False)
    superseded_by_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("lace_facts.id", ondelete="SET NULL"), nullable=True, index=True,
    )
    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False,
                                                  default=_now, server_default=func.now(), index=True)


class LaceSource(Base):
    """A page the Lace read, kept whole so prompts carry only a capped copy.
    One row per URL per Lace; re-reading replaces it."""

    __tablename__ = "lace_sources"
    __table_args__ = (UniqueConstraint("lace_id", "url", name="uq_lace_sources_lace_id_url"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    # Indexed by the unique constraint, which leads with it.
    lace_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("laces.id", ondelete="CASCADE"), nullable=False)
    url: Mapped[str] = mapped_column(Text, nullable=False)
    title: Mapped[str] = mapped_column(Text, nullable=False, default="", server_default="")
    content: Mapped[str] = mapped_column(Text, nullable=False)
    # sha256 of content: lets monitoring tell a changed page from a re-read.
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False,
                                                 default=_now, server_default=func.now())


class LaceCompetitor(Base):
    """A real company competing with the Lace's startup. One row per firm per
    Lace, keyed by its host, so a later hunt refreshes rather than duplicates.
    The researched profile is an opaque agent blob; what is filtered or sorted
    on is a column."""

    __tablename__ = "lace_competitors"
    __table_args__ = (
        UniqueConstraint("lace_id", "domain_key", name="uq_lace_competitors_lace_id_domain_key"),
        CheckConstraint(_one_of("status", COMPETITOR_STATUSES), name="status"),
        CheckConstraint(_one_of("origin", COMPETITOR_ORIGINS), name="origin"),
        Index("ix_lace_competitors_lace_id_status", "lace_id", "status"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    # Indexed by the unique constraint and the status index, which lead with it.
    lace_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("laces.id", ondelete="CASCADE"), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    website: Mapped[str] = mapped_column(Text, nullable=False)
    domain_key: Mapped[str] = mapped_column(String(255), nullable=False)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    # The sourced research profile (agents.schemas.competition.CompetitorProfile).
    profile: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    origin: Mapped[str] = mapped_column(String(12), nullable=False, default="found", server_default="found")
    status: Mapped[str] = mapped_column(String(12), nullable=False, default="tracked", server_default="tracked")
    # The hunt that last found it; SET NULL keeps the firm when runs are pruned.
    found_by_run_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("runs.id", ondelete="SET NULL"), nullable=True, index=True)
    first_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False,
                                                    default=_now, server_default=func.now())
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_now,
                                                   server_default=func.now(), index=True)
    # The monitor's baseline between checks (site text hash, news and post URLs
    # already seen): an opaque blob from agents.pipelines.monitor. NULL until
    # the first check, which is how a never-checked firm is found.
    monitor_state: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    last_checked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)


class LaceEvent(Base):
    """Something the Lace should tell its founder about (a job finished, a
    competitor moved) that arrived while it may be busy. The next turn picks
    up every unconsumed event, in order."""

    __tablename__ = "lace_events"
    __table_args__ = (
        Index("ix_lace_events_pending", "lace_id", "created_at", postgresql_where=text("consumed_at IS NULL")),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    lace_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("laces.id", ondelete="CASCADE"), nullable=False, index=True)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False,
                                                 default=_now, server_default=func.now())
    consumed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
