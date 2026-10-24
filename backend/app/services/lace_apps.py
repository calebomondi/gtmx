"""`agents.lace.apps.LaceApps` for one Lace: its owner's connected apps,
reached through Composio."""

import asyncio
import uuid

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from agents.lace.apps import AppError, XRecord
from backend.app.database.lace_models import Lace
from backend.app.services import connections as connection_service
from data_sources.socials import x_api
from utils.log import logger

# Composio tools, verified against the live catalog.
_X_USER = "TWITTER_USER_LOOKUP_BY_USERNAME"
_X_POST = "TWITTER_POST_LOOKUP_BY_POST_ID"


class DbLaceApps:
    def __init__(self, sessions: async_sessionmaker[AsyncSession], lace_id: uuid.UUID):
        self._sessions = sessions
        self._lace_id = lace_id

    async def _live(self, platform: str) -> tuple[uuid.UUID, str] | None:
        """The Lace owner's id and their live connection to `platform`, if any."""
        async with self._sessions() as session:
            lace = await session.get(Lace, self._lace_id)
            if lace is None:
                return None
            live = next((c for c in await connection_service.list_for_user(session, lace.user_id)
                         if c.platform == platform and c.status == "live"), None)
        return (lace.user_id, live.id) if live else None

    async def x(self, record: XRecord, key: str) -> dict | None:
        found = await self._live("x")
        if found is None:
            return None
        user_id, connection_id = found
        if record == "profile":
            tool, arguments = _X_USER, {"username": key, "user__fields": x_api.USER_FIELDS}
        else:
            tool, arguments = _X_POST, {"id": key, "tweet__fields": x_api.POST_FIELDS,
                                        "expansions": x_api.POST_EXPANSIONS, "user__fields": ["username", "name"]}
        try:
            result = await asyncio.to_thread(connection_service.execute_tool, user_id, tool, arguments, connection_id)
        except Exception as exc:  # noqa: BLE001 -- the SDK raises many types; the caller falls back
            logger.exception("Composio %s failed for Lace %s", tool, self._lace_id)
            raise AppError(f"Couldn't reach X ({type(exc).__name__})") from exc
        if result.get("error"):
            raise AppError(f"X refused the lookup ({result['error']})")
        data = result.get("data")
        return data if isinstance(data, dict) else None
