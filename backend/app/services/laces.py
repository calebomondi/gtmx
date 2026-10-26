"""Laces: create one, find the user's own, archive, restore or delete one,
and read what it knows."""

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import Select, and_, delete, exists, func, literal_column, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.database.lace_models import (
    Lace,
    LaceAccount,
    LaceActivity,
    LaceCompetitor,
    LaceFact,
    LaceMember,
    LaceOpportunity,
    LaceOutreach,
)
from backend.app.database.models import Run
from backend.app.schemas.laces import FactVerdict, LaceMood
from backend.app.services.runs import TERMINAL_STATUSES
from backend.app.services.competitors import checked_website, domain_key
from backend.app.services import connections as connection_service
from backend.app.services import lace_members, website_check
from backend.app.services import limits
from backend.app.services.errors import ConflictError, InvalidInputError, NotFoundError
from config import settings


async def create(db: AsyncSession, user_id: uuid.UUID, name: str, website: str,
                 timezone: str | None = None) -> Lace:
    name = name.strip()
    if not name:
        raise InvalidInputError("Give your Lace a name.")
    website = checked_website(website)
    domain = domain_key(website)
    if await lace_members.lace_for_domain(db, domain) is not None:
        raise _taken(domain)
    await _ensure_room(db, user_id)
    if not await website_check.readable(website):
        raise InvalidInputError(f"We couldn't open {domain}. Check that the website address is right, then try again.")
    # Checked before the insert, so a refused onboarding leaves no Lace behind.
    await limits.ensure_can_start(db, user_id, "lace_onboarding")
    lace = Lace(user_id=user_id, name=name, website=website, domain=domain, timezone=timezone or "UTC")
    db.add(lace)
    try:
        await db.flush()
    except IntegrityError:  # made at the same moment by someone else
        await db.rollback()
        raise _taken(domain) from None
    lace_members.add_owner(db, lace)
    await db.commit()
    return lace


def _taken(domain: str) -> ConflictError:
    return ConflictError(f"{domain} already has a Lace on Thalace. Ask its owner to invite you, or ask to join it.")


async def _ensure_room(db: AsyncSession, user_id: uuid.UUID) -> None:
    """Archived Laces don't count towards the cap."""
    live = await db.scalar(select(func.count()).select_from(Lace).where(
        Lace.user_id == user_id, Lace.status != "archived"))
    if live >= settings.max_laces_per_user:
        raise ConflictError(f"You can have up to {settings.max_laces_per_user} Laces.")


async def _ensure_idle(db: AsyncSession, lace: Lace) -> None:
    """Refuses while any run of the Lace's is unfinished: a run would keep
    writing to a Lace that was archived or deleted under it."""
    if await db.scalar(select(exists().where(Run.lace_id == lace.id, Run.status.not_in(TERMINAL_STATUSES)))):
        raise ConflictError(f"{lace.name} is still working. Try again when it has finished.")


async def archive(db: AsyncSession, lace: Lace) -> Lace:
    """Out of the sidebar, the Feed and the scheduled work; kept whole."""
    await _ensure_idle(db, lace)
    lace.status = "archived"
    await db.commit()
    return lace


async def restore(db: AsyncSession, lace: Lace) -> Lace:
    """Back as it was: active if it finished onboarding, else still onboarding."""
    if lace.status != "archived":
        return lace
    await _ensure_room(db, lace.user_id)
    onboarded = await db.scalar(select(exists().where(
        Run.lace_id == lace.id, Run.kind == "lace_onboarding", Run.status == "completed")))
    lace.status = "active" if onboarded else "onboarding"
    await db.commit()
    return lace


async def delete_lace(db: AsyncSession, lace: Lace) -> None:
    """Gone with everything under it, its own app accounts revoked. Its runs
    stay, unlinked, as the record of what they cost."""
    await _ensure_idle(db, lace)
    entity = connection_service.lace_entity(lace.id)
    await db.delete(lace)
    await db.commit()
    await connection_service.remove_all(entity)


async def prepare_onboarding_retry(db: AsyncSession, lace: Lace) -> None:
    """Clears what a failed onboarding saved, so reading the site again
    doesn't record its facts twice. Only for a Lace that never finished."""
    if lace.status != "onboarding":
        raise ConflictError(f"{lace.name} has already read your site.")
    await _ensure_idle(db, lace)
    await db.execute(delete(LaceFact).where(LaceFact.lace_id == lace.id, LaceFact.origin == "crawl"))
    await db.commit()


@dataclass(frozen=True)
class LaceSummary:
    lace: Lace
    # The user's place on it: their role, their pin.
    member: LaceMember
    mood: LaceMood | None
    last_active_at: datetime


