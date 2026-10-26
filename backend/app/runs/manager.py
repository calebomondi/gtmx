"""Starts, resumes and cancels runs. Each active segment is an asyncio task
owned by this process -- never by a request or a socket -- with a wall-clock
timeout. A failure is recorded on the run and published as an `error` frame;
nothing is left `running` forever.

Single-process by design for launch: tasks live in this process's memory. A
restart fails in-flight segments (recover_after_restart).
"""

import asyncio
import uuid
from collections.abc import Awaitable, Callable, Coroutine
from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.database import models
from backend.app.database.connect import AsyncSessionLocal
from backend.app.database.lace_models import Lace
from backend.app.runs import events
from agents.lace.store import JobRefused
from agents.schemas.lace_ui import BlockAnswer
from backend.app.runs import lace as lace_runs
from backend.app.runs import lace_jobs, social_jobs
from backend.app.runs.errors import user_facing_error
from backend.app.services import limits
from backend.app.services import runs as run_service
from backend.app.services import lace_events
from backend.app.services.errors import ConflictError, InvalidInputError, NotFoundError, RateLimitedError
from backend.app.services.runs import TERMINAL_STATUSES, set_run_fields
from config import settings
from utils.log import current_run_id, current_user_id, logger

_tasks: dict[uuid.UUID, asyncio.Task] = {}

_RESTART_MESSAGE = "The server restarted while this run was working. Please start it again."


def _spawn(run_id: uuid.UUID, user_id: uuid.UUID, segment: Coroutine, timeout_s: float,
           then: Callable[[], Awaitable] | None = None) -> None:
    """Run a segment as the run's task. `then` follows once the run's outcome
    is recorded, however it ended, unless it was cancelled (the canceller
    follows up itself)."""
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
        finally:
            _tasks.pop(run_id, None)
        if then is not None:
            try:
                await then()
            except Exception:  # noqa: BLE001 -- the run is over; what follows retries on the next run's end
                logger.exception("Follow-up after run %s failed", run_id)

    _tasks[run_id] = asyncio.create_task(guarded(), name=f"run:{run_id}")


async def _archived(db: AsyncSession, lace_id: uuid.UUID) -> bool:
    """An archived Lace does no work until it is restored."""
    return await db.scalar(select(Lace.status).where(Lace.id == lace_id)) == "archived"


# A Lace answers one message at a time; the people on it can leave this many more waiting.
MAX_QUEUED_TURNS = 3
_QUEUED = "queued"
# The runs a Lace has one of at a time (uq_runs_one_active_per_lace).
_CONVERSATION_KINDS = ("lace_onboarding", "lace_turn")


class LaceBusy(ConflictError):
    """The Lace is in a conversation run (another message, its brief)."""


async def _start_lace_run(kind: str, user_id: uuid.UUID, lace_id: uuid.UUID, params: dict | None) -> models.Run:
    async with AsyncSessionLocal() as db:
        if await _archived(db, lace_id):
            raise ConflictError("This Lace is archived. Restore it first.")
        await limits.ensure_can_start(db, user_id, kind)
        run = models.Run(user_id=user_id, lace_id=lace_id, kind=kind, status="running", input=params,
                         started_at=datetime.now(UTC))
        db.add(run)
        try:
            await db.commit()
        except IntegrityError as exc:
            if "uq_runs_one_active_per_lace" not in str(exc):
                raise
            raise LaceBusy("Your Lace is still working on the last message.") from None
    return run


