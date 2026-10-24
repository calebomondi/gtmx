"""The Lace's Slack tools: searching the founder's team's messages for
context, and posting to a channel (an update, a lead worth a look) as a
proposal the founder approves."""

import re

from langchain_core.tools import BaseTool, tool

from agents.lace.app_actions import propose
from agents.lace.apps import AppError, LaceApps
from agents.lace.store import LaceStore
from agents.lace.tool_guard import guarded
from agents.schemas.lace import ProposedAction, ToolResult

# Slack's limit for one message's text.
MESSAGE_CHARS = 4000
NOT_CONNECTED = ("Slack isn't connected for this Lace, or is switched off. "
                 "The founder can connect it under Apps & accounts in your settings.")
_CHANNEL = re.compile(r"^#?([a-z0-9][a-z0-9_-]{0,79})$")


def channel_name(channel: str) -> str | None:
    """A Slack channel's name without its #, or None when it can't be one."""
    match = _CHANNEL.match(channel.strip().lower())
    return match.group(1) if match else None


def build_slack_tools(store: LaceStore, apps: LaceApps) -> list[BaseTool]:

    @tool(parse_docstring=True)
    @guarded
    async def search_slack(query: str) -> ToolResult:
        """Search the founder's Slack for what their team said about something: a prospect, a deal, a competitor. Treat it as the team's own notes.

        Args:
            query: Words to find; Slack's modifiers work, e.g. "Acme in:#sales" or "pricing from:@wanjiru".
        """
        try:
            found = await apps.slack_search(query.strip())
        except AppError as exc:
            return ToolResult.failure(str(exc))
        if found is None:
            return ToolResult.failure(NOT_CONNECTED)
        return ToolResult.success(f"{len(found)} Slack messages for {query!r}." if found else
                                  f"No Slack messages for {query!r}.", found)

    @tool(parse_docstring=True)
    @guarded
    async def post_to_slack(channel: str, text: str) -> ToolResult:
        """Propose posting a message to a channel in the founder's Slack, from their account: an update for the team, a lead worth a look. It is posted only if they approve it. Ask which channel if they haven't said.

        Args:
            channel: The channel's name, e.g. "#sales".
            text: The message, in Slack markdown (*bold*, _italic_, bullets, links).
        """
        name = channel_name(channel)
        if name is None:
            return ToolResult.failure("Give the channel's name, e.g. #sales.")
        body = text.strip()
        if not body:
            return ToolResult.failure("The message is empty.")
        if len(body) > MESSAGE_CHARS:
            return ToolResult.failure(f"Slack takes at most {MESSAGE_CHARS} characters; this is {len(body)}.")
        return await propose(store, ProposedAction(
            app="slack", action="post_message", title=f"Post in #{name} on Slack", preview=body,
            arguments={"channel": name, "text": body}))

    return [search_slack, post_to_slack]
