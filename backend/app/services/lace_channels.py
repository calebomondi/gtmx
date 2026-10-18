"""A founder's Instagram business account or Facebook Page, linked to the Lace
that reads its inbound DMs. Only accounts the founder's own live connection
manages can be linked, and each to one Lace."""

import asyncio
import uuid

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.database.lace_models import LaceChannel
from backend.app.services import connections as connection_service
from backend.app.services.errors import ConflictError, InvalidInputError, NotFoundError

# Verified against the live Composio catalog (docs/lace-plan.md, Channels).
_ACCOUNT_TOOLS = {
    "instagram": ("INSTAGRAM_GET_USER_INFO", {"ig_user_id": "me"}),
    "facebook": ("FACEBOOK_LIST_MANAGED_PAGES", {}),
}
LABELS = {"instagram": "Instagram", "facebook": "Facebook"}


def items(data) -> list[dict]:
    """The records in a Composio Graph response: `{"data": [...]}`, or one
    object for a single-record call."""
    if isinstance(data, dict) and isinstance(data.get("data"), list):
        return [d for d in data["data"] if isinstance(d, dict)]
    if isinstance(data, dict) and data.get("id"):
        return [data]
    return []


async def live_connection(db: AsyncSession, user_id: uuid.UUID, platform: str):
    connection = next((c for c in await connection_service.list_for_user(db, user_id)
                       if c.platform == platform and c.status == "live"), None)
    if connection is None:
        raise ConflictError(f"Connect your {LABELS[platform]} account on the Accounts page first.")
    return connection


async def available(db: AsyncSession, user_id: uuid.UUID, platform: str) -> list[dict]:
    """The business accounts (Instagram) or Pages (Facebook) the founder's
    connection manages: [{id, name}]."""
    connection = await live_connection(db, user_id, platform)
    tool, arguments = _ACCOUNT_TOOLS[platform]
    result = await asyncio.to_thread(connection_service.execute_tool, user_id, tool, arguments, connection.id)
    if result.get("error"):
        raise ConflictError(f"{LABELS[platform]} didn't list your accounts. Reconnect it on the Accounts page.")
    return [{"id": str(r["id"]), "name": r.get("username") or r.get("name") or str(r["id"])}
            for r in items(result.get("data"))]


async def list_for_lace(db: AsyncSession, lace_id: uuid.UUID) -> list[LaceChannel]:
    return list((await db.scalars(select(LaceChannel).where(LaceChannel.lace_id == lace_id)
                                  .order_by(LaceChannel.created_at))).all())


async def link(db: AsyncSession, lace_id: uuid.UUID, user_id: uuid.UUID, platform: str, account_id: str) -> LaceChannel:
    account = next((a for a in await available(db, user_id, platform) if a["id"] == account_id), None)
    if account is None:
        raise InvalidInputError(f"That {LABELS[platform]} account isn't one your connection manages.")
    channel = LaceChannel(lace_id=lace_id, user_id=user_id, platform=platform, account_id=account_id,
                          account_name=account["name"][:255])
    db.add(channel)
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise ConflictError("That account is already linked to a Lace.") from None
    return channel


async def unlink(db: AsyncSession, lace_id: uuid.UUID, channel_id: uuid.UUID) -> None:
    channel = await db.scalar(select(LaceChannel).where(LaceChannel.id == channel_id, LaceChannel.lace_id == lace_id))
    if channel is None:
        raise NotFoundError("Channel not found")
    await db.delete(channel)
    await db.commit()
