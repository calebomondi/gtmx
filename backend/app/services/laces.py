"""Laces: create one, find the user's own, and read what it knows."""

import uuid
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import Select, and_, exists, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.database.lace_models import Lace, LaceFact, LaceOutreach
from backend.app.database.models import Run
from backend.app.schemas.laces import LaceMood
from backend.app.services.runs import TERMINAL_STATUSES
from backend.app.services.competitors import domain_key, normalize_website
from backend.app.services import limits
from backend.app.services.errors import ConflictError, InvalidInputError, NotFoundError
from config import settings


async def create(db: AsyncSession, user_id: uuid.UUID, name: str, website: str,
                 timezone: str | None = None) -> Lace:
    name, website = name.strip(), normalize_website(website)
    if not name:
        raise InvalidInputError("Give your Lace a name.")
    if "." not in domain_key(website):
        raise InvalidInputError("That doesn't look like a website address.")
    owned = await db.scalar(select(func.count()).select_from(Lace).where(
        Lace.user_id == user_id, Lace.status != "archived"))
    if owned >= settings.max_laces_per_user:
        raise ConflictError(f"You can have up to {settings.max_laces_per_user} Laces.")
    # Checked before the insert, so a refused onboarding leaves no Lace behind.
    await limits.ensure_can_start(db, user_id, "lace_onboarding")
    lace = Lace(user_id=user_id, name=name, website=website, timezone=timezone or "UTC")
    db.add(lace)
    await db.commit()
    return lace


@dataclass(frozen=True)
class LaceSummary:
    lace: Lace
    mood: LaceMood | None
    last_active_at: datetime


async def list_for_user(db: AsyncSession, user_id: uuid.UUID, limit: int) -> list[LaceSummary]:
    """The user's Laces, most recently active first, each with its mood:
    thinking while a run is unfinished, alert while something waits on the
    founder (a draft to send, a reply not yet read)."""
    working = exists().where(Run.lace_id == Lace.id, Run.status.not_in(TERMINAL_STATUSES))
    waiting = exists().where(LaceOutreach.lace_id == Lace.id, or_(
        and_(LaceOutreach.direction == "outbound", LaceOutreach.status == "draft"),
        and_(LaceOutreach.direction == "inbound", LaceOutreach.status == "received", LaceOutreach.intent.is_(None)),
    ))
    last_run = select(func.max(Run.created_at)).where(Run.lace_id == Lace.id).correlate(Lace).scalar_subquery()
    last_active = func.coalesce(last_run, Lace.created_at)
    rows = await db.execute(
        select(Lace, working.label("working"), waiting.label("waiting"), last_active.label("last_active_at"))
        .where(Lace.user_id == user_id, Lace.status != "archived")
        .order_by(last_active.desc()).limit(limit)
    )
    return [LaceSummary(lace, "thinking" if busy else "alert" if needs else None, active)
            for lace, busy, needs, active in rows.all()]


async def set_pinned(db: AsyncSession, lace: Lace, pinned: bool) -> Lace:
    lace.pinned = pinned
    await db.commit()
    return lace


async def get_owned(db: AsyncSession, user_id: uuid.UUID, lace_id: uuid.UUID) -> Lace:
    """404 for another user's Lace, the same as for one that does not exist."""
    lace = await db.scalar(select(Lace).where(Lace.id == lace_id, Lace.user_id == user_id))
    if lace is None:
        raise NotFoundError("Lace not found")
    return lace


def current_facts_query(lace_id: uuid.UUID, topic: str | None, limit: int) -> Select[tuple[LaceFact]]:
    """A Lace's current facts (superseded ones hidden), newest first."""
    query = (
        select(LaceFact)
        .where(LaceFact.lace_id == lace_id, LaceFact.superseded_by_id.is_(None))
        .order_by(LaceFact.recorded_at.desc()).limit(limit)
    )
    return query if topic is None else query.where(LaceFact.topic == topic)


async def list_facts(db: AsyncSession, lace_id: uuid.UUID, topic: str | None, limit: int) -> list[LaceFact]:
    return list((await db.scalars(current_facts_query(lace_id, topic, limit))).all())


async def update_brief_settings(db: AsyncSession, lace: Lace, changes: dict) -> Lace:
    """Apply the fields present in `changes`. A None setting is ignored, except
    `quiet_hours`, where None removes them."""
    for field in ("brief_frequency", "brief_hour", "timezone", "brief_email"):
        if changes.get(field) is not None:
            setattr(lace, field, changes[field])
    if "quiet_hours" in changes:
        quiet = changes["quiet_hours"] or {}
        lace.quiet_start, lace.quiet_end = quiet.get("start"), quiet.get("end")
    await db.commit()
    return lace
