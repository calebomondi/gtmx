"""In-process scheduler: keeps every active workspace's competitor monitoring
fresh. Single-instance by design for launch (one backend process); a
multi-instance deployment needs a leader lock or an external scheduler."""

import asyncio
from datetime import UTC, datetime, timedelta

from sqlalchemy import func, or_, select

from backend.app.database import models
from backend.app.database.connect import AsyncSessionLocal
from backend.app.runs import manager
from backend.app.services.errors import RateLimitedError
from backend.app.services.runs import TERMINAL_STATUSES
from config import settings
from utils.log import logger

_task: asyncio.Task | None = None


async def _stale_workspaces() -> list[tuple]:
    """(workspace_id, user_id) of live workspaces with a competitor that was
    never checked or is past the max age, and no monitor run in flight."""
    cutoff = datetime.now(UTC) - timedelta(hours=settings.monitor_max_age_h)
    in_flight = select(models.Run.workspace_id).where(
        models.Run.kind == "monitor", models.Run.status.not_in(TERMINAL_STATUSES),
    )
    async with AsyncSessionLocal() as db:
        rows = await db.execute(
            select(models.Workspace.id, models.Workspace.user_id)
            .join(models.Competitor, models.Competitor.workspace_id == models.Workspace.id)
            .where(
                models.Workspace.archived.is_(False),
                or_(models.Competitor.last_checked_at.is_(None), models.Competitor.last_checked_at < cutoff),
                models.Workspace.id.not_in(in_flight),
            )
            .group_by(models.Workspace.id, models.Workspace.user_id)
            .having(func.count(models.Competitor.id) > 0)
        )
        return list(rows.all())


async def sweep() -> int:
    """Start a monitor run for each stale workspace. Returns how many started."""
    started = 0
    for workspace_id, user_id in await _stale_workspaces():
        try:
            await manager.start_background("monitor", user_id, workspace_id)
            started += 1
        except RateLimitedError:
            continue  # this user hit the daily cap; try again next sweep
    return started


async def _loop() -> None:
    await asyncio.sleep(settings.monitor_initial_delay_s)
    while True:
        try:
            started = await sweep()
            if started:
                logger.info("Monitoring sweep started %d run(s)", started)
        except Exception:  # noqa: BLE001 -- the scheduler must outlive one bad sweep
            logger.exception("Monitoring sweep failed")
        await asyncio.sleep(settings.monitor_scan_interval_s)


def start() -> None:
    global _task
    if _task is None and settings.monitor_enabled:
        _task = asyncio.create_task(_loop(), name="monitor-scheduler")


async def stop() -> None:
    global _task
    if _task is not None:
        _task.cancel()
        await asyncio.gather(_task, return_exceptions=True)
        _task = None
