"""Updates a Lace must pass on to its founder, queued until its next turn."""

import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.database.lace_models import LaceEvent

# Events taken into one turn; any more wait for the next.
MAX_EVENTS_PER_TURN = 10


async def add(db: AsyncSession, lace_id: uuid.UUID, text: str, owner_id: uuid.UUID | None = None,
              run_id: uuid.UUID | None = None) -> None:
    """An update for the team's chat, or (`owner_id`) for that member's private
    one; `run_id` is the search it reports on, when it does."""
    db.add(LaceEvent(lace_id=lace_id, owner_id=owner_id, text=text, run_id=run_id))


@dataclass
class Pending:
    """Updates taken for one turn, the searches they report on, and their ids
    (to put them back should the turn fail)."""
    texts: list[str] = field(default_factory=list)
    run_ids: list[uuid.UUID] = field(default_factory=list)
    ids: list[uuid.UUID] = field(default_factory=list)


async def take_pending(db: AsyncSession, lace_id: uuid.UUID, owner_id: uuid.UUID | None = None) -> Pending:
    """The oldest unconsumed events for one chat (the team's, or a member's
    private one), marked consumed in the caller's transaction: if the turn
    that would carry them cannot start, the caller rolls back and they stay
    queued. SKIP LOCKED so two wakes never take the same event."""
    chat = LaceEvent.owner_id.is_(None) if owner_id is None else LaceEvent.owner_id == owner_id
    rows = (await db.scalars(
        select(LaceEvent)
        .where(LaceEvent.lace_id == lace_id, chat, LaceEvent.consumed_at.is_(None))
        .order_by(LaceEvent.created_at).limit(MAX_EVENTS_PER_TURN)
        .with_for_update(skip_locked=True)
    )).all()
    now = datetime.now(UTC)
    for row in rows:
        row.consumed_at = now
    return Pending([row.text for row in rows], [row.run_id for row in rows if row.run_id is not None],
                   [row.id for row in rows])


async def put_back(db: AsyncSession, ids: list[uuid.UUID]) -> None:
    """Queue taken updates again: the turn that was to pass them on failed, so
    the next turn passes them on instead of their being lost."""
    await db.execute(update(LaceEvent).where(LaceEvent.id.in_(ids)).values(consumed_at=None))
