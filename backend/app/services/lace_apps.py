"""`agents.lace.apps.LaceApps` for one Lace: the apps it uses (its own
accounts, else its founder's shared ones), reached through Composio."""

import asyncio
import uuid
from datetime import UTC, datetime, timedelta
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from agents.lace.apps import AppError, AppStatus, CommentsOn, XRecord
from backend.app.database.lace_models import Lace, LaceApp, LaceChannel
from backend.app.services import connections as connection_service
from backend.app.services import crm, lace_app_settings
from backend.app.services.inbox import mail_text
from backend.app.services.lace_channels import items
from config import settings
from data_sources.socials import x_api
from data_sources.socials.brightdata import SocialsError
from data_sources.socials.tiktok import recent_videos as tiktok_videos
from data_sources.socials.tiktok import video_comments as tiktok_comments
from data_sources.socials.x import recent_posts as x_posts
from utils.log import logger

# How long listing the apps may take before a turn goes on without the list.
OVERVIEW_TIMEOUT_S = 8.0
# Reading the founder's mail, calendar and mentions: how much comes back.
EMAIL_RESULTS = 15
THREAD_MESSAGES = 20
EMAIL_CHARS = 2_000
CALENDAR_EVENTS = 50
X_MENTIONS = 20
_GMAIL_SEARCH = "GMAIL_FETCH_EMAILS"
_GMAIL_THREAD = "GMAIL_FETCH_MESSAGE_BY_THREAD_ID"
_CALENDAR_EVENTS = "GOOGLECALENDAR_EVENTS_LIST"
_X_ME = "TWITTER_USER_LOOKUP_ME"
_X_MENTIONS = "TWITTER_GET_USER_MENTIONS"
# Composio tools, verified against the live catalog.
_X_USER = "TWITTER_USER_LOOKUP_BY_USERNAME"
_X_POST = "TWITTER_POST_LOOKUP_BY_POST_ID"
_SHEET_TABS = "GOOGLESHEETS_GET_SHEET_NAMES"
_SHEET_SEARCH = "GOOGLESHEETS_SEARCH_SPREADSHEETS"
SHEET_SEARCH_RESULTS = 10
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
CALENDLY_MEETINGS = 20
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
    def __init__(self, sessions: async_sessionmaker[AsyncSession], lace_id: uuid.UUID,
                 reader_id: uuid.UUID | None = None):
        """`reader_id`: who the turn works for; only the Lace's owner may have
        it read their own mail and calendar (see _personal)."""
        self._sessions = sessions
        self._lace_id = lace_id
        self._reader_id = reader_id

    async def _personal(self, platform: str) -> _Live | None:
        """The live account for reading `platform`'s private content (mail,
        calendar). An account connected for this Lace belongs to the startup,
        so the team reads it; the founder's own shared one only they do."""
        live = await self._live(platform)
        if live is None or live.entity != connection_service.founder_entity(await self._owner()):
            return live
        if self._reader_id != await self._owner():
            raise AppError(f"This {connection_service.label(platform)} is the Lace owner's own account: only they "
                           "can have you read it. Ask them, or connect one for this Lace in its settings.")
        return live

    async def _owner(self) -> uuid.UUID | None:
        async with self._sessions() as session:
            lace = await session.get(Lace, self._lace_id)
        return lace.user_id if lace else None

    async def email_search(self, query: str, days: int) -> list[dict] | None:
        live = await self._personal("gmail")
        if live is None:
            return None
        data = await self._run(live, "gmail", _GMAIL_SEARCH, {
            "query": f"{query} newer_than:{days}d".strip(), "max_results": EMAIL_RESULTS, "include_payload": False})
        return [{"thread_id": m.get("threadId"), "from": m.get("sender"), "subject": m.get("subject"),
                 "date": m.get("messageTimestamp"), "snippet": mail_text(m).strip()[:TEXT_CHARS]}
                for m in _listed(data, "messages")[:EMAIL_RESULTS]]

    async def email_thread(self, thread_id: str) -> list[dict] | None:
        live = await self._personal("gmail")
        if live is None:
            return None
        data = await self._run(live, "gmail", _GMAIL_THREAD, {"thread_id": thread_id})
        return [{"from": m.get("sender"), "date": m.get("messageTimestamp"), "text": mail_text(m).strip()[:EMAIL_CHARS]}
                for m in _listed(data, "messages")[:THREAD_MESSAGES]]

    async def calendar_events(self, days_ahead: int) -> list[dict] | None:
        live = await self._personal("googlecalendar")
        if live is None:
            return None
        now = datetime.now(UTC)
        data = await self._run(live, "googlecalendar", _CALENDAR_EVENTS, {
            "timeMin": now.isoformat(), "timeMax": (now + timedelta(days=days_ahead)).isoformat(),
            "singleEvents": True, "orderBy": "startTime", "maxResults": CALENDAR_EVENTS})
        return [{"title": e.get("summary") or "(no title)", "start": _when(e.get("start")), "end": _when(e.get("end")),
                 "attendees": [{"name": a.get("displayName"), "email": a.get("email")}
                               for a in e.get("attendees") or [] if isinstance(a, dict) and not a.get("self")]}
                for e in _listed(data, "items")[:CALENDAR_EVENTS]]

    async def x_mentions(self) -> list[dict] | None:
        live = await self._live("x")
        if live is None:
            return None
        me = x_api._data(await self._run(live, "x", _X_ME, {}) or {})
        if not me.get("id"):
            raise AppError("X didn't say which account is connected; try again later.")
        data = await self._run(live, "x", _X_MENTIONS, {
            "id": me["id"], "max_results": X_MENTIONS, "expansions": ["author_id"],
            "tweet_fields": ["created_at"], "user_fields": ["username", "name"]})
        record = data if isinstance(data, dict) else {}
        users = {u.get("id"): u for u in ((record.get("includes") or {}).get("users") or []) if isinstance(u, dict)}
        posts = record.get("data") if isinstance(record.get("data"), list) else []
        return [{"author": users.get(p.get("author_id"), {}).get("name"),
                 "handle": users.get(p.get("author_id"), {}).get("username"), "text": (p.get("text") or "")[:TEXT_CHARS],
                 "date": p.get("created_at"), "url": f"https://x.com/i/web/status/{p.get('id')}"}
                for p in posts[:X_MENTIONS] if isinstance(p, dict)]

    async def overview(self) -> list[AppStatus]:
        try:
            async with asyncio.timeout(OVERVIEW_TIMEOUT_S), self._sessions() as session:
                lace = await session.get(Lace, self._lace_id)
                if lace is None:
                    return []
                listed = await lace_app_settings.list_for_lace(session, lace)
        except Exception as exc:  # noqa: BLE001 -- Composio raises many types; the prompt goes on without the list
            raise AppError(f"apps unavailable ({type(exc).__name__})") from exc
        return [AppStatus(platform=a["platform"], label=a["label"], connected=a["status"] is not None,
                          needs_attention=a["status"] is not None and not a["connected"], enabled=a["enabled"],
                          account=a["account"], account_name=a["account_name"],
                          handle=(a["settings"] or {}).get("handle"))
                for a in listed if a["available"] or (a["settings"] or {}).get("handle")]

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
            raise AppError(connection_service.refusal(platform, result["error"]))
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

    async def sheet_search(self, query: str) -> list[dict] | None:
        live = await self._live("googlesheets")
        if live is None:
            return None
        try:
            data = await self._run(live, "googlesheets", _SHEET_SEARCH, {
                "query": query, "search_type": "name", "max_results": SHEET_SEARCH_RESULTS,
                "order_by": "modifiedTime desc"})
        except AppError as exc:
            raise AppError(f"{exc} Until then, ask for the sheet's link.") from exc
        found = _listed(data, "spreadsheets") or _listed(data, "files")
        return [{"id": f.get("id") or f.get("spreadsheetId"), "name": f.get("name") or f.get("title"),
                 "url": f.get("webViewLink") or f"https://docs.google.com/spreadsheets/d/{f.get('id')}",
                 "modified": f.get("modifiedTime")} for f in found[:SHEET_SEARCH_RESULTS] if f.get("id")]

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

    async def _calendly_user(self, live: _Live) -> str:
        me = _calendly_body(await self._run(live, "calendly", "CALENDLY_GET_CURRENT_USER", {}))
        uri = (me.get("resource") or {}).get("uri")
        if not uri:
            raise AppError("Calendly didn't say who you are; reconnect Calendly.")
        return uri

    async def calendly_links(self) -> list[dict] | None:
        live = await self._live("calendly")
        if live is None:
            return None
        types = _calendly_body(await self._run(live, "calendly", "CALENDLY_LIST_USER_S_EVENT_TYPES", {
            "user": await self._calendly_user(live), "active": True, "count": 100}))
        return [{"name": t.get("name"), "minutes": t.get("duration"), "url": t.get("scheduling_url")}
                for t in types.get("collection") or [] if isinstance(t, dict) and t.get("scheduling_url")]

    async def calendly_meetings(self, days_back: int, days_ahead: int) -> list[dict] | None:
        live = await self._live("calendly")
        if live is None:
            return None
        now = datetime.now(UTC)
        events = _calendly_body(await self._run(live, "calendly", "CALENDLY_LIST_EVENTS", {
            "user": await self._calendly_user(live), "status": "active", "count": CALENDLY_MEETINGS,
            "sort": "start_time:asc", "min_start_time": (now - timedelta(days=days_back)).isoformat(),
            "max_start_time": (now + timedelta(days=days_ahead)).isoformat()}))
        meetings = []
        for event in (events.get("collection") or [])[:CALENDLY_MEETINGS]:
            if not isinstance(event, dict) or not event.get("uri"):
                continue
            invitees = _calendly_body(await self._run(live, "calendly", "CALENDLY_LIST_EVENT_INVITEES", {
                "uuid": event["uri"].rstrip("/").rsplit("/", 1)[-1], "status": "active"}))
            meetings.append({"name": event.get("name"), "start": event.get("start_time"), "invitees": [
                {"name": i.get("name"), "email": i.get("email")}
                for i in invitees.get("collection") or [] if isinstance(i, dict)]})
        return meetings

    async def my_posts(self, platform: str) -> list[dict] | None:
        handle = await self.handle(platform)
        if handle is None:
            return None
        read = x_posts if platform == "x" else tiktok_videos
        try:
            return await asyncio.to_thread(read, handle, settings, settings.social_read_timeout_s)
        except SocialsError as exc:
            logger.warning("Reading %s's %s posts failed: %s", handle, platform, exc)
            raise AppError(f"Couldn't read @{handle} on {connection_service.label(platform)} just now; try again later.") \
                from exc

    async def tiktok_comments(self, videos: int) -> list[dict] | None:
        handle = await self.handle("tiktok")
        if handle is None:
            return None
        try:
            listed = await asyncio.to_thread(tiktok_videos, handle, settings, settings.social_read_timeout_s)
            chosen = [v for v in listed if (v["comments"] or 0) > 0][:videos]
            read = await asyncio.gather(*(asyncio.to_thread(tiktok_comments, v["url"], settings,
                                                            settings.tiktok_comments_timeout_s) for v in chosen))
        except SocialsError as exc:
            logger.warning("Reading @%s's TikTok comments failed: %s", handle, exc)
            raise AppError(f"Couldn't read @{handle}'s TikTok comments just now; try again later.") from exc
        return [{"url": v["url"], "caption": v["text"], "comments": comments[:COMMENTS_PER_POST]}
                for v, comments in zip(chosen, read)]

    async def handle(self, platform: str) -> str | None:
        """The founder's own handle on `platform`, as saved in the Lace's settings."""
        async with self._sessions() as session:
            saved = await session.scalar(select(LaceApp.settings).where(
                LaceApp.lace_id == self._lace_id, LaceApp.platform == platform))
        return (saved or {}).get("handle")

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


def _calendly_body(data) -> dict:
    """A Calendly API response, whether or not Composio wraps it."""
    if isinstance(data, dict) and not ({"resource", "collection"} & data.keys()):
        data = next((data[k] for k in ("data", "response_data") if isinstance(data.get(k), dict)), data)
    return data if isinstance(data, dict) else {}


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


def _listed(data, key: str) -> list[dict]:
    """A list in a Composio result, whether or not it wraps the API's own."""
    found = data.get(key) if isinstance(data, dict) else None
    if found is None and isinstance(data, dict) and isinstance(data.get("data"), dict):
        found = data["data"].get(key)
    return [item for item in found or [] if isinstance(item, dict)]


def _when(moment) -> str | None:
    """A calendar event's start or end: its time, or its date for all-day events."""
    return (moment.get("dateTime") or moment.get("date")) if isinstance(moment, dict) else None
