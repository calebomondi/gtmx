"""A Lace's competitors: the firms its hunts found, kept one per host."""

import uuid
from datetime import UTC, datetime

from sqlalchemy import literal_column, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from agents.schemas.competition import CompetitorProfile
from backend.app.database.lace_models import LaceCompetitor
from backend.app.services.competitors import domain_key, normalize_website
from backend.app.services.errors import NotFoundError


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
    """Save a hunt's profiles. A firm already on file gets the fresh profile;
    its status and origin stay as they were, so a firm the founder dismissed
    is not brought back and one they added stays theirs. Returns (new, refreshed)."""
    new = refreshed = 0
    now = datetime.now(UTC)
    for profile in profiles:
        website = normalize_website(profile.website)
        stmt = insert(LaceCompetitor).values(
            id=uuid.uuid4(), lace_id=lace_id, name=profile.name[:255], website=website,
            domain_key=domain_key(website)[:255], summary=profile.description,
            profile=profile.model_dump(mode="json"), found_by_run_id=run_id, last_seen_at=now,
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
