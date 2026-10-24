"""`agents.lace.apps.LaceApps` for one Lace: the apps it uses (its own
accounts, else its founder's shared ones), reached through Composio."""

import asyncio
import uuid
from datetime import UTC, datetime
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from agents.lace.apps import AppError, CommentsOn, XRecord
from backend.app.database.lace_models import Lace, LaceChannel
from backend.app.services import connections as connection_service
from backend.app.services import crm, lace_app_settings
from backend.app.services.lace_channels import items
from data_sources.socials import x_api
from utils.log import logger

# Composio tools, verified against the live catalog.
_X_USER = "TWITTER_USER_LOOKUP_BY_USERNAME"
_X_POST = "TWITTER_POST_LOOKUP_BY_POST_ID"
_SHEET_TABS = "GOOGLESHEETS_GET_SHEET_NAMES"
_SHEET_VALUES = "GOOGLESHEETS_BATCH_GET"
# The most rows and columns read from one tab (the header row included).
SHEET_ROWS = 1000
SHEET_COLUMNS = "ZZ"
_NOTION_SEARCH = "NOTION_SEARCH_NOTION_PAGE"
_NOTION_BLOCKS = "NOTION_FETCH_BLOCK_CONTENTS"
# Notion search results kept; block pages (of 100) and characters read from one page.
NOTION_RESULTS = 20
NOTION_BLOCK_PAGES = 5
NOTION_CHARS = 30_000
# How each Notion block type reads as a line of text.
_NOTION_LINE = {"heading_1": "# ", "heading_2": "## ", "heading_3": "### ", "bulleted_list_item": "- ",
                "numbered_list_item": "1. ", "quote": "> ", "to_do": "[ ] ", "toggle": "", "callout": "",
                "paragraph": "", "code": ""}
