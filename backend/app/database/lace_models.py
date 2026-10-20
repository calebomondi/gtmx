"""Tables for the Lace agent: the Lace itself, what it knows, and what it read.

Lace v2 starts its own schema instead of reshaping the v1 workspace tables;
see docs/lace-plan.md.
"""

from __future__ import annotations

import uuid
from datetime import UTC, date, datetime

from sqlalchemy import Boolean, CheckConstraint, Date, DateTime, Float, Integer, SmallInteger, ForeignKey, Index, String, Text, UUID, UniqueConstraint, false, func, text
from sqlalchemy.dialects.postgresql import JSONB as JSON
from sqlalchemy.orm import Mapped, mapped_column

from agents.schemas.opportunities import OPPORTUNITY_KINDS, OPPORTUNITY_STATUSES
from agents.schemas.lace import ACCOUNT_STATUSES, ACTIVITY_KINDS, ACTIVITY_REFS, CONTACT_SOURCES, BRIEF_FREQUENCIES, CONTACT_STATUSES, INBOX_PLATFORMS, OUTREACH_CHANNELS, COMPETITOR_ORIGINS, COMPETITOR_STATUSES, CONFIDENCES, FACT_ORIGINS, FACT_TOPICS
from backend.app.database.connect import Base

LACE_STATUSES = ("onboarding", "active", "archived")


def _one_of(column: str, values: tuple[str, ...]) -> str:
    return f"{column} IN ({', '.join(repr(v) for v in values)})"


def _now() -> datetime:
    return datetime.now(UTC)


class Lace(Base):
    """One startup's agent. Its LangGraph thread id is its own id."""

    __tablename__ = "laces"
    __table_args__ = (
        CheckConstraint(_one_of("status", LACE_STATUSES), name="status"),
        CheckConstraint(_one_of("brief_frequency", BRIEF_FREQUENCIES), name="brief_frequency"),
        CheckConstraint("brief_hour BETWEEN 0 AND 23", name="brief_hour"),
        # Quiet hours are a window, so both ends or neither, and not empty.
        CheckConstraint("(quiet_start IS NULL) = (quiet_end IS NULL)", name="quiet_hours_paired"),
        CheckConstraint("quiet_start BETWEEN 0 AND 23 AND quiet_end BETWEEN 0 AND 23 AND quiet_start <> quiet_end",
                        name="quiet_hours_range"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    # Supabase owns users: indexed, no FK.
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(60), nullable=False)
    website: Mapped[str] = mapped_column(Text, nullable=False)
    # Learned at onboarding; NULL until then.
    startup_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="onboarding",
                                        server_default="onboarding", index=True)
    # Shown first in the founder's sidebar.
    pinned: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default=false())
    # The ideal customer profile (agents.schemas.icp.ICP): the Lace's own
    # judgment, so a blob rather than facts. NULL until first defined.
    icp: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    icp_updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # The brief: how often, at what local hour, in which timezone (IANA name).
    brief_frequency: Mapped[str] = mapped_column(String(8), nullable=False, default="daily", server_default="daily")
    brief_hour: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=8, server_default="8")
    timezone: Mapped[str] = mapped_column(String(64), nullable=False, default="UTC", server_default="UTC")
    brief_email: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default=false())
    # Local hours [start, end) in which nothing is emailed; may wrap midnight.
    quiet_start: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)
    quiet_end: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)
    # When the last brief was due, whether or not there was news for it.
    last_brief_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
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
    # The founder's review: confirmed it, or said it is wrong (retracted facts
    # drop out of what the Lace knows but stay on record).
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    retracted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
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


class LaceActivity(Base):
    """Something the Lace did or found, shown to the founder in its Feed.
    Written in the same transaction as the result it reports. Not the same as
    a LaceEvent, which is an update queued for the Lace itself to read."""

    __tablename__ = "lace_activity"
    __table_args__ = (
        CheckConstraint(_one_of("kind", ACTIVITY_KINDS), name="kind"),
        CheckConstraint(f"ref_type IS NULL OR {_one_of('ref_type', ACTIVITY_REFS)}", name="ref_type"),
        CheckConstraint("(ref_type IS NULL) = (ref_id IS NULL)", name="ref_paired"),
        Index("ix_lace_activity_lace_id_created_at", "lace_id", "created_at"),
        Index("ix_lace_activity_unread", "lace_id", postgresql_where=text("read_at IS NULL")),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    # Indexed by the created_at index, which leads with it.
    lace_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("laces.id", ondelete="CASCADE"), nullable=False)
    kind: Mapped[str] = mapped_column(String(24), nullable=False)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    # The one thing it is about, when there is one (a reply, a brief); not a
    # foreign key, since it may point at different tables.
    ref_type: Mapped[str | None] = mapped_column(String(16), nullable=True)
    ref_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False,
                                                 default=_now, server_default=func.now())
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


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


FIT_STRENGTHS = ("strong", "moderate", "weak")


