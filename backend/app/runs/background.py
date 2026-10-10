"""Background run kinds: no questions, one segment from start to finish. The
runner does the agent work and the database writes; this records the outcome
on the run and publishes it, so all kinds share one lifecycle (manager)."""

import uuid
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime

from backend.app.account_runner import run_account_discovery_for_workspace
from backend.app.competitor_runner import research_competitor_site, run_competitor_discovery
from backend.app.database import models
from backend.app.runs import events, signals
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


EXECUTORS: dict[str, Callable[[uuid.UUID, uuid.UUID, dict], Awaitable[None]]] = {
    "competitors": competitors,
    "accounts": accounts,
    "competitor_research": competitor_research,
}
