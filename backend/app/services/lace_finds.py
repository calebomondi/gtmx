"""Private finds and their review: what a member's private chat found
(competitors, accounts, opportunities with an owner_id) stays theirs until
they push it to the team. Then another member approves it, and it becomes
the team's, saved; or sends it back to them with a note. Admins and the
owner may approve anything, their own pushes too."""

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from agents.schemas.lace import ActivityKind, LaceRole, SavedKind
from backend.app.database.lace_models import LaceAccount, LaceCompetitor, LaceContact, LaceEvent, LaceOpportunity, LaceOutreach
from backend.app.services import lace_activity, lace_events
from backend.app.services.errors import ForbiddenError, NotFoundError

# A note left when someone sends a find back without one.
NO_NOTE = "Sent back without a note."


@dataclass(frozen=True)
class _Kind:
    model: type
    key: str  # its unique key column, per owner
    saved: str  # the status of a saved one
    name: str  # the column it is called by
    detail: str  # a second line about it
    noun: str  # "competitor"
    saved_kind: ActivityKind

    @property
    def label(self) -> str:
        return f"{'an' if self.noun[0] in 'aeiou' else 'a'} {self.noun}"


KINDS: dict[str, _Kind] = {
    "competitor": _Kind(LaceCompetitor, "domain_key", "tracked", "name", "website", "competitor", "competitor_saved"),
    "account": _Kind(LaceAccount, "key", "target", "name", "website", "target account", "account_saved"),
    "opportunity": _Kind(LaceOpportunity, "url_key", "open", "title", "organiser", "opportunity", "opportunity_saved"),
}


@dataclass(frozen=True)
class Find:
    kind: SavedKind
    id: uuid.UUID
    name: str
    detail: str | None
    status: str
    owner_id: uuid.UUID
    proposed_at: datetime | None
    review_note: str | None


def _find(kind: SavedKind, row) -> Find:
    spec = KINDS[kind]
    return Find(kind, row.id, getattr(row, spec.name), getattr(row, spec.detail), row.status, row.owner_id,
                row.proposed_at, row.review_note)


async def mine(db: AsyncSession, lace_id: uuid.UUID, owner_id: uuid.UUID, limit: int) -> list[Find]:
    """A member's private finds still in play (not dismissed), newest first."""
    found: list[Find] = []
    for kind, spec in KINDS.items():
        rows = await db.scalars(select(spec.model).where(
            spec.model.lace_id == lace_id, spec.model.owner_id == owner_id, spec.model.status != "dismissed")
            .order_by(spec.model.last_seen_at.desc()).limit(limit))
        found += [_find(kind, r) for r in rows]
    return found


async def push(db: AsyncSession, lace_id: uuid.UUID, owner_id: uuid.UUID,
               items: list[tuple[SavedKind, uuid.UUID]]) -> int:
    """Put a member's private finds up for the team's review. Others' finds,
    and ones already waiting, are skipped. Returns how many went up."""
    pushed: list[str] = []
    now = datetime.now(UTC)
    for kind, find_id in items:
        spec = KINDS[kind]
        row = await db.scalar(select(spec.model).where(
            spec.model.id == find_id, spec.model.lace_id == lace_id, spec.model.owner_id == owner_id,
            spec.model.proposed_at.is_(None)))
        if row is not None:
            row.proposed_at, row.review_note = now, None
            pushed.append(getattr(row, spec.name))
    if pushed:
        await lace_activity.add(db, lace_id, "finds_proposed", f"{lace_activity.plural(len(pushed), 'find')} to review",
                                lace_activity.names(pushed), actor_id=owner_id)
    await db.commit()
    return len(pushed)


async def forget_private(db: AsyncSession, lace_id: uuid.UUID, owner_id: uuid.UUID) -> None:
    """Someone left the Lace: what only they could see goes (their unpushed
    finds, their chat's queued updates). What they pushed stays for the
    team to review. The caller commits."""
    for spec in KINDS.values():
        await db.execute(delete(spec.model).where(
            spec.model.lace_id == lace_id, spec.model.owner_id == owner_id, spec.model.proposed_at.is_(None)))
    await db.execute(delete(LaceEvent).where(LaceEvent.lace_id == lace_id, LaceEvent.owner_id == owner_id))


