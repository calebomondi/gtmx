"""The Lace's Telegram tools: posting to the startup's channel, through the
founder's bot, as a proposal they approve. A bot can only post where it was
added (a channel where it is an admin, a group it is in)."""

import re

from langchain_core.tools import BaseTool, tool

from agents.lace.app_actions import propose
from agents.lace.store import LaceStore
from agents.lace.tool_guard import guarded
from agents.schemas.lace import ProposedAction, ToolResult

# Telegram's limit for one message.
MESSAGE_CHARS = 4096
_USERNAME = re.compile(r"^(?:@|(?:https?://)?(?:t\.me|telegram\.me)/)([A-Za-z][A-Za-z0-9_]{4,31})/?$", re.I)
_CHAT_ID = re.compile(r"^-?\d{5,20}$")


def chat_target(value: str) -> str | None:
    """Where a bot can send: a public channel or group as "@name" (from @name
    or a t.me link), or a chat's numeric id; None for anything else."""
    text = (value or "").strip()
    if _CHAT_ID.match(text):
        return text
    match = _USERNAME.match(text)
    return f"@{match.group(1)}" if match else None


def build_telegram_tools(store: LaceStore) -> list[BaseTool]:

    @tool(parse_docstring=True)
    @guarded
    async def post_to_telegram(channel: str, text: str) -> ToolResult:
        """Propose posting to the startup's Telegram channel or group through the founder's bot: an announcement or an update. It is posted only if they approve it. The bot must be an admin of the channel.

        Args:
            channel: The channel's @name or t.me link, or a chat id.
            text: The post, exactly as it will appear.
        """
        target = chat_target(channel)
        if target is None:
            return ToolResult.failure("Give the channel's @name or its t.me link.")
        body = text.strip()
        if not body:
            return ToolResult.failure("The post is empty.")
        if len(body) > MESSAGE_CHARS:
            return ToolResult.failure(f"Telegram takes at most {MESSAGE_CHARS} characters; this is {len(body)}.")
        return await propose(store, ProposedAction(
            app="telegram", action="send_message", title=f"Post in {target} on Telegram", preview=body,
            arguments={"chat_id": target, "text": body}))

    return [post_to_telegram]
