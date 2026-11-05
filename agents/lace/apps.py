"""What a Lace can do through the apps its founder connected, as an interface.

The backend implements it for the Lace's owner (through Composio) and hands it
to `build_lace_graph`, as it does the store: `agents/` never imports
`backend/`, and the model never names an account or a user.
"""

from typing import Literal, Protocol

from pydantic import BaseModel

XRecord = Literal["profile", "post"]
# The founder's public accounts a Lace reads by handle, with no app to connect.
PublicFeed = Literal["x", "tiktok"]
# The CRMs a Lace can read and add leads to.
CrmApp = Literal["zoho", "hubspot"]
# The founder's own accounts whose post comments a Lace can read.
CommentsOn = Literal["instagram", "facebook"]


class AppError(Exception):
    """An app call that failed (refused, rate limited, timed out). The message
    is safe to show the model."""


class AppStatus(BaseModel):
    """One app as the Lace is told about it: whether it can use it, and whose
    account it is."""
    platform: str
    label: str
    connected: bool
    # Connected but needing the founder (an expired login), or a link left pending.
    needs_attention: bool = False
    enabled: bool
    # "own": this Lace's own account; "shared": the founder's, shared by their Laces.
    account: Literal["own", "shared"] | None = None
    account_name: str | None = None
    # The founder's public handle saved for it (X, TikTok): read without connecting.
    handle: str | None = None
    # Connected, but the Page or business account this Lace speaks for isn't linked yet.
    needs_link: bool = False


class LaceApps(Protocol):
    async def email_search(self, query: str, days: int) -> list[dict] | None:
        """Mail in the founder's Gmail matching a Gmail search query, within the
        last `days`, newest first, bounded: {thread_id, from, subject, date,
        snippet}. None when no Gmail is on for this Lace. Raises AppError."""
        ...

    async def email_thread(self, thread_id: str) -> list[dict] | None:
        """One Gmail thread's messages, oldest first: {from, date, text},
        each bounded. None when no Gmail is on. Raises AppError."""
        ...

    async def calendar_events(self, days_ahead: int) -> list[dict] | None:
        """The founder's Google Calendar events from now: {id, title, start,
        end, location, join, description, organizer, attendees: [{name, email,
        response}]}. None when it isn't on. Raises AppError."""
        ...

    async def calendar_free_times(self, days: int, minutes: int) -> dict | None:
        """Free `minutes`-long slots in working hours over the next `days`:
        {timezone, slots: ["Mon 10 Nov, 14:00-14:30 (Africa/Nairobi)"]}. None
        when Google Calendar isn't on. Raises AppError."""
        ...

    async def x_mentions(self) -> list[dict] | None:
        """Recent posts on X mentioning the founder's connected account:
        {author, handle, text, date, url}. None when X isn't on. Raises AppError."""
        ...

    async def tiktok_comments(self, videos: int) -> list[dict] | None:
        """Comments on the founder's newest TikTok videos that have any, read
        by their public handle: [{url, caption, comments: [{author, text,
        date, likes}]}]. None when no TikTok handle is saved. Slow (minutes).
        Raises AppError when the read fails."""
        ...

    async def overview(self) -> list[AppStatus]:
        """Every app: connected or not, whose account, and whether this Lace
        may use it. Raises AppError when it can't be found out."""
        ...

    async def x(self, record: XRecord, key: str) -> dict | None:
        """A profile (key: the handle) or a post (key: its id) from X, through
        the founder's connected X account: the API's record, or None when X
        isn't connected. Raises AppError when the call fails."""
        ...

    async def sheet_search(self, query: str) -> list[dict] | None:
        """Spreadsheets in the founder's Drive whose names match, newest first:
        {id, name, url, modified}. None when Google Sheets isn't on. Raises
        AppError, saying so when the connection can't search Drive."""
        ...

    async def sheet(self, spreadsheet_id: str, tab: str | None) -> dict | None:
        """One tab of a Google Sheet the founder can open (the first when
        `tab` is None): {tabs, tab, rows}, rows as lists of cell text with the
        header first, bounded. None when Google Sheets isn't connected or is
        switched off; AppError when the call fails."""
        ...

    async def notion_search(self, query: str) -> list[dict] | None:
        """Pages and databases in the founder's Notion whose titles match:
        [{id, title, url, kind}], bounded. None when Notion isn't connected or
        is switched off; AppError when the call fails."""
        ...

    async def notion_page(self, page_id: str) -> str | None:
        """A Notion page's text, as markdown-ish lines (headings, bullets,
        to-dos), bounded. None when Notion isn't connected or is switched off;
        AppError when the call fails."""
        ...

    async def slack_search(self, query: str) -> list[dict] | None:
        """Messages in the founder's Slack matching `query` (Slack's search
        syntax: in:#channel, from:@name): [{text, author, channel, date,
        link}], newest first, bounded. None when Slack isn't connected or is
        switched off; AppError when the call fails."""
        ...

    async def asana_tasks(self) -> list[dict] | None:
        """The founder's open Asana tasks (assigned to them): [{name, due_on,
        project, link}], bounded. None when Asana isn't connected or is
        switched off; AppError when the call fails."""
        ...

    async def crm(self) -> CrmApp | None:
        """The CRM this Lace uses (connected and switched on), if any."""
        ...

    async def crm_deals(self) -> list[dict] | None:
        """The deals in the Lace's CRM, newest first, bounded: [{name,
        company, stage, amount, close_date, updated, closed, won}]. None
        without a CRM; AppError when a call fails."""
        ...

    async def crm_find(self, query: str) -> list[dict] | None:
        """Leads, contacts and companies in the Lace's CRM whose name, company
        or email contains `query`: [{kind, name, company, email}], bounded.
        None without a CRM; AppError when a call fails."""
        ...

    async def calendly_links(self) -> list[dict] | None:
        """The founder's active Calendly event types: [{name, minutes, url}].
        None when Calendly isn't connected or is switched off; AppError when
        the call fails."""
        ...

    async def calendly_meetings(self, days_back: int, days_ahead: int) -> list[dict] | None:
        """Meetings booked on the founder's Calendly in that window, soonest
        first, bounded: [{name, start, invitees: [{name, email}]}]. None when
        Calendly isn't connected or is switched off; AppError when a call fails."""
        ...

    async def my_posts(self, platform: PublicFeed) -> list[dict] | None:
        """The founder's recent public posts on X or videos on TikTok, read by
        the handle saved in the Lace's settings (no app connected), newest
        first: [{url, text, date, views, likes, ...}]. None when no handle is
        saved; AppError when the read fails."""
        ...

    async def my_comments(self, platform: CommentsOn, posts: int) -> list[dict] | None:
        """Comments on the founder's own recent posts (their most recent
        `posts`), newest posts first: [{platform, post_url, post_text,
        comment_id, author, text, date}]. None when the app isn't connected;
        AppError when a call fails."""
        ...
