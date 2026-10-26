"""The cards under a Lace's replies, marked with where their items stand now:
a card is a snapshot from when it was shown, but the founder may have saved
or dismissed the item since, in the chat or anywhere else. Proposed app
actions likewise show whether they were approved, ran or were declined."""

import uuid
from collections import defaultdict

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.database.lace_models import LaceAccount, LaceCompetitor, LaceOpportunity, LaceOutreach
from backend.app.services import lace_app_actions

# A card whose item no longer exists (a discarded draft, a deleted Lace's rows).
GONE = "gone"
_TABLES = {"competitor": LaceCompetitor, "account": LaceAccount, "opportunity": LaceOpportunity,
           "draft": LaceOutreach}


def _uuid(value: str) -> uuid.UUID | None:
    try:
        return uuid.UUID(value)
    except ValueError:
        return None


async def _statuses(db: AsyncSession, lace_id: uuid.UUID, kind: str, ids: set[str]) -> dict[str, str]:
    table = _TABLES[kind]
    keys = [k for k in map(_uuid, ids) if k is not None]
    rows = (await db.execute(select(table.id, table.status).where(table.lace_id == lace_id, table.id.in_(keys)))).all()
    return {str(row_id): status for row_id, status in rows}


async def with_status(db: AsyncSession, lace_id: uuid.UUID, messages: list[dict]) -> list[dict]:
    """The messages, with each card's `status` set to its item's status now."""
    wanted: dict[str, set[str]] = defaultdict(set)
    for message in messages:
        for block in message.get("ui") or []:
            if block.get("type") == "card" and block.get("kind") in _TABLES:
                wanted[block["kind"]].add(block["id"])
    now = {kind: await _statuses(db, lace_id, kind, ids) for kind, ids in wanted.items()}
    actions = await lace_app_actions.statuses(db, lace_id, {
        key for m in messages for b in m.get("ui") or [] if b.get("type") == "action" and (key := _uuid(b["id"]))})
    for message in messages:
        for block in message.get("ui") or []:
            if block.get("type") == "card" and block.get("kind") in _TABLES:
                block["status"] = now[block["kind"]].get(block["id"], GONE)
            elif block.get("type") == "action":
                action = actions.get(block["id"])
                block["status"] = action.status if action else GONE
                block["result"], block["url"] = (action.result, action.url) if action else (None, None)
    return messages
