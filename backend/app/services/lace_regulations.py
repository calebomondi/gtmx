"""A Lace's jurisdictions and regulations: where a founder confirmed its
startup is registered and operates, and the laws, regulations, bills and
filing obligations its searches found there, one per source page (per owner;
see lace_competitors for `owner_id` and `member_id`)."""

import re
import uuid
from datetime import UTC, date, datetime

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from agents.schemas.lace import ItemsChanged, NamedItem
from agents.schemas.regulations import JURISDICTION_PATTERN, Jurisdiction, Regulation, RegulationStatus, RegulationSummary
from backend.app.database.lace_models import Lace, LaceRegulation
from backend.app.services.errors import NotFoundError
from backend.app.services.lace_opportunities import url_key

# The most places one startup operates in that its searches cover.
MAX_PLACES = 10
_CODE = re.compile(JURISDICTION_PATTERN)


def _date(value: str | None) -> date | None:
    try:
        return date.fromisoformat(value[:10]) if value else None
    except ValueError:
        return None


def jurisdiction_of(lace: Lace) -> Jurisdiction:
    return Jurisdiction(registered_in=lace.registered_in, operates_in=list(lace.operates_in or []),
                        confirmed=lace.jurisdiction_confirmed_at is not None)


async def set_jurisdiction(db: AsyncSession, lace_id: uuid.UUID, registered_in: str | None,
                           operates_in: list[str]) -> Jurisdiction:
    """Record where a founder said the startup is registered and operates, as
    confirmed now. Raises ValueError for anything but ISO 3166 codes."""
    places = list(dict.fromkeys(operates_in))
    bad = [c for c in [registered_in, *places] if c is not None and not _CODE.match(c)]
    if bad:
        raise ValueError(f"Not ISO 3166 codes: {', '.join(bad)}. Use codes like KE, NG or US-DE.")
    if len(places) > MAX_PLACES:
        raise ValueError(f"At most {MAX_PLACES} places it operates in; got {len(places)}.")
    lace = await db.get(Lace, lace_id)
    if lace is None:
        raise NotFoundError("Lace not found")
    lace.registered_in, lace.operates_in = registered_in, places
    lace.jurisdiction_confirmed_at = datetime.now(UTC)
    await db.flush()
    return jurisdiction_of(lace)


def summary(row: LaceRegulation) -> RegulationSummary:
    return RegulationSummary(
        id=str(row.id), kind=row.kind, title=row.title, authority=row.authority, jurisdiction=row.jurisdiction,
        url=row.url, stage=row.stage, in_force_on=row.in_force_on.isoformat() if row.in_force_on else None,
        next_date=row.next_date.isoformat() if row.next_date else None, why_it_applies=row.why_it_applies,
        what_to_do=row.what_to_do, status=row.status,
    )


async def list_for_lace(db: AsyncSession, lace_id: uuid.UUID, status: RegulationStatus, limit: int,
                        owner_id: uuid.UUID | None = None) -> list[LaceRegulation]:
    """Tracked ones by the soonest next date, the rest newest first."""
    query = select(LaceRegulation).where(LaceRegulation.lace_id == lace_id, LaceRegulation.owned_by(owner_id),
                                         LaceRegulation.status == status)
    order = ((LaceRegulation.next_date.asc().nulls_last(), LaceRegulation.last_seen_at.desc()) if status == "tracked"
             else (LaceRegulation.last_seen_at.desc(),))
    return list((await db.scalars(query.order_by(*order).limit(limit))).all())


async def set_status(db: AsyncSession, lace_id: uuid.UUID, ids: list[uuid.UUID], status: RegulationStatus,
                     member_id: uuid.UUID | None = None) -> ItemsChanged:
    """Track or dismiss regulations a member can see; the rest are missing."""
    rows = (await db.scalars(select(LaceRegulation).where(
        LaceRegulation.id.in_(ids), LaceRegulation.lace_id == lace_id, LaceRegulation.seen_by(member_id)))).all()
    for row in rows:
        row.status = status
    await db.flush()
    found = {row.id for row in rows}
    return ItemsChanged(changed=[NamedItem(id=str(r.id), name=r.title) for r in rows],
                        missing=[str(i) for i in ids if i not in found])


async def upsert_found(db: AsyncSession, lace_id: uuid.UUID, run_id: uuid.UUID, found: list[Regulation],
                       owner_id: uuid.UUID | None = None) -> tuple[int, int]:
    """Save a search's regulations. A new one is a suggestion until the
    founder tracks it. One already on file is refreshed and keeps its status,
    so a dismissed one stays dismissed. Returns (new, refreshed)."""
    keys = [url_key(r.url) for r in found]
    known = set((await db.scalars(select(LaceRegulation.url_key).where(
        LaceRegulation.lace_id == lace_id, LaceRegulation.owned_by(owner_id),
        LaceRegulation.url_key.in_(keys)))).all())
    now = datetime.now(UTC)
    for r, key in zip(found, keys):
        stmt = insert(LaceRegulation).values(
            id=uuid.uuid4(), lace_id=lace_id, owner_id=owner_id, kind=r.kind, title=r.title[:500],
            authority=(r.authority or None) and r.authority[:255], jurisdiction=r.jurisdiction, url=r.url,
            url_key=key, stage=r.stage, stage_changed_at=now if r.stage else None, in_force_on=_date(r.in_force_on),
            next_date=_date(r.next_date), why_it_applies=r.why_it_applies, what_to_do=r.what_to_do,
            found_by_run_id=run_id, last_seen_at=now, status="suggested",
        )
        # A bill's stage is the watcher's to move, so a search never sets one back.
        refresh = {c: stmt.excluded[c] for c in ("kind", "title", "authority", "url", "in_force_on", "next_date",
                                                 "why_it_applies", "what_to_do", "found_by_run_id", "last_seen_at")}
        await db.execute(stmt.on_conflict_do_update(constraint="uq_lace_regulations_lace_id_owner_id_url_key",
                                                    set_=refresh))
    refreshed = len(set(keys) & known)
    return len(set(keys)) - refreshed, refreshed
