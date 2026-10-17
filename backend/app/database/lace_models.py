"""Tables for the Lace agent: the Lace itself, what it knows, and what it read.

Lace v2 starts its own schema instead of reshaping the v1 workspace tables;
see docs/lace-plan.md. Tables for competitors, accounts, contacts,
opportunities and messages arrive with the phase whose tools first write them.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, String, Text, UUID, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from agents.schemas.lace import FACT_TOPICS, CONFIDENCES, FACT_ORIGINS
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