async def _queue_turn(user_id: uuid.UUID, lace_id: uuid.UUID, params: dict) -> models.Run:
    """Keep a message for when the Lace is free: it is answered after the
    ones before it (start_next_queued). Refused past MAX_QUEUED_TURNS."""
    async with AsyncSessionLocal() as db:
        waiting = await db.scalar(select(func.count()).select_from(models.Run).where(
            models.Run.lace_id == lace_id, models.Run.kind == "lace_turn", models.Run.status == _QUEUED))
        if (waiting or 0) >= MAX_QUEUED_TURNS:
            raise ConflictError(f"{waiting} messages are already waiting for your Lace; try again in a moment.")
        await limits.ensure_can_start(db, user_id, "lace_turn")
        run = models.Run(user_id=user_id, lace_id=lace_id, kind="lace_turn", status=_QUEUED, input=params)
        db.add(run)
        await db.commit()
    # The turn it waited for may have ended between the refusal and the insert.
    await start_next_queued(lace_id)
    return run


async def start_next_queued(lace_id: uuid.UUID) -> bool:
    """Start the Lace's oldest waiting message, if the Lace is free. True when
    one started (its own end starts the next); a waiting answer to a question
    that is no longer open fails with the reason and the next is tried."""
    while True:
        async with AsyncSessionLocal() as db:
            run = await db.scalar(select(models.Run).where(
                models.Run.lace_id == lace_id, models.Run.kind == "lace_turn", models.Run.status == _QUEUED,
            ).order_by(models.Run.created_at).limit(1).with_for_update(skip_locked=True))
            if run is None:
                return False
            run.status, run.started_at = "running", datetime.now(UTC)
            try:
                await db.commit()
            except IntegrityError as exc:
                if "uq_runs_one_active_per_lace" not in str(exc):
                    raise
                return False  # a turn started first; its end starts this one
            run_id, user_id, params = run.id, run.user_id, dict(run.input or {})
        try:
            message = await _queued_message(lace_id, params)
        except (ConflictError, InvalidInputError) as exc:  # its question was answered meanwhile
            reason = str(exc)
        except Exception as exc:  # noqa: BLE001 -- a run left running with no task would block the Lace
            logger.exception("Waiting message %s could not be started", run_id)
            reason = user_facing_error(exc)
        else:
            _spawn_turn(run_id, user_id, lace_id, message, actor_id=user_id)
            return True
        await set_run_fields(models.Run, run_id, status="failed", error=reason, finished_at=datetime.now(UTC))
        await events.publish(run_id, "error", {"message": reason})


async def _queued_message(lace_id: uuid.UUID, params: dict):
    author, name = params["author"], params.get("name_for_lace")
    if params.get("answer"):
        answer = BlockAnswer.model_validate(params["answer"])
        return lace_runs.signed(await lace_runs.answer_message(lace_id, answer), author, name)
    return lace_runs.signed(lace_runs.founder_message(params.get("text", ""), params.get("documents"),
                                                      params.get("draft")), author, name)


async def start_lace_onboarding(user_id: uuid.UUID, lace_id: uuid.UUID) -> models.Run:
    run = await _start_lace_run("lace_onboarding", user_id, lace_id, None)
    _spawn(run.id, user_id, _then_wake(lace_runs.onboarding_segment(run.id, lace_id), user_id, lace_id),
           settings.lace_onboarding_timeout_s, then=_next_queued(lace_id))
    return run


async def start_lace_turn(user_id: uuid.UUID, lace_id: uuid.UUID, text: str, author: dict,
                          name_for_lace: str | None, attachments: list[dict] | None = None,
                          draft: dict | None = None) -> tuple[models.Run, bool]:
    """One founder message and the Lace's work on it, with any documents
    attached ([{id, filename}], already checked to be the Lace's) and the
    unsent draft it is about, if any (lace_outreach.unsent_draft). The caller
    has already checked that the user is on the Lace. `author` and
    `name_for_lace` sign the message (lace_runs.signed). While the Lace is
    busy the message waits its turn: (run, True) for a queued one."""
    text = text.strip()
    if not text and not attachments:
        raise InvalidInputError("Write a message first.")
    params = {"text": text, **({"documents": attachments} if attachments else {}),
              **({"draft_id": draft["id"]} if draft else {})}
    try:
        run = await _start_lace_run("lace_turn", user_id, lace_id, params)
    except LaceBusy:
        return await _queue_turn(user_id, lace_id, {**params, "draft": draft, "author": author,
                                                     "name_for_lace": name_for_lace}), True
    message = lace_runs.signed(lace_runs.founder_message(text, attachments, draft), author, name_for_lace)
    _spawn_turn(run.id, user_id, lace_id, message, actor_id=user_id)
    return run, False