_SLACK_SEARCH = "SLACK_SEARCH_MESSAGES"
SLACK_RESULTS = 20
_ASANA_WORKSPACES = "ASANA_GET_MULTIPLE_WORKSPACES"
_ASANA_TASKS = "ASANA_GET_MULTIPLE_TASKS"
ASANA_TASKS = 100
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

    async def sheet(self, spreadsheet_id: str, tab: str | None) -> dict | None:
        live = await self._live("googlesheets")
        if live is None:
            return None
        tabs = await self._run(live, "googlesheets", _SHEET_TABS, {"spreadsheet_id": spreadsheet_id})
        names = [str(n) for n in (tabs or {}).get("sheet_names") or []] if isinstance(tabs, dict) else []
        if not names:
            raise AppError("Google Sheets didn't list that spreadsheet's tabs: check the link, and that you can open it.")
        chosen = next((n for n in names if tab and n.lower() == tab.strip().lower()), None) if tab else names[0]
        if chosen is None:
            raise AppError(f"There's no tab named {tab!r}; its tabs are {', '.join(names)}.")
        quoted = chosen.replace("'", "''")
        data = await self._run(live, "googlesheets", _SHEET_VALUES, {
            "spreadsheet_id": spreadsheet_id, "ranges": [f"'{quoted}'!A1:{SHEET_COLUMNS}{SHEET_ROWS}"]})
        ranges = ((data or {}).get("spreadsheet_data") or {}).get("valueRanges") or [] if isinstance(data, dict) else []
        values = (ranges[0].get("values") if ranges and isinstance(ranges[0], dict) else None) or []
        return {"tabs": names, "tab": chosen, "rows": [[str(c) for c in row] for row in values if isinstance(row, list)]}

    async def notion_search(self, query: str) -> list[dict] | None:
        live = await self._live("notion")
        if live is None:
            return None
        data = await self._run(live, "notion", _NOTION_SEARCH, {"query": query, "page_size": NOTION_RESULTS})
        results = ((data or {}).get("response_data") or {}).get("results") or [] if isinstance(data, dict) else []
        return [{"id": r.get("id"), "title": _notion_title(r), "url": r.get("url"), "kind": r.get("object")}
                for r in results if isinstance(r, dict) and r.get("id")]

    async def notion_page(self, page_id: str) -> str | None:
        live = await self._live("notion")
        if live is None:
            return None
        lines: list[str] = []
        cursor = None
        for _ in range(NOTION_BLOCK_PAGES):
            data = await self._run(live, "notion", _NOTION_BLOCKS, {
                "block_id": page_id, "page_size": 100, **({"start_cursor": cursor} if cursor else {})})
            found = (data or {}).get("block_child_data") or {} if isinstance(data, dict) else {}
            for block in found.get("results") or []:
                kind = block.get("type") if isinstance(block, dict) else None
                if kind in _NOTION_LINE:
                    text = _plain((block.get(kind) or {}).get("rich_text"))
                    checked = kind == "to_do" and (block.get(kind) or {}).get("checked")
                    lines.append(("[x] " if checked else _NOTION_LINE[kind]) + text if text else "")
            cursor = found.get("next_cursor") if found.get("has_more") else None
            if not cursor or sum(map(len, lines)) > NOTION_CHARS:
                break
        return "\n".join(lines).strip()[:NOTION_CHARS]

    async def slack_search(self, query: str) -> list[dict] | None:
        live = await self._live("slack")
        if live is None:
            return None
        data = await self._run(live, "slack", _SLACK_SEARCH, {"query": query, "count": SLACK_RESULTS,
                                                               "sort": "timestamp", "sort_dir": "desc"})
        messages = (data or {}).get("messages") or {} if isinstance(data, dict) else {}
        return [{"text": (m.get("text") or "")[:TEXT_CHARS * 2], "author": m.get("username") or m.get("user"),
                 "channel": (m.get("channel") or {}).get("name"), "date": _slack_date(m.get("ts")),
                 "link": m.get("permalink")}
                for m in messages.get("matches") or [] if isinstance(m, dict) and m.get("text")]

    async def asana_tasks(self) -> list[dict] | None:
        live = await self._live("asana")
        if live is None:
            return None
        workspace = await asana_workspace(lambda tool, args: self._run(live, "asana", tool, args))
        tasks = items(await self._run(live, "asana", _ASANA_TASKS, {
            "workspace": workspace, "assignee": "me", "completed_since": "now", "limit": ASANA_TASKS,
            "opt_fields": ["name", "due_on", "completed", "permalink_url", "projects.name"]}))
        return [{"name": t.get("name"), "due_on": t.get("due_on"),
                 "project": ", ".join(p.get("name") or "" for p in t.get("projects") or [] if isinstance(p, dict)) or None,
                 "link": t.get("permalink_url")}
                for t in tasks if t.get("name") and not t.get("completed")]

    async def _crm_live(self) -> tuple[str, _Live] | None:
        for platform in crm.CRM_APPS:
            if (live := await self._live(platform)) is not None:
                return platform, live
        return None

    async def crm(self) -> str | None:
        found = await self._crm_live()
        return found[0] if found else None

    async def crm_deals(self) -> list[dict] | None:
        if (found := await self._crm_live()) is None:
            return None
        platform, live = found
        return await crm.DEALS[platform](lambda tool, args: self._run(live, platform, tool, args))

    async def crm_find(self, query: str) -> list[dict] | None:
        if (found := await self._crm_live()) is None:
            return None
        platform, live = found
        return await crm.FIND[platform](lambda tool, args: self._run(live, platform, tool, args), query)

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


async def asana_workspace(run) -> str:
    """The founder's Asana workspace (the first, for one with several);
    `run(tool, arguments)` returns a tool's data."""
    workspaces = items(await run(_ASANA_WORKSPACES, {"limit": 10}))
    if not workspaces or not workspaces[0].get("gid"):
        raise AppError("Asana didn't list a workspace for this account.")
    return str(workspaces[0]["gid"])


def _slack_date(ts) -> str | None:
    """A Slack message's ts (epoch seconds, as text) as an ISO date and time."""
    try:
        return datetime.fromtimestamp(float(ts), UTC).isoformat(timespec="minutes")
    except (TypeError, ValueError):
        return None


def _plain(rich_text) -> str:
    return "".join(part.get("plain_text") or "" for part in rich_text or [] if isinstance(part, dict))


def _notion_title(record: dict) -> str:
    """A page's title property, or a database's title."""
    if record.get("object") == "database":
        return _plain(record.get("title")) or "Untitled"
    for prop in (record.get("properties") or {}).values():
        if isinstance(prop, dict) and prop.get("type") == "title":
            return _plain(prop.get("title")) or "Untitled"
    return "Untitled"


def _comment(platform: str, post_url, post_text, comment_id, author, text, date) -> dict:
    return {"platform": platform, "post_url": post_url, "post_text": (post_text or "")[:TEXT_CHARS],
            "comment_id": comment_id, "author": author, "text": (text or "")[:TEXT_CHARS], "date": date}
