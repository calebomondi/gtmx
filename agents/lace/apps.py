"""What a Lace can do through the apps its founder connected, as an interface.

The backend implements it for the Lace's owner (through Composio) and hands it
to `build_lace_graph`, as it does the store: `agents/` never imports
`backend/`, and the model never names an account or a user.
"""

from typing import Literal, Protocol

XRecord = Literal["profile", "post"]
# The founder's own accounts whose post comments a Lace can read.
CommentsOn = Literal["instagram", "facebook"]


class AppError(Exception):
    """An app call that failed (refused, rate limited, timed out). The message
    is safe to show the model."""


class LaceApps(Protocol):
    async def x(self, record: XRecord, key: str) -> dict | None:
        """A profile (key: the handle) or a post (key: its id) from X, through
        the founder's connected X account: the API's record, or None when X
        isn't connected. Raises AppError when the call fails."""
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

    async def my_comments(self, platform: CommentsOn, posts: int) -> list[dict] | None:
        """Comments on the founder's own recent posts (their most recent
        `posts`), newest posts first: [{platform, post_url, post_text,
        comment_id, author, text, date}]. None when the app isn't connected;
        AppError when a call fails."""
        ...