async def start_lace_answer(user_id: uuid.UUID, lace_id: uuid.UUID, answer: BlockAnswer, author: dict,
                            name_for_lace: str | None) -> tuple[models.Run, bool]:
    """The founder's answer to a question under the Lace's latest reply (a
    choice, checklist or form), and the Lace's work on it; queued like a
    message while the Lace is busy, and checked again when its turn comes."""
    message = lace_runs.signed(await lace_runs.answer_message(lace_id, answer), author, name_for_lace)
    try:
        run = await _start_lace_run("lace_turn", user_id, lace_id, {"answer": answer.model_dump()})
    except LaceBusy:
        return await _queue_turn(user_id, lace_id, {"answer": answer.model_dump(), "author": author,
                                                     "name_for_lace": name_for_lace}), True
    _spawn_turn(run.id, user_id, lace_id, message, actor_id=user_id)
    return run, False


def _spawn_turn(run_id: uuid.UUID, user_id: uuid.UUID, lace_id: uuid.UUID, message,
                actor_id: uuid.UUID | None) -> None:
    """`actor_id`: the person the turn answers, None for a turn of updates."""
    turn = lace_runs.turn_segment(run_id, lace_id, message, jobs=_LaceJobs(user_id, lace_id, actor_id),
                                  actor_id=actor_id)
    _spawn(run_id, user_id, _then_wake(turn, user_id, lace_id), settings.lace_turn_timeout_s,
           then=_next_queued(lace_id))


def _next_queued(lace_id: uuid.UUID) -> Callable[[], Awaitable]:
    """What follows a conversation run: the next waiting message. If the
    run's own wake started a turn of updates, that turn's end starts it."""
    return lambda: start_next_queued(lace_id)


async def _then_wake(segment: Coroutine, user_id: uuid.UUID, lace_id: uuid.UUID) -> None:
    """Run a conversation segment, then pass on any updates that queued while
    it was busy. Only after success: a failed turn leaves them queued for
    the next message."""
    await segment
    await wake_lace(user_id, lace_id)


async def wake_lace(user_id: uuid.UUID, lace_id: uuid.UUID) -> None:
    """Start a turn carrying the Lace's queued updates, if it has any and is
    not already in a conversation run; that run calls this again when it ends.
    Not counted against the daily turn cap: updates come from jobs the founder
    started, which are capped themselves."""
    try:
        async with AsyncSessionLocal() as db, db.begin():
            # Its updates stay queued for when it is restored.
            if await _archived(db, lace_id):
                return
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
    _spawn_turn(run.id, user_id, lace_id, lace_runs.event_message(updates), actor_id=None)


async def post_brief(user_id: uuid.UUID, lace_id: uuid.UUID, brief_id: uuid.UUID, request: str) -> bool:
    """Start the turn in which the Lace writes its brief. False when the Lace
    is in a conversation run: the brief stays pending for the next sweep."""
    try:
        async with AsyncSessionLocal() as db, db.begin():
            if await _archived(db, lace_id):
                return False
            run = models.Run(user_id=user_id, lace_id=lace_id, kind="lace_turn", status="running",
                             input={"brief_id": str(brief_id)}, started_at=datetime.now(UTC))
            db.add(run)
            await db.flush()
    except IntegrityError as exc:
        if "uq_runs_one_active_per_lace" not in str(exc):
            raise
        return False
    brief = lace_runs.brief_segment(run.id, lace_id, brief_id, request, jobs=_LaceJobs(user_id, lace_id, None))
    _spawn(run.id, user_id, _then_wake(brief, user_id, lace_id), settings.lace_turn_timeout_s,
           then=_next_queued(lace_id))
    return True


