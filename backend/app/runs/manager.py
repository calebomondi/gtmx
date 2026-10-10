"""Starts, resumes and cancels runs. Each active segment is an asyncio task
owned by this process -- never by a request or a socket -- with a wall-clock
timeout. A failure is recorded on the run and published as an `error` frame;
nothing is left `running` forever.

Single-process by design for launch: tasks live in this process's memory. A
restart fails in-flight segments (recover_after_restart) while runs paused for
an answer stay resumable from their checkpoint.
"""

import asyncio
import uuid
from collections.abc import Coroutine
from datetime import UTC, datetime

from langgraph.types import Command
from sqlalchemy import select

from agents.llm import main as llm
from backend.app.database import models
from backend.app.database.connect import AsyncSessionLocal
from backend.app.runs import background, discovery, events
from backend.app.runs import signals as run_signals
from backend.app.runs.errors import user_facing_error
from backend.app.schemas.agents import DiscoveryRequest
from backend.app.services import limits
from backend.app.services import runs as run_service
from backend.app.services.errors import ConflictError, InvalidInputError
from backend.app.services.runs import TERMINAL_STATUSES, set_run_fields
from config import settings
from utils.log import logger

_tasks: dict[uuid.UUID, asyncio.Task] = {}

_RESTART_MESSAGE = "The server restarted while this run was working. Please start it again."


def _spawn(run_id: uuid.UUID, segment: Coroutine, timeout_s: float) -> None:
    async def guarded() -> None:
        # Bills every LLM call this segment makes (in any worker thread) to the run.
        llm.current_run_id.set(str(run_id))
        try:
            async with asyncio.timeout(timeout_s):
                await segment
        except asyncio.CancelledError:
            raise  # cancel() already recorded the outcome
        except Exception as exc:  # noqa: BLE001 -- recorded on the run and published
            logger.exception("Run %s failed", run_id)
            message = user_facing_error(exc)
            await set_run_fields(models.Run, run_id, status="failed", error=message, finished_at=datetime.now(UTC))
            await events.publish(run_id, "error", {"message": message})
            await run_signals.run_failed(run_id, message)
        finally:
            _tasks.pop(run_id, None)

    _tasks[run_id] = asyncio.create_task(guarded(), name=f"run:{run_id}")


async def start_discovery(user_id: uuid.UUID, request: DiscoveryRequest) -> models.Run:
    async with AsyncSessionLocal() as db:
        await limits.ensure_can_start(db, user_id, "discovery")
        run = models.Run(
            user_id=user_id,
            kind="discovery",
            status="running",
            input=request.model_dump(mode="json"),
            started_at=datetime.now(UTC),
        )
        db.add(run)
        await db.commit()
    _spawn(run.id, discovery.run_segment(run.id, discovery.build_initial_state(request)),
           settings.discovery_segment_timeout_s)
    return run


async def start_background(
    kind: str,
    user_id: uuid.UUID,
    workspace_id: uuid.UUID,
    *,
    params: dict | None = None,
    progress: dict | None = None,
) -> models.Run:
    """Start a non-interactive run (competitors, accounts, competitor_research)
    under the same lifecycle as discovery: timeout, failure recording, restart
    recovery, event log. `params` is kept as the run's input."""
    executor = background.EXECUTORS[kind]
    async with AsyncSessionLocal() as db:
        await limits.ensure_can_start(db, user_id, kind)
        run = models.Run(
            user_id=user_id,
            workspace_id=workspace_id,
            kind=kind,
            status="running",
            input=params,
            progress=progress,
            started_at=datetime.now(UTC),
        )
        db.add(run)
        await db.commit()
    _spawn(run.id, executor(run.id, workspace_id, params or {}), settings.background_run_timeout_s)
    return run


async def answer(user_id: uuid.UUID, run_id: uuid.UUID, text: str) -> None:
    """Resume a run paused on a question with the user's answer."""
    text = (text or "").strip()
    if not text:
        raise InvalidInputError("An answer is required.")
    async with AsyncSessionLocal() as db:
        await run_service.get_owned(db, user_id, run_id)  # 404 for someone else's run
        if not await run_service.claim_for_resume(db, user_id, run_id):
            raise ConflictError("This run is not waiting for an answer.")
    await events.publish(run_id, "answered", {"answer": text})
    _spawn(run_id, discovery.run_segment(run_id, Command(resume=text)), settings.discovery_segment_timeout_s)


async def cancel(user_id: uuid.UUID, run_id: uuid.UUID) -> models.Run:
    async with AsyncSessionLocal() as db:
        run = await run_service.get_owned(db, user_id, run_id)
        if run.status in TERMINAL_STATUSES:
            return run
        run.status = "cancelled"
        run.finished_at = datetime.now(UTC)
        await db.commit()
    task = _tasks.pop(run_id, None)
    if task is not None:
        task.cancel()
    await events.publish(run_id, "cancelled", {"message": "Run cancelled."})
    return run


async def recover_after_restart() -> None:
    """Fail segments that were mid-flight when the process died; their tasks
    are gone. Runs awaiting an answer need nothing: they resume on answer."""
    async with AsyncSessionLocal() as db:
        stranded = (await db.execute(
            select(models.Run.id).where(models.Run.status.in_(("pending", "running")))
        )).scalars().all()
    for run_id in stranded:
        if run_id in _tasks:
            continue
        await set_run_fields(models.Run, run_id, status="failed", error=_RESTART_MESSAGE, finished_at=datetime.now(UTC))
        await events.publish(run_id, "error", {"message": _RESTART_MESSAGE})
    if stranded:
        logger.warning("Marked %d interrupted run(s) failed after restart", len(stranded))


async def shutdown() -> None:
    """Cancel live segments on graceful shutdown; recover_after_restart marks
    them failed on the next boot."""
    for task in list(_tasks.values()):
        task.cancel()
    if _tasks:
        await asyncio.gather(*_tasks.values(), return_exceptions=True)
