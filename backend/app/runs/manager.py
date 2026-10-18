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
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.database import models
from backend.app.database.connect import AsyncSessionLocal
from backend.app.runs import background, discovery, events
from agents.lace.store import JobRefused
from backend.app.runs import lace as lace_runs
from backend.app.runs import signals as run_signals
from backend.app.runs.errors import user_facing_error
from backend.app.schemas.agents import DiscoveryRequest
from backend.app.services import limits
from backend.app.services import runs as run_service
from backend.app.services import lace_events
from backend.app.services.errors import ConflictError, InvalidInputError, NotFoundError, RateLimitedError
from backend.app.services.runs import TERMINAL_STATUSES, set_run_fields
from config import settings
from utils.log import current_run_id, current_user_id, logger

_tasks: dict[uuid.UUID, asyncio.Task] = {}

_RESTART_MESSAGE = "The server restarted while this run was working. Please start it again."


def _spawn(run_id: uuid.UUID, user_id: uuid.UUID, segment: Coroutine, timeout_s: float) -> None:
    async def guarded() -> None:
        # Bills every LLM/API call this segment makes (in any worker thread) to
        # the run, and tags its log lines with the run and user.
        current_run_id.set(str(run_id))
        current_user_id.set(str(user_id))
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
    _spawn(run.id, user_id, discovery.run_segment(run.id, discovery.build_initial_state(request)),
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
    _spawn(run.id, user_id, executor(run.id, workspace_id, params or {}), settings.background_run_timeout_s)
    return run


async def _start_lace_run(kind: str, user_id: uuid.UUID, lace_id: uuid.UUID, params: dict | None) -> models.Run:
    async with AsyncSessionLocal() as db:
        await limits.ensure_can_start(db, user_id, kind)
        run = models.Run(user_id=user_id, lace_id=lace_id, kind=kind, status="running", input=params,
                         started_at=datetime.now(UTC))
        db.add(run)
        try:
            await db.commit()
        except IntegrityError as exc:
            if "uq_runs_one_active_per_lace" not in str(exc):
                raise
            raise ConflictError("Your Lace is still working on the last message.") from None
    return run


async def start_lace_onboarding(user_id: uuid.UUID, lace_id: uuid.UUID) -> models.Run:
    run = await _start_lace_run("lace_onboarding", user_id, lace_id, None)
    _spawn(run.id, user_id, _then_wake(lace_runs.onboarding_segment(run.id, lace_id), user_id, lace_id),
           settings.lace_onboarding_timeout_s)
    return run


async def start_lace_turn(user_id: uuid.UUID, lace_id: uuid.UUID, text: str) -> models.Run:
    """One founder message and the Lace's work on it. The caller has already
    checked that `lace_id` is the user's."""
    text = text.strip()
    if not text:
        raise InvalidInputError("Write a message first.")
    run = await _start_lace_run("lace_turn", user_id, lace_id, {"text": text})
    _spawn_turn(run.id, user_id, lace_id, lace_runs.founder_message(text))
    return run


def _spawn_turn(run_id: uuid.UUID, user_id: uuid.UUID, lace_id: uuid.UUID, message) -> None:
    turn = lace_runs.turn_segment(run_id, lace_id, message, jobs=_LaceJobs(user_id, lace_id))
    _spawn(run_id, user_id, _then_wake(turn, user_id, lace_id), settings.lace_turn_timeout_s)


async def _then_wake(segment: Coroutine, user_id: uuid.UUID, lace_id: uuid.UUID) -> None:
    """Run a conversation segment, then pass on any updates that queued while
    it was busy. Only after success: a failed turn leaves them queued for the
    founder's next message."""
    await segment
    await wake_lace(user_id, lace_id)


async def wake_lace(user_id: uuid.UUID, lace_id: uuid.UUID) -> None:
    """Start a turn carrying the Lace's queued updates, if it has any and is
    not already in a conversation run; that run calls this again when it ends.
    Not counted against the daily turn cap: updates come from jobs the founder
    started, which are capped themselves."""
    try:
        async with AsyncSessionLocal() as db, db.begin():
            updates = await lace_events.take_pending(db, lace_id)
            if not updates:
                return
            run = models.Run(user_id=user_id, lace_id=lace_id, kind="lace_turn", status="running",
                             input={"updates": updates}, started_at=datetime.now(UTC))
            db.add(run)
            await db.flush()
    except IntegrityError as exc:
        if "uq_runs_one_active_per_lace" not in str(exc):
            raise
        return  # rolled back: the updates stay queued for the running turn to pick up
    _spawn_turn(run.id, user_id, lace_id, lace_runs.event_message(updates))


# The run kind behind each job a Lace's tools can start.
_TOOL_JOB_RUN_KINDS = {"find_competitors": "lace_competitors", "check_competitors": "lace_monitor",
                       "find_accounts": "lace_accounts", "find_contacts": "lace_contacts"}
_JOB_SEGMENTS = {"lace_competitors": lace_runs.competitors_job, "lace_monitor": lace_runs.monitor_job,
                 "lace_accounts": lace_runs.accounts_job, "lace_contacts": lace_runs.contacts_job}
_JOB_BUSY = {
    "lace_competitors": "A competitor search is already running; I'll report when it's done.",
    "lace_monitor": "I'm already checking the competitors; I'll report anything that matters.",
    "lace_accounts": "A search for target accounts is already running; I'll report when it's done.",
    "lace_contacts": "A contact search is already running; I'll report when it's done.",
}


async def start_lace_job(run_kind: str, user_id: uuid.UUID, lace_id: uuid.UUID, params: dict) -> models.Run:
    """Start a Lace's background job. It runs alongside the conversation and,
    when it ends (either way), wakes the Lace with whatever it queued. Raises
    JobRefused while one of the same kind is running or past the daily cap."""
    async with AsyncSessionLocal() as db:
        busy = await db.scalar(select(func.count()).select_from(models.Run).where(
            models.Run.lace_id == lace_id, models.Run.kind == run_kind,
            models.Run.status.not_in(TERMINAL_STATUSES)))
        if busy:
            raise JobRefused(_JOB_BUSY[run_kind])
        try:
            await limits.ensure_can_start(db, user_id, run_kind)
        except RateLimitedError as exc:
            raise JobRefused(str(exc)) from None
        run = models.Run(user_id=user_id, lace_id=lace_id, kind=run_kind, status="running",
                         input=params, started_at=datetime.now(UTC))
        db.add(run)
        await db.commit()
    _spawn(run.id, user_id, _job_then_wake(_JOB_SEGMENTS[run_kind](run.id, lace_id, params), user_id, lace_id),
           settings.background_run_timeout_s)
    return run


async def _job_then_wake(job: Coroutine, user_id: uuid.UUID, lace_id: uuid.UUID) -> None:
    # Jobs queue an update even when they fail, so wake either way. A job run
    # is not a conversation run, so its own row never blocks the wake.
    try:
        await job
    finally:
        await wake_lace(user_id, lace_id)


class _LaceJobs:
    """The jobs a Lace's tools start, for one Lace."""

    def __init__(self, user_id: uuid.UUID, lace_id: uuid.UUID):
        self._user_id, self._lace_id = user_id, lace_id

    async def start(self, kind: str, params: dict) -> str:
        run = await start_lace_job(_TOOL_JOB_RUN_KINDS[kind], self._user_id, self._lace_id, params)
        return str(run.id)


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
    _spawn(run_id, user_id, discovery.run_segment(run_id, Command(resume=text)), settings.discovery_segment_timeout_s)


async def cancel(user_id: uuid.UUID, run_id: uuid.UUID) -> models.Run:
    async with AsyncSessionLocal() as db:
        run = await run_service.get_owned(db, user_id, run_id)
        return await _cancel(db, run, "Run cancelled.")


async def cancel_any(run_id: uuid.UUID, message: str) -> models.Run:
    """Cancel any user's run. Admin-only: callers are behind require_admin."""
    async with AsyncSessionLocal() as db:
        run = await db.get(models.Run, run_id)
        if run is None:
            raise NotFoundError("Run not found")
        return await _cancel(db, run, message)


async def _cancel(db: AsyncSession, run: models.Run, message: str) -> models.Run:
    if run.status in TERMINAL_STATUSES:
        return run
    run.status = "cancelled"
    run.finished_at = datetime.now(UTC)
    await db.commit()
    task = _tasks.pop(run.id, None)
    if task is not None:
        task.cancel()
    await events.publish(run.id, "cancelled", {"message": message})
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