class LaceAccount(Base):
    """A target account for the Lace's startup: a company (or a community,
    event or creator for consumer offers) with a current trigger. One row per
    `key` (its domain, or its name when it has no site) per Lace, so a later
    search refreshes rather than duplicates. Discovery's record and the fit
    case are agent blobs; what is sorted or filtered on is a column."""

    __tablename__ = "lace_accounts"
    __table_args__ = (
        UniqueConstraint("lace_id", "key", name="uq_lace_accounts_lace_id_key"),
        CheckConstraint(_one_of("status", ACCOUNT_STATUSES), name="status"),
        CheckConstraint(f"fit_strength IS NULL OR {_one_of('fit_strength', FIT_STRENGTHS)}", name="fit_strength"),
        CheckConstraint(f"contact_status IS NULL OR {_one_of('contact_status', CONTACT_STATUSES)}",
                        name="contact_status"),
        Index("ix_lace_accounts_lace_id_status", "lace_id", "status"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    # Indexed by the unique constraint and the status index, which lead with it.
    lace_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("laces.id", ondelete="CASCADE"), nullable=False)
    key: Mapped[str] = mapped_column(String(255), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    account_type: Mapped[str] = mapped_column(String(16), nullable=False)
    website: Mapped[str | None] = mapped_column(Text, nullable=True)
    geo: Mapped[str | None] = mapped_column(String(120), nullable=True)
    score: Mapped[float | None] = mapped_column(Float, nullable=True)
    fit_strength: Mapped[str | None] = mapped_column(String(12), nullable=True)
    status: Mapped[str] = mapped_column(String(12), nullable=False, default="target", server_default="target")
    # Someone there asked to stop: no more drafts or sends to it.
    do_not_contact: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default=false())
    # person | organisation | none: whether someone named can be reached. Set
    # from discovery's own contacts, then by a contact search, which also sets
    # contacts_checked_at (NULL: the search never ran for it).
    contact_status: Mapped[str | None] = mapped_column(String(16), nullable=True)
    contacts_checked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # agents.schemas.accounts.AccountRecord and AccountFit.
    record: Mapped[dict] = mapped_column(JSON, nullable=False)
    fit: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    found_by_run_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("runs.id", ondelete="SET NULL"), nullable=True, index=True)
    first_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False,
                                                    default=_now, server_default=func.now())
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_now,
                                                   server_default=func.now(), index=True)


OUTREACH_DIRECTIONS = ("outbound", "inbound")
# outbound: draft | sending | sent | failed | bounced. inbound: received | bounced.
class LaceContact(Base):
    """A person at one of the Lace's target accounts, for the founder's
    Contacts. One row per person per Lace, keyed by email, else LinkedIn URL,
    else name (services.lace_contacts.contact_key); the account record keeps
    its own copy for the agents, which read the record."""

    __tablename__ = "lace_contacts"
    __table_args__ = (
        UniqueConstraint("lace_id", "key", name="uq_lace_contacts_lace_id_key"),
        CheckConstraint(_one_of("source", CONTACT_SOURCES), name="source"),
        CheckConstraint("email IS NOT NULL OR linkedin IS NOT NULL OR name IS NOT NULL", name="identified"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    # Indexed by the unique constraint, which leads with it.
    lace_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("laces.id", ondelete="CASCADE"), nullable=False)
    account_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("lace_accounts.id", ondelete="CASCADE"),
                                                  nullable=False, index=True)
    key: Mapped[str] = mapped_column(String(320), nullable=False)
    name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    title: Mapped[str | None] = mapped_column(String(200), nullable=True)
    email: Mapped[str | None] = mapped_column(String(320), nullable=True)
    linkedin: Mapped[str | None] = mapped_column(Text, nullable=True)
    source: Mapped[str] = mapped_column(String(16), nullable=False)
    # The founder cleared this person for outreach: nothing is drafted to
    # anyone until then.
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    first_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False,
                                                    default=_now, server_default=func.now())
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_now,
                                                   server_default=func.now())


OUTREACH_STATUSES = ("draft", "sending", "sent", "failed", "bounced", "received")


class LaceOutreach(Base):
    """One message in a Lace's outreach: a draft the Lace wrote, what the
    founder sent, or a reply that came back. Sending is always the founder's
    own action; the Lace only drafts."""

    __tablename__ = "lace_outreach"
    __table_args__ = (
        CheckConstraint(_one_of("channel", OUTREACH_CHANNELS), name="channel"),
        CheckConstraint(_one_of("direction", OUTREACH_DIRECTIONS), name="direction"),
        CheckConstraint(_one_of("status", OUTREACH_STATUSES), name="status"),
        Index("ix_lace_outreach_lace_id_status", "lace_id", "status"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    # Indexed by the status index, which leads with it.
    lace_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("laces.id", ondelete="CASCADE"), nullable=False)
    # Supabase owns users: indexed, no FK. Daily send caps count by it.
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    account_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("lace_accounts.id", ondelete="SET NULL"), nullable=True, index=True)
    run_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("runs.id", ondelete="SET NULL"), nullable=True, index=True)
    channel: Mapped[str] = mapped_column(String(16), nullable=False)
    direction: Mapped[str] = mapped_column(String(8), nullable=False, default="outbound", server_default="outbound")
    # The provider's thread (Gmail threadId): ties replies to what was sent.
    thread_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    provider_message_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    # Composio log id of the send, for support/debugging.
    provider_log_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    recipient_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    recipient_company: Mapped[str] = mapped_column(String(255), nullable=False, default="", server_default="")
    # An email address, or the profile or page URL for any other channel.
    recipient_address: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    subject: Mapped[str | None] = mapped_column(String(255), nullable=True)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="draft", server_default="draft")
    # inbound: how the reply was read (agents.schemas.outreach.ReplyIntent).
    intent: Mapped[str | None] = mapped_column(String(24), nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False,
                                                 default=_now, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_now,
                                                 server_default=func.now(), onupdate=_now)


