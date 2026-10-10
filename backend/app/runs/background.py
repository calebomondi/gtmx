"""Background run kinds: no questions, one segment from start to finish. The
runner does the agent work and the database writes; this records the outcome
on the run and publishes it, so all kinds share one lifecycle (manager)."""

import asyncio
import uuid
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime

from backend.app.account_runner import run_account_discovery_for_workspace
from backend.app.competitor_runner import research_competitor_site, run_competitor_discovery
from backend.app.database import models
from agents.pipelines.chat import workspace_chat
from backend.app.database.connect import AsyncSessionLocal
from backend.app.runs import events, signals
from backend.app.services import chat as chat_service
from backend.app.services.runs import set_run_fields


async def _finish(run_id: uuid.UUID, outcome: dict) -> None:
    run = await set_run_fields(models.Run, run_id, status="completed", finished_at=datetime.now(UTC))
    if run is not None:
        await set_run_fields(models.Run, run_id, progress={**(run.progress or {}), **outcome})
    await events.publish(run_id, "complete", outcome)


async def competitors(run_id: uuid.UUID, workspace_id: uuid.UUID, _params: dict) -> None:
    await _finish(run_id, await run_competitor_discovery(workspace_id=workspace_id, run_id=run_id))
    await signals.competitors_found(run_id)


async def accounts(run_id: uuid.UUID, workspace_id: uuid.UUID, _params: dict) -> None:
    await _finish(run_id, await run_account_discovery_for_workspace(workspace_id=workspace_id, run_id=run_id))
    await signals.accounts_found(run_id)


async def competitor_research(run_id: uuid.UUID, workspace_id: uuid.UUID, params: dict) -> None:
    """Fill in one manually added competitor from its own website. A failure
    leaves the row's `unsourced_fields` as the honest record."""
    researched = await research_competitor_site(
        workspace_id=workspace_id, competitor_id=uuid.UUID(params["competitor_id"]),
    )
    await _finish(run_id, {"researched": bool(researched)})


async def chat(run_id: uuid.UUID, workspace_id: uuid.UUID, params: dict) -> None:
    """Answer the user's latest chat message and store the reply."""
    async with AsyncSessionLocal() as db:
        run = await db.get(models.Run, run_id)
        history = [(m.role, m.content) for m in await chat_service.list_messages(db, workspace_id)]
        context, offer_name = await chat_service.workspace_context(db, workspace_id)
    question, prior = history[-1][1], history[:-1][-chat_service.HISTORY_TURNS:]
    reply = await asyncio.to_thread(workspace_chat.answer, question, context, prior, offer_name)
    async with AsyncSessionLocal() as db:
        message = await chat_service.add_assistant_message(db, workspace_id, run.user_id, run_id, reply)
    await _finish(run_id, {"message_id": str(message.id)})


EXECUTORS: dict[str, Callable[[uuid.UUID, uuid.UUID, dict], Awaitable[None]]] = {
    "competitors": competitors,
    "accounts": accounts,
    "competitor_research": competitor_research,
    "chat": chat,
}
