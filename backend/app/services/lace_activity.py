"""A Lace's activity: what it did or found, for the founder's Feed. Each item
is written in the same transaction as the result it reports, so the Feed
never shows something that was not saved, nor misses something that was."""

import uuid
from collections.abc import Sequence
from datetime import UTC, datetime

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from agents.schemas.lace import ActivityKind, ActivityRef
from backend.app.database.lace_models import Lace, LaceActivity
from backend.app.services import lace_members

# Names quoted in an activity's summary; the rest are counted.
NAMES_SHOWN = 3
TITLE_CHARS = 200
# A brief's Feed item: its title, and its summary until the Lace has written it.
BRIEF_TITLE = "Your brief"
BRIEF_WRITING = "Writing it now…"


def names(items: Sequence[str]) -> str:
    """"A, B and C", or "A, B, C and 4 more"."""
    shown = list(items[:NAMES_SHOWN])
    rest = len(items) - len(shown)
    if rest > 0:
        return f"{', '.join(shown)} and {rest} more"
    if len(shown) > 1:
        return f"{', '.join(shown[:-1])} and {shown[-1]}"
    return shown[0] if shown else ""


def plural(count: int, one: str, many: str | None = None) -> str:
    return f"{count} {one}" if count == 1 else f"{count} {many or one + 's'}"


async def add(db: AsyncSession, lace_id: uuid.UUID, kind: ActivityKind, title: str, summary: str | None = None,
              ref: tuple[ActivityRef, uuid.UUID] | None = None, actor_id: uuid.UUID | None = None) -> None:
    """Something the Lace did or found; `actor_id` is who asked for it."""
    ref_type, ref_id = ref if ref else (None, None)
    db.add(LaceActivity(lace_id=lace_id, kind=kind, title=title[:TITLE_CHARS], summary=summary,
                        ref_type=ref_type, ref_id=ref_id, actor_id=actor_id))


async def note(db: AsyncSession, lace_id: uuid.UUID, actor_id: uuid.UUID | None, kind: ActivityKind, title: str,
               summary: str | None = None) -> None:
    """Something done at a person's hand or word (`actor_id`; None when the
    Lace did it on its own), for the Feed's history. Already read: the Feed's
    seen state is shared, and nobody needs telling what they did themselves."""
    db.add(LaceActivity(lace_id=lace_id, kind=kind, title=title[:TITLE_CHARS], summary=summary,
                        actor_id=actor_id, read_at=datetime.now(UTC)))


async def fill_ref(db: AsyncSession, ref_type: ActivityRef, ref_id: uuid.UUID, summary: str) -> bool:
    """Set the summary of the item about this ref and show it as new again.
    False when there is no such item."""
    result = await db.execute(update(LaceActivity).where(
        LaceActivity.ref_type == ref_type, LaceActivity.ref_id == ref_id).values(summary=summary, read_at=None))
    return bool(result.rowcount)


async def list_for_lace(db: AsyncSession, lace_id: uuid.UUID, limit: int,
                        before: datetime | None = None) -> list[LaceActivity]:
    """Newest first; `before` pages back from an item's created_at."""
    query = select(LaceActivity).where(LaceActivity.lace_id == lace_id)
    if before is not None:
        query = query.where(LaceActivity.created_at < before)
    return list((await db.scalars(query.order_by(LaceActivity.created_at.desc()).limit(limit))).all())


async def unread_count(db: AsyncSession, lace_id: uuid.UUID) -> int:
    return await db.scalar(select(func.count()).select_from(LaceActivity).where(
        LaceActivity.lace_id == lace_id, LaceActivity.read_at.is_(None))) or 0


async def mark_all_read(db: AsyncSession, lace_id: uuid.UUID) -> int:
    """The founder has seen the Feed. Returns how many were unread."""
    result = await db.execute(update(LaceActivity).where(
        LaceActivity.lace_id == lace_id, LaceActivity.read_at.is_(None)).values(read_at=datetime.now(UTC)))
    await db.commit()
    return result.rowcount or 0


async def list_for_user(db: AsyncSession, user_id: uuid.UUID, limit: int,
                        before: datetime | None = None) -> list[tuple[LaceActivity, Lace]]:
    """Activity across all the user's Laces (archived ones left out), newest
    first, each with its Lace."""
    query = (select(LaceActivity, Lace).join(Lace, Lace.id == LaceActivity.lace_id)
             .where(Lace.id.in_(lace_members.lace_ids_of(user_id)), Lace.status != "archived"))
    if before is not None:
        query = query.where(LaceActivity.created_at < before)
    return [(a, lace) for a, lace in (await db.execute(query.order_by(LaceActivity.created_at.desc()).limit(limit))).all()]
