"""`agents.lace.apps.LaceApps` for one Lace: the apps it uses (its own
accounts, else its founder's shared ones), reached through Composio."""

import asyncio
import uuid
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from agents.lace.apps import AppError, CommentsOn, XRecord
from backend.app.database.lace_models import Lace, LaceChannel
from backend.app.services import connections as connection_service
from backend.app.services import lace_app_settings
from backend.app.services.lace_channels import items
from data_sources.socials import x_api
from utils.log import logger

# Composio tools, verified against the live catalog.
_X_USER = "TWITTER_USER_LOOKUP_BY_USERNAME"
_X_POST = "TWITTER_POST_LOOKUP_BY_POST_ID"
# The founder's recent posts read for comments, and comments read per post.
COMMENTS_PER_POST = 20
TEXT_CHARS = 300


@dataclass(frozen=True)
class _Live:
    entity: str
    connection_id: str
    # The account in the app linked to this Lace (its Instagram business account, its Page).
    linked_account: str | None


class DbLaceApps:
    def __init__(self, sessions: async_sessionmaker[AsyncSession], lace_id: uuid.UUID):
        self._sessions = sessions
        self._lace_id = lace_id

    async def _live(self, platform: str) -> _Live | None:
        """The live account this Lace uses for `platform`, if any."""
        async with self._sessions() as session:
            lace = await session.get(Lace, self._lace_id)
            if lace is None or not await lace_app_settings.enabled(session, lace, platform):
                return None
            live = await connection_service.connection_for(session, lace, platform)
            linked = await session.scalar(select(LaceChannel.account_id).where(
                LaceChannel.lace_id == self._lace_id, LaceChannel.platform == platform))
        return _Live(live.entity, live.id, linked) if live else None

    async def _run(self, live: _Live, platform: str, tool: str, arguments: dict):
        """One Composio tool's data; AppError when it is refused or fails."""
        try:
            result = await asyncio.to_thread(connection_service.execute_tool, live.entity, tool, arguments,
                                             live.connection_id)
        except Exception as exc:  # noqa: BLE001 -- the SDK raises many types; reported to the model
            logger.exception("Composio %s failed for Lace %s", tool, self._lace_id)
            raise AppError(f"Couldn't reach {connection_service.label(platform)} ({type(exc).__name__})") from exc
        if result.get("error"):
            raise AppError(f"{connection_service.label(platform)} refused it ({str(result['error'])[:200]})")
        return result.get("data")

    async def x(self, record: XRecord, key: str) -> dict | None:
        live = await self._live("x")
        if live is None:
            return None
        if record == "profile":
            tool, arguments = _X_USER, {"username": key, "user__fields": x_api.USER_FIELDS}
        else:
            tool, arguments = _X_POST, {"id": key, "tweet__fields": x_api.POST_FIELDS,
                                        "expansions": x_api.POST_EXPANSIONS, "user__fields": ["username", "name"]}
        data = await self._run(live, "x", tool, arguments)
        return data if isinstance(data, dict) else None

    async def my_comments(self, platform: CommentsOn, posts: int) -> list[dict] | None:
        live = await self._live(platform)
        if live is None:
            return None
        if platform == "instagram":
            return await self._instagram_comments(live, posts)
        return await self._facebook_comments(live, posts)

    async def _instagram_comments(self, live: _Live, posts: int) -> list[dict]:
        media_args = {"limit": posts, **({"ig_user_id": live.linked_account} if live.linked_account else {})}
        media = items(await self._run(live, "instagram", "INSTAGRAM_GET_USER_MEDIA", media_args))
        found = []
        for post in media:
            if not post.get("comments_count"):
                continue
            comments = items(await self._run(live, "instagram", "INSTAGRAM_GET_POST_COMMENTS",
                                             {"ig_post_id": post["id"], "limit": COMMENTS_PER_POST}))
            found += [_comment("instagram", post.get("permalink"), post.get("caption"), c.get("id"), c.get("username"),
                               c.get("text"), c.get("timestamp")) for c in comments if c.get("text")]
        return found

    async def _facebook_comments(self, live: _Live, posts: int) -> list[dict]:
        page = live.linked_account
        if not page:
            pages = items(await self._run(live, "facebook", "FACEBOOK_LIST_MANAGED_PAGES", {}))
            if len(pages) != 1:
                raise AppError("Link the Facebook Page this Lace uses (Messaging → Inboxes) to read its comments.")
            page = str(pages[0]["id"])
        page_posts = items(await self._run(live, "facebook", "FACEBOOK_GET_PAGE_POSTS", {
            "page_id": page, "limit": posts, "fields": "id,message,permalink_url,created_time"}))
        found = []
        for post in page_posts:
            comments = items(await self._run(live, "facebook", "FACEBOOK_GET_COMMENTS", {
                "object_id": post["id"], "limit": COMMENTS_PER_POST, "fields": "id,message,from,created_time"}))
            found += [_comment("facebook", post.get("permalink_url"), post.get("message"), c.get("id"),
                               (c.get("from") or {}).get("name"), c.get("message"), c.get("created_time"))
                      for c in comments if c.get("message")]
        return found


def _comment(platform: str, post_url, post_text, comment_id, author, text, date) -> dict:
    return {"platform": platform, "post_url": post_url, "post_text": (post_text or "")[:TEXT_CHARS],
            "comment_id": comment_id, "author": author, "text": (text or "")[:TEXT_CHARS], "date": date}
