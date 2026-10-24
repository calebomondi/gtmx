"""Proposing an action in one of the founder's apps: kept for their approval
and shown under the Lace's reply with Approve and Decline. Every tool that
acts in an app goes through here; none acts directly."""

from agents.lace.store import LaceStore
from agents.schemas.lace import ProposedAction, ToolResult
from agents.schemas.lace_ui import ActionBlock


async def propose(store: LaceStore, action: ProposedAction) -> ToolResult:
    action_id = await store.propose_action(action)
    card = ActionBlock(id=action_id, app=action.app, title=action.title, preview=action.preview, status="proposed")
    return ToolResult.success(
        f"Proposed \"{action.title}\": it runs only if the founder approves it, under your reply. "
        "Say in a line what it will do, and stop.",
        {"ui": [card.model_dump()]},
    )
