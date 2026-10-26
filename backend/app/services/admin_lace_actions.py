"""Admin fixes for duplicate Laces: ones made before a startup could have
only one Lace, which share their website's domain with an older Lace and
so hold no domain of their own. Either the duplicate's people join the Lace
holding the domain and the duplicate is archived, or the duplicate takes the
domain over. Both write an admin_audit_log row."""

import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.database.lace_models import Lace, LaceMember
from backend.app.services import admin_laces, lace_activity, lace_members, laces
from backend.app.services.admin import record_audit
from backend.app.services.competitors import domain_key
from backend.app.services.errors import ConflictError, NotFoundError


async def _duplicate(db: AsyncSession, lace_id: uuid.UUID) -> Lace:
    lace = await db.get(Lace, lace_id)
    if lace is None:
        raise NotFoundError("Lace not found.")
    if lace.domain is not None:
        raise ConflictError(f"{lace.name} already holds its domain, {lace.domain}.")
    return lace


async def _audit(db: AsyncSession, actor, action: str, lace: Lace, before: dict, after: dict) -> None:
    await record_audit(db, actor_id=actor.id, actor_email=actor.email, action=action, target_type="lace",
                       target_id=str(lace.id), before=before, after=after)


async def fold(db: AsyncSession, actor, lace_id: uuid.UUID) -> None:
    """The duplicate's people join the Lace holding its domain (its owner as
    an admin) and the duplicate is archived. Its own facts and finds stay on
    it, archived: they are not merged."""
    lace = await _duplicate(db, lace_id)
    holder = await admin_laces.holder_of(db, lace)
    if holder is None:
        raise ConflictError(f"No Lace holds {domain_key(lace.website)} now. Give {lace.name} the domain instead.")
    if holder.status == "archived":
        raise ConflictError(f"{holder.name} is archived. Give {lace.name} the domain instead.")
    await laces.ensure_idle(db, lace)
    joined = [str(m.user_id) for m in await _people(db, lace) if await _join(db, holder, m)]
    before = {"status": lace.status}
    lace.status = "archived"
    await _audit(db, actor, "lace.fold", lace, before, {"status": "archived", "into": str(holder.id), "joined": joined})
    await db.commit()


async def _people(db: AsyncSession, lace: Lace) -> list[LaceMember]:
    return list(await db.scalars(select(LaceMember).where(
        LaceMember.lace_id == lace.id, LaceMember.status == "active")))


async def _join(db: AsyncSession, holder: Lace, member: LaceMember) -> bool:
    """Puts the person on the holder's Lace, unless they are on it already."""
    row = await lace_members.membership(db, holder.id, member.user_id)
    if row is not None and row.status == "active":
        return False
    role = "admin" if member.role in ("owner", "admin") else "member"
    now = datetime.now(UTC)
    if row is None:
        db.add(LaceMember(lace_id=holder.id, user_id=member.user_id, role=role, status="active", created_at=now,
                          responded_at=now))
    else:
        row.role, row.status, row.responded_at = role, "active", now
    await lace_activity.note(db, holder.id, member.user_id, "member_joined", "Joined the team")
    return True


async def take_domain(db: AsyncSession, actor, lace_id: uuid.UUID) -> None:
    """The duplicate becomes the startup's Lace; the one that held the
    domain becomes the duplicate."""
    lace = await _duplicate(db, lace_id)
    holder = await admin_laces.holder_of(db, lace)
    domain = domain_key(lace.website)
    if holder is not None:
        holder.domain = None
        await db.flush()  # free the unique domain before this Lace takes it
    lace.domain = domain
    await _audit(db, actor, "lace.take_domain", lace, {"domain": None, "held_by": holder and str(holder.id)},
                 {"domain": domain})
    await db.commit()