async def list_for_user(db: AsyncSession, user_id: uuid.UUID, limit: int) -> list[LaceSummary]:
    """The Laces the user is on, most recently active first, each with its mood:
    thinking while a run is unfinished, alert while something waits on the
    founder (a draft to send, a reply not yet read, activity not yet seen, a
    suggestion to save or dismiss)."""
    working = exists().where(Run.lace_id == Lace.id, Run.status.not_in(TERMINAL_STATUSES))
    waiting = or_(
        exists().where(LaceOutreach.lace_id == Lace.id, or_(
            and_(LaceOutreach.direction == "outbound", LaceOutreach.status == "draft"),
            and_(LaceOutreach.direction == "inbound", LaceOutreach.status == "received", LaceOutreach.intent.is_(None)),
        )),
        exists().where(LaceActivity.lace_id == Lace.id, LaceActivity.read_at.is_(None)),
        *(exists().where(model.lace_id == Lace.id, model.team(), model.status == "suggested")
          for model in (LaceCompetitor, LaceAccount, LaceOpportunity)),
    )
    last_run = select(func.max(Run.created_at)).where(Run.lace_id == Lace.id).correlate(Lace).scalar_subquery()
    last_active = func.coalesce(last_run, Lace.created_at)
    rows = await db.execute(
        select(Lace, LaceMember, working.label("working"), waiting.label("waiting"),
               last_active.label("last_active_at"))
        .join(LaceMember, and_(LaceMember.lace_id == Lace.id, LaceMember.user_id == user_id,
                               LaceMember.status == "active"))
        .where(Lace.status != "archived")
        .order_by(last_active.desc()).limit(limit)
    )
    return [LaceSummary(lace, member, "thinking" if busy else "alert" if needs else None, active)
            for lace, member, busy, needs, active in rows.all()]


async def list_archived(db: AsyncSession, user_id: uuid.UUID, limit: int) -> list[tuple[Lace, LaceMember]]:
    """The archived Laces the user is on, most recently changed first."""
    rows = await db.execute(
        select(Lace, LaceMember)
        .join(LaceMember, and_(LaceMember.lace_id == Lace.id, LaceMember.user_id == user_id,
                               LaceMember.status == "active"))
        .where(Lace.status == "archived").order_by(Lace.updated_at.desc()).limit(limit))
    return [(lace, member) for lace, member in rows.all()]


async def set_pinned(db: AsyncSession, member: LaceMember, pinned: bool) -> None:
    """Pin or unpin a Lace in one person's sidebar."""
    member.pinned = pinned
    await db.commit()


def current_facts_query(lace_id: uuid.UUID, topic: str | None, limit: int) -> Select[tuple[LaceFact]]:
    """A Lace's current facts (superseded and retracted ones hidden), newest first."""
    query = (
        select(LaceFact)
        .where(LaceFact.lace_id == lace_id, LaceFact.superseded_by_id.is_(None), LaceFact.retracted_at.is_(None))
        .order_by(LaceFact.recorded_at.desc()).limit(limit)
    )
    return query if topic is None else query.where(LaceFact.topic == topic)


async def list_facts(db: AsyncSession, lace_id: uuid.UUID, topic: str | None, limit: int) -> list[LaceFact]:
    return list((await db.scalars(current_facts_query(lace_id, topic, limit))).all())


def watch_interval():
    """Each Lace's watch interval as an SQL interval, for queries over Laces."""
    return Lace.watch_every_h * literal_column("interval '1 hour'")


async def update_brief_settings(db: AsyncSession, lace: Lace, changes: dict) -> Lace:
    """Apply the fields present in `changes`. A None setting is ignored, except
    `quiet_hours`, where None removes them."""
    for field in ("brief_frequency", "brief_hour", "timezone", "brief_email", "watch_every_h"):
        if changes.get(field) is not None:
            setattr(lace, field, changes[field])
    if "quiet_hours" in changes:
        quiet = changes["quiet_hours"] or {}
        lace.quiet_start, lace.quiet_end = quiet.get("start"), quiet.get("end")
    await db.commit()
    return lace


async def _current_fact(db: AsyncSession, lace_id: uuid.UUID, fact_id: uuid.UUID) -> LaceFact:
    fact = await db.scalar(select(LaceFact).where(
        LaceFact.id == fact_id, LaceFact.lace_id == lace_id,
        LaceFact.superseded_by_id.is_(None), LaceFact.retracted_at.is_(None)).with_for_update())
    if fact is None:
        raise NotFoundError("Fact not found")
    return fact


async def review_fact(db: AsyncSession, lace_id: uuid.UUID, fact_id: uuid.UUID, verdict: FactVerdict) -> LaceFact:
    """The founder confirms a fact, or says it is wrong."""
    fact = await _current_fact(db, lace_id, fact_id)
    now = datetime.now(UTC)
    if verdict == "confirmed":
        fact.confirmed_at = now
    else:
        fact.retracted_at = now
    await db.commit()
    return fact


async def correct_fact(db: AsyncSession, lace_id: uuid.UUID, fact_id: uuid.UUID, claim: str) -> LaceFact:
    """The founder rewrites a fact: their version supersedes it."""
    claim = claim.strip()
    if not claim:
        raise InvalidInputError("Write the fact as it should read.")
    old = await _current_fact(db, lace_id, fact_id)
    new = LaceFact(lace_id=lace_id, topic=old.topic, claim=claim, source_url=None, confidence="high",
                   origin="user", confirmed_at=datetime.now(UTC))
    db.add(new)
    await db.flush()
    old.superseded_by_id = new.id
    await db.commit()
    return new
