"""Who is on a Lace, and what each may do there.

A Lace is shared by a startup's founding team: its owner (who made it), and
the people they invite as admins or members. Everyone on it works with the
same Lace. Admins and the owner also manage its apps, settings and people;
only the owner archives or deletes it. Someone not on a Lace, or invited but
not yet in, sees it as missing (404), so its existence can't be probed.
"""

import uuid
from datetime import UTC, datetime

from sqlalchemy import Select, select
from sqlalchemy.ext.asyncio import AsyncSession

from agents.schemas.lace import LaceRole
from backend.app.database.lace_models import Lace, LaceMember
from backend.app.services.errors import ForbiddenError, NotFoundError

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