# The run kind behind each job a Lace's tools can start.
_TOOL_JOB_RUN_KINDS = {"find_competitors": "lace_competitors", "check_competitors": "lace_monitor",
                       "find_accounts": "lace_accounts", "find_contacts": "lace_contacts", "define_icp": "lace_icp",
                       "draft_outreach": "lace_drafts", "find_opportunities": "lace_opportunities",
                       "read_tiktok_comments": "lace_comments"}
_JOB_SEGMENTS = {"lace_competitors": lace_jobs.competitors_job, "lace_monitor": lace_jobs.monitor_job,
                 "lace_accounts": lace_jobs.accounts_job, "lace_contacts": lace_jobs.contacts_job,
                 "lace_icp": lace_jobs.icp_job,
                 "lace_drafts": lace_jobs.drafts_job, "lace_reply": lace_jobs.reply_job,
                 "lace_opportunities": lace_jobs.opportunities_job,
                 "lace_comments": social_jobs.tiktok_comments_job}
_JOB_BUSY = {
    "lace_competitors": "A competitor search is already running; I'll report when it's done.",
    "lace_monitor": "I'm already checking the competitors; I'll report anything that matters.",
    "lace_accounts": "A search for target accounts is already running; I'll report when it's done.",
    "lace_icp": "I'm already working out the ideal customer profile; I'll report when it's done.",
    "lace_contacts": "A contact search is already running; I'll report when it's done.",
    "lace_drafts": "I'm already drafting messages; I'll report when they're ready.",
    # A running reply job reads every unread reply before it ends, new ones too.
    "lace_reply": "Replies are already being read.",
    "lace_opportunities": "I'm already looking for opportunities; I'll report when it's done.",
    "lace_comments": "I'm already reading their TikTok comments; I'll report when it's done.",
}


async def start_lace_job(run_kind: str, user_id: uuid.UUID, lace_id: uuid.UUID, params: dict) -> models.Run:
    """Start a Lace's background job. It runs alongside the conversation and,
    when it ends (either way), wakes the Lace with whatever it queued. Raises
    JobRefused while one of the same kind is running or past the daily cap."""
    async with AsyncSessionLocal() as db:
        if await _archived(db, lace_id):
            raise JobRefused("This Lace is archived. Restore it first.")
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
    """The jobs a Lace's tools start, for one Lace, on behalf of the person
    the turn answers (`actor_id`; None when the Lace acts on its own)."""

    def __init__(self, user_id: uuid.UUID, lace_id: uuid.UUID, actor_id: uuid.UUID | None):
        self._user_id, self._lace_id, self._actor_id = user_id, lace_id, actor_id

    async def start(self, kind: str, params: dict) -> str:
        params = {**params, "actor_id": str(self._actor_id) if self._actor_id else None}
        run = await start_lace_job(_TOOL_JOB_RUN_KINDS[kind], self._user_id, self._lace_id, params)
        return str(run.id)


async def cancel(user_id: uuid.UUID, run_id: uuid.UUID) -> models.Run:
    async with AsyncSessionLocal() as db:
        run = await run_service.get_visible(db, user_id, run_id)
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
    if run.lace_id is not None and run.kind in _CONVERSATION_KINDS:
        await start_next_queued(run.lace_id)
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
    # Messages that were waiting: the turn they waited for is gone.
    async with AsyncSessionLocal() as db:
        waiting = (await db.execute(select(models.Run.lace_id).where(
            models.Run.status == _QUEUED).distinct())).scalars().all()
    for lace_id in waiting:
        await start_next_queued(lace_id)


async def shutdown() -> None:
    """Cancel live segments on graceful shutdown; recover_after_restart marks
    them failed on the next boot."""
    for task in list(_tasks.values()):
        task.cancel()
    if _tasks:
        await asyncio.gather(*_tasks.values(), return_exceptions=True)
