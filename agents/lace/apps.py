"""What a Lace can do through the apps its founder connected, as an interface.

The backend implements it for the Lace's owner (through Composio) and hands it
to `build_lace_graph`, as it does the store: `agents/` never imports
`backend/`, and the model never names an account or a user.
"""

from typing import Literal, Protocol

XRecord = Literal["profile", "post"]


class AppError(Exception):
    """An app call that failed (refused, rate limited, timed out). The message
    is safe to show the model."""


class LaceApps(Protocol):
    async def x(self, record: XRecord, key: str) -> dict | None:
        """A profile (key: the handle) or a post (key: its id) from X, through
        the founder's connected X account: the API's record, or None when X
        isn't connected. Raises AppError when the call fails."""
        ...
