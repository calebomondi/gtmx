"""Who is on a Lace, and what each may do there.

A Lace is shared by a startup's founding team: its owner (who made it), and
the people they invite as admins or members. Everyone on it works with the
same Lace. Admins and the owner also manage its apps, settings and people;
only the owner archives or deletes it. Someone not on a Lace, or invited but
not yet in, sees it as missing (404), so its existence can't be probed.
"""

import asyncio
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import Select, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from agents.schemas.lace import LaceRole
from backend.app import supabase_admin
from backend.app.database.lace_models import Lace, LaceMember
from backend.app.services import admin as admin_service
from backend.app.services.errors import ConflictError, ForbiddenError, InvalidInputError, NotFoundError
from utils.log import logger

# People on one Lace, invites included: a founding team, with room.
MAX_MEMBERS = 12

# Each role can do everything the ones below it can.
_RANK: dict[str, int] = {"member": 1, "admin": 2, "owner": 3}
_ROLE_NAME = {"admin": "an admin", "owner": "the owner"}


def lace_ids_of(user_id: uuid.UUID) -> Select[tuple[uuid.UUID]]:
    """The ids of the Laces the user is on, for `Lace.id.in_(...)`."""
    return select(LaceMember.lace_id).where(LaceMember.user_id == user_id, LaceMember.status == "active")


async def membership(db: AsyncSession, lace_id: uuid.UUID, user_id: uuid.UUID) -> LaceMember | None:
    """The user's row on the Lace, in any status."""
    return await db.scalar(select(LaceMember).where(LaceMember.lace_id == lace_id, LaceMember.user_id == user_id))


async def open_lace(db: AsyncSession, lace_id: uuid.UUID, user_id: uuid.UUID,
                    at_least: LaceRole) -> tuple[Lace, LaceMember]:
    """The Lace and the user's place on it. NotFoundError unless they are on
    it; ForbiddenError when their role is below `at_least`."""
    member = await membership(db, lace_id, user_id)
    lace = await db.get(Lace, lace_id) if member is not None and member.status == "active" else None
    if lace is None:
        raise NotFoundError("Lace not found")
    if _RANK[member.role] < _RANK[at_least]:
        raise ForbiddenError(f"Only {_ROLE_NAME[at_least]} of {lace.name} can do that.")
    return lace, member


def add_owner(db: AsyncSession, lace: Lace) -> None:
    """Its creator joins a new Lace as its owner; the caller commits."""
    now = datetime.now(UTC)
    db.add(LaceMember(lace_id=lace.id, user_id=lace.user_id, role="owner", status="active", created_at=now,
                      responded_at=now))


@dataclass(frozen=True)
class Person:
    """Someone on a Lace (or invited to it), as the team sees them."""
    user_id: uuid.UUID
    name: str | None
    email: str | None
    avatar_url: str | None
    role: str
    status: str


async def _user(user_id: uuid.UUID):
    try:
        return await supabase_admin.get_user(user_id)
    except Exception:  # noqa: BLE001 -- the SDK raises many types; a person without a name is still listed
        logger.exception("Looking up user %s failed", user_id)
        return None


async def people(db: AsyncSession, lace: Lace) -> list[Person]:
    """The Lace's people and open invites: the owner first, then by when they joined."""
    rows = list((await db.scalars(select(LaceMember).where(
        LaceMember.lace_id == lace.id, LaceMember.status != "declined")
        .order_by(LaceMember.role != "owner", LaceMember.created_at))).all())
    users = await asyncio.gather(*(_user(r.user_id) for r in rows))
    return [Person(r.user_id, supabase_admin.name_of(u), getattr(u, "email", None), supabase_admin.avatar_of(u),
                   r.role, r.status) for r, u in zip(rows, users)]


async def _signed_up(email: str):
    wanted = email.strip().lower()
    return next((u for u in await admin_service.list_all_users() if (u.email or "").lower() == wanted), None)


