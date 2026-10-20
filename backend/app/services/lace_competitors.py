"""A Lace's competitors: the firms its hunts found, kept one per host."""

import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import literal_column, or_, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from agents.schemas.competition import CompetitorProfile
from agents.schemas.monitor import CompetitorChange
from backend.app.database import models
from backend.app.database.lace_models import Lace, LaceCompetitor, LaceCompetitorMove
from backend.app.services.competitors import domain_key, normalize_website
from backend.app.services.errors import NotFoundError
from backend.app.services.runs import TERMINAL_STATUSES

MOVE_TITLE_CHARS = 200


async def list_for_lace(db: AsyncSession, lace_id: uuid.UUID, status: str, limit: int) -> list[LaceCompetitor]:
    rows = await db.scalars(
        select(LaceCompetitor)
        .where(LaceCompetitor.lace_id == lace_id, LaceCompetitor.status == status)
        .order_by(LaceCompetitor.last_seen_at.desc()).limit(limit)
    )
    return list(rows.all())


async def set_status(db: AsyncSession, lace_id: uuid.UUID, competitor_id: uuid.UUID, status: str) -> LaceCompetitor:
    """404 for a competitor that is not this Lace's."""
    row = await db.scalar(select(LaceCompetitor).where(
        LaceCompetitor.id == competitor_id, LaceCompetitor.lace_id == lace_id))
    if row is None:
        raise NotFoundError("Competitor not found")
    row.status = status
    await db.commit()
    return row


async def list_tracked(db: AsyncSession, lace_id: uuid.UUID, limit: int) -> list[LaceCompetitor]:
    return await list_for_lace(db, lace_id, "tracked", limit)


async def upsert_found(db: AsyncSession, lace_id: uuid.UUID, run_id: uuid.UUID,
                       profiles: list[CompetitorProfile]) -> tuple[int, int]:
    """Save a hunt's profiles. A new firm is a suggestion until the founder
    saves it. A firm already on file gets the fresh profile; its status and
    origin stay as they were, so a firm the founder dismissed is not brought
    back and one they saved stays saved. Returns (new, refreshed)."""
    new = refreshed = 0
    now = datetime.now(UTC)
    for profile in profiles:
        website = normalize_website(profile.website)
        stmt = insert(LaceCompetitor).values(
            id=uuid.uuid4(), lace_id=lace_id, name=profile.name[:255], website=website,
            domain_key=domain_key(website)[:255], summary=profile.description,
            profile=profile.model_dump(mode="json"), found_by_run_id=run_id, last_seen_at=now, status="suggested",
        )
        # Returns whether the row was inserted: xmax is 0 on a row this
        # statement inserted, and set on one it updated.
        stmt = stmt.on_conflict_do_update(
            constraint="uq_lace_competitors_lace_id_domain_key",
            set_={"name": stmt.excluded.name, "summary": stmt.excluded.summary, "profile": stmt.excluded.profile,
                  "found_by_run_id": stmt.excluded.found_by_run_id, "last_seen_at": stmt.excluded.last_seen_at},
        ).returning(literal_column("xmax = 0"))
        if await db.scalar(stmt):
            new += 1
        else:
            refreshed += 1
    return new, refreshed


async def all_domains(db: AsyncSession, lace_id: uuid.UUID) -> list[str]:
    """Every competitor domain on file, tracked or dismissed."""
    return list((await db.scalars(select(LaceCompetitor.domain_key).where(LaceCompetitor.lace_id == lace_id))).all())


async def due_for_check(db: AsyncSession, lace_id: uuid.UUID, limit: int) -> list[LaceCompetitor]:
    """Tracked competitors, never-checked first, then the longest unchecked."""
    rows = await db.scalars(
        select(LaceCompetitor)
        .where(LaceCompetitor.lace_id == lace_id, LaceCompetitor.status == "tracked")
        .order_by(LaceCompetitor.last_checked_at.asc().nulls_first()).limit(limit)
    )
    return list(rows.all())


async def add_moves(db: AsyncSession, lace_id: uuid.UUID, competitor_id: uuid.UUID, run_id: uuid.UUID | None,
                    changes: list[CompetitorChange]) -> None:
    """Keep each material move the monitor found, with its source."""
    db.add_all(LaceCompetitorMove(
        lace_id=lace_id, competitor_id=competitor_id, run_id=run_id, kind=c.kind, importance=c.importance,
        title=c.title[:MOVE_TITLE_CHARS], summary=c.summary, implication=c.implication or None,
        counter_move=c.counter_move or None, sources=[c.source_url] if c.source_url else [],
    ) for c in changes)


async def list_moves(db: AsyncSession, lace_id: uuid.UUID, limit: int) -> list[tuple[LaceCompetitorMove, str]]:
    """The Lace's competitor moves with each competitor's name, newest first."""
    rows = await db.execute(
        select(LaceCompetitorMove, LaceCompetitor.name)
        .join(LaceCompetitor, LaceCompetitor.id == LaceCompetitorMove.competitor_id)
        .where(LaceCompetitorMove.lace_id == lace_id)
        .order_by(LaceCompetitorMove.detected_at.desc()).limit(limit))
    return [(move, name) for move, name in rows.all()]


async def save_check(db: AsyncSession, competitor_id: uuid.UUID, state: dict) -> None:
    row = await db.get(LaceCompetitor, competitor_id)
    if row is not None:  # dismissed and deleted mid-check is fine; the check is just dropped
        row.monitor_state = state
        row.last_checked_at = datetime.now(UTC)


async def laces_due_for_monitoring(db: AsyncSession, max_age: timedelta) -> list[tuple[uuid.UUID, uuid.UUID]]:
    """(lace_id, user_id) of active Laces with a tracked competitor that was
    never checked or is older than `max_age`, and no check already running."""
    in_flight = select(models.Run.lace_id).where(
        models.Run.kind == "lace_monitor", models.Run.status.not_in(TERMINAL_STATUSES), models.Run.lace_id.is_not(None))
    cutoff = datetime.now(UTC) - max_age
    rows = await db.execute(
        select(Lace.id, Lace.user_id).distinct()
        .join(LaceCompetitor, LaceCompetitor.lace_id == Lace.id)
        .where(Lace.status == "active", LaceCompetitor.status == "tracked",
               or_(LaceCompetitor.last_checked_at.is_(None), LaceCompetitor.last_checked_at < cutoff),
               Lace.id.not_in(in_flight))
    )
    return [(lace_id, user_id) for lace_id, user_id in rows.all()]
