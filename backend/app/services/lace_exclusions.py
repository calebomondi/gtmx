"""What a Lace learns from the founder dismissing a find with a reason: the
reason joins its ideal customer profile's exclusions, which every later
customer and opportunity search steers clear of."""

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from agents.schemas.lace import DismissReason
from backend.app.database.lace_models import Lace

REASON_LABELS: dict[DismissReason, str] = {
    "not_our_buyer": "not our buyer", "too_small": "too small", "wrong_place": "wrong place",
    "no_need": "no need for what we sell", "other": "not a fit",
}
# Exclusions a profile keeps, its own and learned; the oldest go first.
MAX_EXCLUSIONS = 30


async def learn(db: AsyncSession, lace_id: uuid.UUID, find, name: str, reason: DismissReason | None,
                note: str | None) -> None:
    """Keep why the founder dismissed a team find, as an exclusion on the
    Lace's profile. A member's private find teaches the team nothing, and
    without a profile there is nowhere to keep it yet."""
    if reason is None or find.owner_id is not None:
        return
    lace = await db.get(Lace, lace_id)
    if lace is None or not lace.icp:
        return
    why = REASON_LABELS[reason] + (f": {note.strip()}" if note and note.strip() else "")
    line = f"Like {name} ({why})"
    kept = [e for e in lace.icp.get("exclusions") or [] if e != line]
    lace.icp = {**lace.icp, "exclusions": [*kept, line][-MAX_EXCLUSIONS:]}
    await db.commit()