async def invite(db: AsyncSession, lace: Lace, inviter: LaceMember, email: str, role: LaceRole) -> Person:
    """Invite someone who has signed up, as an admin or a member. Only the
    owner invites admins. Re-inviting someone who declined asks again."""
    if role == "owner":
        raise InvalidInputError("A Lace has one owner.")
    if role == "admin" and inviter.role != "owner":
        raise ForbiddenError("Only the owner can invite admins.")
    user = await _signed_up(email)
    if user is None:
        raise InvalidInputError("No one has signed up with that email yet. Ask them to sign up first, then invite them.")
    user_id = uuid.UUID(str(user.id))
    row = await membership(db, lace.id, user_id)
    if row is not None and row.status != "declined":
        raise ConflictError("They are already on this Lace." if row.status == "active" else "They are already invited.")
    count = await db.scalar(select(func.count()).select_from(LaceMember).where(
        LaceMember.lace_id == lace.id, LaceMember.status != "declined"))
    if (count or 0) >= MAX_MEMBERS:
        raise ConflictError(f"A Lace takes at most {MAX_MEMBERS} people.")
    if row is None:
        row = LaceMember(lace_id=lace.id, user_id=user_id)
        db.add(row)
    row.role, row.status, row.invited_by, row.responded_at = role, "invited", inviter.user_id, None
    row.created_at = datetime.now(UTC)
    await db.commit()
    return Person(user_id, supabase_admin.name_of(user), user.email, supabase_admin.avatar_of(user), role, "invited")


async def _target(db: AsyncSession, lace: Lace, user_id: uuid.UUID) -> LaceMember:
    row = await membership(db, lace.id, user_id)
    if row is None or row.status == "declined":
        raise NotFoundError("They aren't on this Lace.")
    return row


async def set_role(db: AsyncSession, lace: Lace, user_id: uuid.UUID, role: LaceRole) -> None:
    """Make someone an admin or a member (the owner's call)."""
    row = await _target(db, lace, user_id)
    if row.role == "owner" or role == "owner":
        raise InvalidInputError("The owner stays the owner.")
    row.role = role
    await db.commit()


async def remove(db: AsyncSession, lace: Lace, actor: LaceMember, user_id: uuid.UUID) -> None:
    """Take someone off the Lace, or withdraw their invite. Admins remove
    members; the owner removes anyone but themself."""
    row = await _target(db, lace, user_id)
    if row.role == "owner":
        raise InvalidInputError("The owner can't be removed.")
    if row.role == "admin" and actor.role != "owner":
        raise ForbiddenError("Only the owner can remove an admin.")
    await db.delete(row)
    await db.commit()


async def leave(db: AsyncSession, member: LaceMember) -> None:
    if member.role == "owner":
        raise InvalidInputError("The owner can't leave their Lace; archive or delete it instead.")
    await db.delete(member)
    await db.commit()


@dataclass(frozen=True)
class Invite:
    lace: Lace
    role: str
    invited_by: str | None
    invited_at: datetime


async def invites_for(db: AsyncSession, user_id: uuid.UUID) -> list[Invite]:
    """The user's invites still waiting for their answer, newest first."""
    rows = (await db.execute(select(LaceMember, Lace).join(Lace, Lace.id == LaceMember.lace_id).where(
        LaceMember.user_id == user_id, LaceMember.status == "invited", Lace.status != "archived")
        .order_by(LaceMember.created_at.desc()))).all()
    inviters = await asyncio.gather(*(_user(row.invited_by) for row, _ in rows))
    return [Invite(lace, row.role, (supabase_admin.name_of(u) or getattr(u, "email", None)) if u else None,
                   row.created_at) for (row, lace), u in zip(rows, inviters)]


async def _invited(db: AsyncSession, lace_id: uuid.UUID, user_id: uuid.UUID) -> LaceMember:
    row = await membership(db, lace_id, user_id)
    if row is None or row.status != "invited":
        raise NotFoundError("No invite to that Lace.")
    return row


async def accept(db: AsyncSession, lace_id: uuid.UUID, user_id: uuid.UUID) -> LaceMember:
    row = await _invited(db, lace_id, user_id)
    row.status, row.responded_at = "active", datetime.now(UTC)
    await db.commit()
    return row


async def decline(db: AsyncSession, lace_id: uuid.UUID, user_id: uuid.UUID) -> None:
    row = await _invited(db, lace_id, user_id)
    row.status, row.responded_at = "declined", datetime.now(UTC)
    await db.commit()
