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

    async def my_comments(self, platform: CommentsOn, posts: int) -> list[dict] | None:
        """Comments on the founder's own recent posts (their most recent
        `posts`), newest posts first: [{platform, post_url, post_text,
        comment_id, author, text, date}]. None when the app isn't connected;
        AppError when a call fails."""
        ...
