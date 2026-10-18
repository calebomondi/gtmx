"""Laces: create one, find the user's own, and read what it knows."""

import uuid

from sqlalchemy import Select, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.database.lace_models import Lace, LaceFact
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


async def list_for_user(db: AsyncSession, user_id: uuid.UUID, limit: int) -> list[Lace]:
    rows = await db.scalars(
        select(Lace).where(Lace.user_id == user_id, Lace.status != "archived")
        .order_by(Lace.created_at.desc()).limit(limit)
    )
    return list(rows.all())


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
