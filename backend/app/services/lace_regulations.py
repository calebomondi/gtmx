"""A Lace's jurisdictions and regulations: where a founder confirmed its
startup is registered and operates, and the laws, regulations, bills and
filing obligations its searches found there, one per source page (per owner;
see lace_competitors for `owner_id` and `member_id`)."""

import re
import uuid
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta

from sqlalchemy import func, or_, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from agents.schemas.lace import ItemsChanged, NamedItem
from agents.schemas.regulations import JURISDICTION_PATTERN, Jurisdiction, Regulation, RegulationStatus, RegulationSummary
from backend.app.database import models
from backend.app.database.lace_models import Lace, LaceRegulation
from backend.app.services import lace_activity, lace_events
from backend.app.services.errors import NotFoundError
from backend.app.services.lace_opportunities import url_key
from backend.app.services.runs import TERMINAL_STATUSES
from config import settings
from data_sources.legislation.mzalendo import HOUSES, BillStatus, bill_key

# The most places one startup operates in that its searches cover.
MAX_PLACES = 10
_CODE = re.compile(JURISDICTION_PATTERN)
# A stage a bill no longer moves on from.
FINAL_STAGES = ("assented", "withdrawn", "lapsed")
# How a moved bill is described on the Feed.
STAGE_NEWS = {
    "published": "was published", "first_reading": "had its first reading", "committee": "went to committee",
    "second_reading": "reached second reading", "whole_house": "went before the Committee of the Whole House",
    "third_reading": "reached third reading", "assented": "was signed into law", "withdrawn": "was withdrawn",
    "lapsed": "lapsed",
}
# Kenya Law's bill links carry the house: /akn/ke/bill/<na|senate>/<date>/.
_KENYA_LAW_BILL = re.compile(r"kenyalaw\.org/akn/ke/bill/(na|senate)/(\d{4})-")
_HOUSE_OF = {code: house for house, code in HOUSES.items()}


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


async def laces_due_for_search(db: AsyncSession) -> list[tuple[uuid.UUID, uuid.UUID]]:
    """(lace_id, user_id) of active Laces with a confirmed jurisdiction whose
    last regulations search is older than the search interval (or never ran)
    and none is running."""
    recent = select(models.Run.id).where(
        models.Run.kind == "lace_regulations", models.Run.lace_id == Lace.id,
        or_(models.Run.status.not_in(TERMINAL_STATUSES),
            models.Run.created_at >= func.now() - timedelta(hours=settings.regulation_search_every_h)))
    rows = await db.execute(select(Lace.id, Lace.user_id).where(
        Lace.status == "active", Lace.jurisdiction_confirmed_at.is_not(None), ~recent.exists()))
    return [(lace_id, user_id) for lace_id, user_id in rows.all()]


async def bills_due_for_check(db: AsyncSession, now: datetime) -> list[LaceRegulation]:
    """Tracked Kenyan bills, on any Lace, still moving and not read within the
    check interval."""
    stale = now - timedelta(hours=settings.bill_check_every_h)
    return list((await db.scalars(select(LaceRegulation).join(Lace, Lace.id == LaceRegulation.lace_id).where(
        Lace.status == "active", LaceRegulation.kind == "bill", LaceRegulation.status == "tracked",
        LaceRegulation.jurisdiction == "KE",
        or_(LaceRegulation.stage.is_(None), LaceRegulation.stage.not_in(FINAL_STAGES)),
        or_(LaceRegulation.last_checked_at.is_(None), LaceRegulation.last_checked_at < stale)))).all())


def houses_of(bills: list[LaceRegulation]) -> list[str]:
    """The houses whose tracker covers these bills: the one in a Kenya Law
    link, else both."""
    houses = set()
    for bill in bills:
        found = _KENYA_LAW_BILL.search(bill.url)
        houses |= {_HOUSE_OF[found[1]]} if found else set(HOUSES)
    return sorted(houses)


def status_of(bill: LaceRegulation, tracker: list[BillStatus]) -> BillStatus | None:
    """The tracker's row for a bill: same name and year, in its house when known."""
    found = _KENYA_LAW_BILL.search(bill.url)
    house = _HOUSE_OF[found[1]] if found else None
    key = bill_key(bill.title, int(found[2]) if found else None)
    for row in tracker:
        if bill_key(row.title, row.year) == key and house in (None, row.house):
            return row
    return None


@dataclass(frozen=True)
class BillMove:
    lace_id: uuid.UUID
    title: str
    stage: str


async def apply_stages(db: AsyncSession, bills: list[LaceRegulation], tracker: list[BillStatus],
                       now: datetime) -> list[BillMove]:
    """Record where each bill now stands and when it was checked. A bill that
    moved goes on its Lace's Feed (a team's) or to the member's chat (theirs
    alone); a first reading of its stage is recorded quietly."""
    moves = []
    for bill in bills:
        bill.last_checked_at = now
        row = status_of(bill, tracker)
        if row is None or row.stage == bill.stage:
            continue
        was, bill.stage, bill.stage_changed_at = bill.stage, row.stage, now
        if was is None:
            continue
        news = f"{bill.title} {STAGE_NEWS[row.stage]}"
        if bill.owner_id is None:
            await lace_activity.add(db, bill.lace_id, "bill_moved", news, bill.why_it_applies or None)
        else:
            await lace_events.add(db, bill.lace_id, f"A bill the member tracks moved: {news} ({bill.url}). "
                                                    "Tell them what it means for us.", bill.owner_id)
        moves.append(BillMove(bill.lace_id, bill.title, row.stage))
    await db.flush()
    return moves