class LaceChannel(Base):
    """A founder's Instagram business account or Facebook Page, linked to the
    Lace that reads its inbound DMs. One Lace per account, so every DM has an
    owner; the founder chooses which."""

    __tablename__ = "lace_channels"
    __table_args__ = (
        UniqueConstraint("platform", "account_id", name="uq_lace_channels_platform_account_id"),
        CheckConstraint(_one_of("platform", INBOX_PLATFORMS), name="platform"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    lace_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("laces.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    platform: Mapped[str] = mapped_column(String(16), nullable=False)
    # The Instagram business account id, or the Facebook Page id.
    account_id: Mapped[str] = mapped_column(String(64), nullable=False)
    account_name: Mapped[str] = mapped_column(String(255), nullable=False, default="", server_default="")
    # Newest message time seen, so a sync only reads conversations updated since.
    synced_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False,
                                                 default=_now, server_default=func.now())


class LaceOpportunity(Base):
    """A place to showcase, a buyer to sell to, or a partner, found for the
    Lace's startup. One row per source page per Lace; a later search refreshes
    it and keeps the founder's dismissal. Deadlines and dates are real dates,
    so closed ones are filtered and the soonest sorted first."""

    __tablename__ = "lace_opportunities"
    __table_args__ = (
        UniqueConstraint("lace_id", "url_key", name="uq_lace_opportunities_lace_id_url_key"),
        CheckConstraint(_one_of("kind", OPPORTUNITY_KINDS), name="kind"),
        CheckConstraint(_one_of("status", OPPORTUNITY_STATUSES), name="status"),
        Index("ix_lace_opportunities_lace_id_status_deadline", "lace_id", "status", "deadline"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    # Indexed by the unique constraint and the status index, which lead with it.
    lace_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("laces.id", ondelete="CASCADE"), nullable=False)
    kind: Mapped[str] = mapped_column(String(16), nullable=False)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    organiser: Mapped[str | None] = mapped_column(String(255), nullable=True)
    url: Mapped[str] = mapped_column(Text, nullable=False)
    # The url without scheme, www or trailing slash: the page's identity for dedup.
    url_key: Mapped[str] = mapped_column(String(1024), nullable=False)
    deadline: Mapped[date | None] = mapped_column(Date, nullable=True)
    event_date: Mapped[date | None] = mapped_column(Date, nullable=True, index=True)
    location: Mapped[str | None] = mapped_column(String(255), nullable=True)
    why_it_fits: Mapped[str] = mapped_column(Text, nullable=False, default="", server_default="")
    how_to_act: Mapped[str] = mapped_column(Text, nullable=False, default="", server_default="")
    status: Mapped[str] = mapped_column(String(12), nullable=False, default="open", server_default="open")
    found_by_run_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("runs.id", ondelete="SET NULL"), nullable=True, index=True)
    first_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False,
                                                    default=_now, server_default=func.now())
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_now,
                                                   server_default=func.now(), index=True)


class LaceBrief(Base):
    """One brief: the digest it was written from, and the Lace's own words
    once posted in the conversation (NULL until then)."""

    __tablename__ = "lace_briefs"
    __table_args__ = (Index("ix_lace_briefs_lace_id_created_at", "lace_id", "created_at"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    # Indexed by the created_at index, which leads with it.
    lace_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("laces.id", ondelete="CASCADE"), nullable=False)
    digest: Mapped[str] = mapped_column(Text, nullable=False)
    body: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False,
                                                 default=_now, server_default=func.now())
    posted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    emailed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)


class LaceDocument(Base):
    """A document the founder shared with the Lace (a deck, a one-pager, a
    customer list), kept as the text extracted from it. The file itself is
    not kept: the Lace only ever reads the text."""

    __tablename__ = "lace_documents"
    __table_args__ = (Index("ix_lace_documents_lace_id_created_at", "lace_id", "created_at"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    # Indexed by the created_at index, which leads with it.
    lace_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("laces.id", ondelete="CASCADE"), nullable=False)
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    content_type: Mapped[str] = mapped_column(String(127), nullable=False)
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    # The text was cut to settings.lace_document_max_chars.
    truncated: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default=false())
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False,
                                                 default=_now, server_default=func.now())