async def to_review(db: AsyncSession, lace_id: uuid.UUID, limit: int) -> list[Find]:
    """Finds pushed to the team and not yet reviewed, oldest first."""
    found: list[Find] = []
    for kind, spec in KINDS.items():
        rows = await db.scalars(select(spec.model).where(
            spec.model.lace_id == lace_id, spec.model.proposed_at.is_not(None)).limit(limit))
        found += [_find(kind, r) for r in rows]
    return sorted(found, key=lambda f: f.proposed_at)[:limit]


def may_review(find: Find, reviewer_id: uuid.UUID, role: LaceRole) -> bool:
    """Someone else reviews a member's push; admins and the owner may also
    approve their own."""
    return find.owner_id != reviewer_id or role in ("owner", "admin")


async def _pending(db: AsyncSession, lace_id: uuid.UUID, kind: SavedKind, find_id: uuid.UUID,
                   reviewer_id: uuid.UUID, role: LaceRole):
    """The pushed find, if this reviewer may decide it."""
    spec = KINDS[kind]
    row = await db.scalar(select(spec.model).where(
        spec.model.id == find_id, spec.model.lace_id == lace_id, spec.model.proposed_at.is_not(None)))
    if row is None:
        raise NotFoundError("Nothing like that is waiting for review.")
    if not may_review(_find(kind, row), reviewer_id, role):
        raise ForbiddenError("Someone else on the team reviews what you push.")
    return row


async def approve(db: AsyncSession, lace_id: uuid.UUID, kind: SavedKind, find_id: uuid.UUID,
                  reviewer_id: uuid.UUID, role: LaceRole, reviewer_name: str) -> None:
    """A pushed find becomes the team's, saved (merged into the team's own
    copy when there is one). The team's Lace hears of it, and who approved
    it, at its next turn."""
    spec = KINDS[kind]
    row = await _pending(db, lace_id, kind, find_id, reviewer_id, role)
    name, owner_id = getattr(row, spec.name), row.owner_id
    await _into_team(db, lace_id, kind, row)
    await lace_activity.add(db, lace_id, spec.saved_kind, f"Saved {name} as {spec.label}", "Approved for the team",
                            actor_id=owner_id)
    await lace_events.add(db, lace_id, f"{name} ({spec.noun}), found in a private chat, was approved for the team "
                          f"by {reviewer_name} and is now saved on its file.")
    await db.commit()


async def send_back(db: AsyncSession, lace_id: uuid.UUID, kind: SavedKind, find_id: uuid.UUID,
                    reviewer_id: uuid.UUID, role: LaceRole, note: str | None) -> None:
    """A pushed find goes back to its owner, still private, with why."""
    spec = KINDS[kind]
    row = await _pending(db, lace_id, kind, find_id, reviewer_id, role)
    row.proposed_at, row.review_note = None, (note or "").strip() or NO_NOTE
    await lace_activity.add(db, lace_id, "finds_returned", f"Sent {getattr(row, spec.name)} back", row.review_note,
                            actor_id=reviewer_id)
    await db.commit()


async def _into_team(db: AsyncSession, lace_id: uuid.UUID, kind: SavedKind, row) -> None:
    """Make a private find the team's, saved. When the team has its own copy
    (same key), that copy is saved instead, takes the private one's people
    and messages, and the private one goes."""
    spec = KINDS[kind]
    team = await db.scalar(select(spec.model).where(
        spec.model.lace_id == lace_id, spec.model.team(), getattr(spec.model, spec.key) == getattr(row, spec.key)))
    if team is None:
        row.owner_id, row.status, row.proposed_at, row.review_note = None, spec.saved, None, None
        return
    team.status = spec.saved
    if kind == "account":
        await db.execute(update(LaceContact).where(LaceContact.account_id == row.id).values(account_id=team.id))
        await db.execute(update(LaceOutreach).where(LaceOutreach.account_id == row.id).values(account_id=team.id))
    await db.delete(row)
