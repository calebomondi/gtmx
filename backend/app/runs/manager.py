"""Starts, resumes and cancels runs. Each active segment is an asyncio task
owned by this process -- never by a request or a socket -- with a wall-clock
timeout. A failure is recorded on the run and published as an `error` frame;
nothing is left `running` forever.

Single-process by design for launch: tasks live in this process's memory. A
restart fails in-flight segments (recover_after_restart).
"""

import asyncio
import uuid
from dataclasses import dataclass
from collections.abc import Awaitable, Callable, Coroutine
from datetime import UTC, datetime

from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.database import models
from backend.app.database.connect import AsyncSessionLocal
from backend.app.database.lace_models import Lace, LaceCompetitor
from backend.app.runs import events
from agents.lace.buyers import knows_buyers
from agents.lace.store import JobRefused
from agents.lace.tools import BUYER_FACTS_READ
from agents.schemas.lace import JobStart, RunningJob
from agents.schemas.lace_ui import BlockAnswer
from backend.app.runs import lace as lace_runs
from backend.app.runs.lace import LaceThread
from backend.app.runs import customer_jobs, follow_up_jobs, lace_jobs, listening_jobs, regulation_jobs, social_jobs, understanding_jobs
from backend.app.runs.errors import user_facing_error
from backend.app.services import customer_learning, limits
from backend.app.services import runs as run_service
from backend.app.services import lace_events
from backend.app.services.lace_store import DbLaceStore
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


def _busy(exc: IntegrityError, thread: LaceThread) -> ConflictError:
    """The conflict a refused conversation run means: the team's chat is
    busy (its message can wait), or the member's private one is."""
    if thread.owner_id is None and "uq_runs_one_active_per_lace" in str(exc):
        return LaceBusy("Your Lace is still working on the last message.")
    if thread.owner_id is not None and "uq_runs_one_private_turn" in str(exc):
        return ConflictError("I'm still answering your last message here.")
    raise exc


async def _start_lace_run(kind: str, user_id: uuid.UUID, thread: LaceThread, params: dict | None) -> models.Run:
    async with AsyncSessionLocal() as db:
        if await _archived(db, thread.lace_id):
            raise ConflictError("This Lace is archived. Restore it first.")
        await limits.ensure_can_start(db, user_id, kind)
        run = models.Run(user_id=user_id, lace_id=thread.lace_id, owner_id=thread.owner_id, kind=kind,
                         status="running", input=params, started_at=datetime.now(UTC))
        db.add(run)
        try:
            await db.commit()
        except IntegrityError as exc:
            raise _busy(exc, thread) from None
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
            _spawn_turn(run_id, user_id, LaceThread(lace_id), message, actor_id=user_id)
            return True
        await set_run_fields(models.Run, run_id, status="failed", error=reason, finished_at=datetime.now(UTC))
        await events.publish(run_id, "error", {"message": reason})


async def _queued_message(lace_id: uuid.UUID, params: dict):
    author, name = params["author"], params.get("name_for_lace")
    if params.get("answer"):
        answer = BlockAnswer.model_validate(params["answer"])
        return lace_runs.signed(await lace_runs.answer_message(LaceThread(lace_id), answer), author, name)
    return lace_runs.signed(lace_runs.founder_message(params.get("text", ""), params.get("documents"),
                                                      params.get("draft")), author, name)


async def start_lace_onboarding(user_id: uuid.UUID, lace_id: uuid.UUID) -> models.Run:
    run = await _start_lace_run("lace_onboarding", user_id, LaceThread(lace_id), None)

    # Only the welcome: the first searches wait for the founder's first reply (first_look).
    _spawn(run.id, user_id, _then_wake(lace_runs.onboarding_segment(run.id, lace_id), user_id, LaceThread(lace_id)),
           settings.lace_onboarding_timeout_s, then=lambda: start_next_queued(lace_id))
    return run


# How many competitors and opportunities the first look finds: the strongest
# few, quickly. A search the founder asks for later finds the usual number.
FIRST_LOOK_LIMIT = 5
_FIRST_LOOK_KINDS = ("lace_competitors", "lace_icp", "lace_opportunities")


async def _founder_turns(db: AsyncSession, lace_id: uuid.UUID) -> int:
    """Finished turns in the team's chat that answered someone (a message or
    an answer to a question), not updates or briefs."""
    return await db.scalar(select(func.count()).select_from(models.Run).where(
        models.Run.lace_id == lace_id, models.Run.kind == "lace_turn", models.Run.owner_id.is_(None),
        models.Run.status == "completed",
        or_(models.Run.input["text"].is_not(None), models.Run.input["answer"].is_not(None)))) or 0


async def _kinds_ever_run(db: AsyncSession, lace_id: uuid.UUID) -> set[str]:
    return set((await db.scalars(select(models.Run.kind).distinct().where(
        models.Run.lace_id == lace_id, models.Run.kind.in_(_FIRST_LOOK_KINDS)))).all())


async def first_look(user_id: uuid.UUID, lace_id: uuid.UUID) -> list[str]:
    """After the founder's first reply to the Lace's welcome (so what they
    corrected is on file), start what makes the Lace useful: the top
    competitors, and the ideal customer profile when it knows who buys, whose
    end starts the top opportunities (_after_first_look_icp). Each reports as
    it finishes. Nothing the founder already had started runs again, and a
    job refused (a daily cap) is left for them to ask for. Returns the run
    kinds started."""
    async with AsyncSessionLocal() as db:
        lace = await db.get(Lace, lace_id)
        if lace is None or lace.status != "active" or await _founder_turns(db, lace_id) != 1:
            return []
        ran = await _kinds_ever_run(db, lace_id)
        rivals = await db.scalar(select(func.count()).select_from(LaceCompetitor)
                                 .where(LaceCompetitor.lace_id == lace_id))
        has_icp = lace.icp is not None
    wanted: list[tuple[str, dict]] = []
    if not rivals and "lace_competitors" not in ran:
        wanted.append(("lace_competitors", {"focus": None, "first_look": True, "limit": FIRST_LOOK_LIMIT}))
    if has_icp:
        if "lace_opportunities" not in ran:
            wanted.append(("lace_opportunities", {"first_look": True, "limit": FIRST_LOOK_LIMIT}))
    elif "lace_icp" not in ran:
        facts = await DbLaceStore(AsyncSessionLocal, lace_id).facts(None, BUYER_FACTS_READ)
        if knows_buyers(facts):
            wanted.append(("lace_icp", {"guidance": None, "first_look": True}))
    return await _start_all(user_id, lace_id, wanted)


async def _after_first_look_icp(user_id: uuid.UUID, lace_id: uuid.UUID) -> list[str]:
    """The first look's ideal customer profile is saved: look for the top
    opportunities for it, unless an opportunity search already ran."""
    async with AsyncSessionLocal() as db:
        lace = await db.get(Lace, lace_id)
        if lace is None or lace.icp is None or "lace_opportunities" in await _kinds_ever_run(db, lace_id):
            return []
    return await _start_all(user_id, lace_id,
                            [("lace_opportunities", {"first_look": True, "limit": FIRST_LOOK_LIMIT})])


async def _after_customers(run_id: uuid.UUID, user_id: uuid.UUID, lace_id: uuid.UUID) -> list[str]:
    """Customers were learned: rework the ideal customer profile from them."""
    async with AsyncSessionLocal() as db:
        run = await db.get(models.Run, run_id)
    if run is None or run.status != "completed" or not (run.progress or {}).get("learned"):
        return []
    return await _start_all(user_id, lace_id, [("lace_icp", {"guidance": customer_learning.ICP_GUIDANCE})])


async def _start_all(user_id: uuid.UUID, lace_id: uuid.UUID, wanted: list[tuple[str, dict]]) -> list[str]:
    started = []
    for kind, params in wanted:
        try:
            await start_lace_job(kind, user_id, lace_id, params)
            started.append(kind)
        except JobRefused as exc:
            logger.info("First look for Lace %s: %s not started: %s", lace_id, kind, exc)
    return started


async def _then_first_look(turn: Coroutine, user_id: uuid.UUID, lace_id: uuid.UUID) -> None:
    """Run a turn that answered the founder in the team's chat, then start
    the first look if it was their first reply. A first look that can't
    start never fails the turn."""
    await turn
    try:
        await first_look(user_id, lace_id)
    except Exception:  # noqa: BLE001 -- the reply is given; the founder can ask for the searches
        logger.exception("First look for Lace %s could not start", lace_id)


async def start_lace_turn(user_id: uuid.UUID, thread: LaceThread, text: str, author: dict,
                          name_for_lace: str | None, attachments: list[dict] | None = None,
                          draft: dict | None = None) -> tuple[models.Run, bool]:
    """One founder message in a conversation (the team's, or the user's
    private one) and the Lace's work on it, with any documents attached
    ([{id, filename}], already checked to be the Lace's) and the unsent draft
    it is about, if any (lace_outreach.unsent_draft). The caller has already
    checked that the user is on the Lace. `author` and `name_for_lace` sign
    the message (lace_runs.signed). While the team's chat is busy the message
    waits its turn: (run, True) for a queued one."""
    text = text.strip()
    if not text and not attachments:
        raise InvalidInputError("Write a message first.")
    params = {"text": text, **({"documents": attachments} if attachments else {}),
              **({"draft_id": draft["id"]} if draft else {})}
    try:
        run = await _start_lace_run("lace_turn", user_id, thread, params)
    except LaceBusy:
        return await _queue_turn(user_id, thread.lace_id, {**params, "draft": draft, "author": author,
                                                            "name_for_lace": name_for_lace}), True
    message = lace_runs.signed(lace_runs.founder_message(text, attachments, draft), author, name_for_lace)
    _spawn_turn(run.id, user_id, thread, message, actor_id=user_id, who=author.get("name"))
    return run, False


async def start_lace_answer(user_id: uuid.UUID, thread: LaceThread, answer: BlockAnswer, author: dict,
                            name_for_lace: str | None) -> tuple[models.Run, bool]:
    """The founder's answer to a question under the Lace's latest reply (a
    choice, checklist or form), and the Lace's work on it; queued like a
    message while the team's chat is busy, and checked again when its turn
    comes."""
    message = lace_runs.signed(await lace_runs.answer_message(thread, answer), author, name_for_lace)
    try:
        run = await _start_lace_run("lace_turn", user_id, thread, {"answer": answer.model_dump()})
    except LaceBusy:
        return await _queue_turn(user_id, thread.lace_id, {"answer": answer.model_dump(), "author": author,
                                                            "name_for_lace": name_for_lace}), True
    _spawn_turn(run.id, user_id, thread, message, actor_id=user_id, who=author.get("name"))
    return run, False


def _spawn_turn(run_id: uuid.UUID, user_id: uuid.UUID, thread: LaceThread, message,
                actor_id: uuid.UUID | None, who: str | None = None, found_by: list[uuid.UUID] | None = None,
                event_ids: list[uuid.UUID] | None = None) -> None:
    """`actor_id`: the person the turn answers, None for a turn of updates;
    `who` names them in their private chat; `found_by`, the searches whose
    updates it passes on, and `event_ids` those updates, queued again if it
    fails. Only the team's chat has messages waiting for it to be free."""
    jobs = _LaceJobs(user_id, thread.lace_id, actor_id, thread.owner_id)
    turn = lace_runs.turn_segment(run_id, thread, message, jobs=jobs, actor_id=actor_id, who=who,
                                  found_by=found_by or [])
    if actor_id is not None and thread.owner_id is None:
        turn = _then_first_look(turn, user_id, thread.lace_id)
    if event_ids:
        turn = _putting_back(turn, event_ids)
    _spawn(run_id, user_id, _then_wake(turn, user_id, thread), settings.lace_turn_timeout_s,
           then=_next_queued(thread.lace_id) if thread.owner_id is None else None)


def _next_queued(lace_id: uuid.UUID) -> Callable[[], Awaitable]:
    """What follows a conversation run: the next waiting message. If the
    run's own wake started a turn of updates, that turn's end starts it."""
    return lambda: start_next_queued(lace_id)


async def _putting_back(turn: Coroutine, event_ids: list[uuid.UUID]) -> None:
    """Run a turn of updates; if it fails (a model down, a timeout), queue the
    updates again so the next turn passes them on. They are not passed on
    straight away: whatever failed would most likely fail again."""
    try:
        await turn
    except BaseException:
        async with AsyncSessionLocal() as db, db.begin():
            await lace_events.put_back(db, event_ids)
        raise


async def _then_wake(segment: Coroutine, user_id: uuid.UUID, thread: LaceThread) -> None:
    """Run a conversation segment, then pass on any updates that queued for
    its chat while it was busy. Only after success: a failed turn leaves them
    queued for the next message."""
    await segment
    await wake_lace(user_id, thread.lace_id, thread.owner_id)


async def wake_lace(user_id: uuid.UUID, lace_id: uuid.UUID, owner_id: uuid.UUID | None = None) -> None:
    """Start a turn carrying the queued updates for one chat (the team's, or
    `owner_id`'s private one), if it has any and is not already in a
    conversation run; that run calls this again when it ends. Not counted
    against the daily turn cap: updates come from jobs the founder started,
    which are capped themselves."""
    thread = LaceThread(lace_id, owner_id)
    try:
        async with AsyncSessionLocal() as db, db.begin():
            # Its updates stay queued for when it is restored.
            if await _archived(db, lace_id):
                return
            pending = await lace_events.take_pending(db, lace_id, owner_id)
            if not pending.texts:
                return
            run = models.Run(user_id=user_id, lace_id=lace_id, owner_id=owner_id, kind="lace_turn",
                             status="running", input={"updates": pending.texts}, started_at=datetime.now(UTC))
            db.add(run)
            await db.flush()
    except IntegrityError as exc:
        _busy(exc, thread)
        return  # rolled back: the updates stay queued for the running turn to pick up
    _spawn_turn(run.id, user_id, thread, lace_runs.event_message(pending.texts), actor_id=None,
                found_by=pending.run_ids, event_ids=pending.ids)


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
    brief = lace_runs.brief_segment(run.id, lace_id, brief_id, request, jobs=_LaceJobs(user_id, lace_id, None, None))
    _spawn(run.id, user_id, _then_wake(brief, user_id, LaceThread(lace_id)), settings.lace_turn_timeout_s,
           then=_next_queued(lace_id))
    return True


# The run kind behind each job a Lace's tools can start.
_TOOL_JOB_RUN_KINDS = {"find_competitors": "lace_competitors", "check_competitors": "lace_monitor",
                       "find_accounts": "lace_accounts", "find_contacts": "lace_contacts", "define_icp": "lace_icp",
                       "draft_outreach": "lace_drafts", "find_opportunities": "lace_opportunities",
                       "read_tiktok_comments": "lace_comments", "find_regulations": "lace_regulations",
                       "refresh_understanding": "lace_refresh", "listen": "lace_listening",
                       "learn_from_customers": "lace_customers"}
_JOB_SEGMENTS = {"lace_competitors": lace_jobs.competitors_job, "lace_monitor": lace_jobs.monitor_job,
                 "lace_accounts": lace_jobs.accounts_job, "lace_contacts": lace_jobs.contacts_job,
                 "lace_icp": lace_jobs.icp_job,
                 "lace_drafts": lace_jobs.drafts_job, "lace_reply": lace_jobs.reply_job,
                 "lace_opportunities": lace_jobs.opportunities_job,
                 "lace_comments": social_jobs.tiktok_comments_job,
                 "lace_regulations": regulation_jobs.regulations_job,
                 "lace_refresh": understanding_jobs.refresh_job,
                 "lace_listening": listening_jobs.listening_job,
                 "lace_follow_ups": follow_up_jobs.follow_ups_job,
                 "lace_customers": customer_jobs.customers_job}
# Jobs of one kind run one at a time per Lace; this many more may wait their turn.
MAX_QUEUED_JOBS = 3


@dataclass(frozen=True)
class JobRequest:
    run: models.Run
    ahead: int  # jobs of its kind running or waiting before it; 0 when it started now


async def _lock_jobs(db: AsyncSession, lace_id: uuid.UUID, run_kind: str) -> None:
    """Serialise start-or-queue decisions for one Lace's jobs of one kind, for
    the transaction, so two requests can't both see it idle and both start."""
    await db.execute(select(func.pg_advisory_xact_lock(func.hashtextextended(f"{lace_id}:{run_kind}", 0))))


async def _open_jobs(db: AsyncSession, lace_id: uuid.UUID, run_kind: str) -> list[models.Run]:
    """The Lace's jobs of this kind running or waiting, oldest first."""
    return list((await db.scalars(select(models.Run).where(
        models.Run.lace_id == lace_id, models.Run.kind == run_kind,
        models.Run.status.not_in(TERMINAL_STATUSES)).order_by(models.Run.created_at))).all())


async def _refuse_archived(db: AsyncSession, lace_id: uuid.UUID) -> None:
    if await _archived(db, lace_id):
        raise JobRefused("This Lace is archived. Restore it first.")


async def _refuse_past_cap(db: AsyncSession, user_id: uuid.UUID, run_kind: str) -> None:
    try:
        await limits.ensure_can_start(db, user_id, run_kind)
    except RateLimitedError as exc:
        raise JobRefused(str(exc)) from None


def _same_request(params: dict | None, other: dict | None) -> bool:
    """The same job asked again, whoever on the team asked."""
    def request(p: dict | None) -> dict:
        return {k: v for k, v in (p or {}).items() if k != "actor_id"}
    return request(params) == request(other)


async def start_lace_job(run_kind: str, user_id: uuid.UUID, lace_id: uuid.UUID, params: dict) -> models.Run:
    """Start a Lace's background job now, or refuse while one of its kind is
    running or waiting (a scheduled check, a reading of replies: the one under
    way covers it) or past the daily cap. See request_lace_job for the rest."""
    async with AsyncSessionLocal() as db:
        await _lock_jobs(db, lace_id, run_kind)
        await _refuse_archived(db, lace_id)
        if await _open_jobs(db, lace_id, run_kind):
            raise JobRefused(f"The {_JOB_NAMES[run_kind]} is already under way.")
        await _refuse_past_cap(db, user_id, run_kind)
        run = models.Run(user_id=user_id, lace_id=lace_id, owner_id=lace_jobs.private_to(params), kind=run_kind,
                         status="running", input=params, started_at=datetime.now(UTC))
        db.add(run)
        await db.commit()
    _run_job(run)
    return run


async def request_lace_job(run_kind: str, user_id: uuid.UUID, lace_id: uuid.UUID, params: dict) -> JobRequest:
    """Start a Lace's background job, or queue it behind the one of its kind
    that is running; it starts on its own when that one ends. It runs
    alongside the conversation and, when it ends (either way), wakes the chat
    it was started from with whatever it queued; one started from a member's
    private chat (params["private_to"]) is theirs alone. Raises JobRefused
    when the same job is already running or waiting, when MAX_QUEUED_JOBS
    wait, or past the daily cap."""
    async with AsyncSessionLocal() as db:
        await _lock_jobs(db, lace_id, run_kind)
        await _refuse_archived(db, lace_id)
        open_jobs = await _open_jobs(db, lace_id, run_kind)
        name = _JOB_NAMES[run_kind]
        for job in open_jobs:
            if _same_request(job.input, params):
                state = "waiting its turn" if job.status == _QUEUED else "under way"
                raise JobRefused(f"That same {name} is already {state}; its results will come here.")
        if len(open_jobs) > MAX_QUEUED_JOBS:
            raise JobRefused(f"{len(open_jobs) - 1} more of this kind ({name}) are already waiting their turn; "
                             "ask again once one has run.")
        await _refuse_past_cap(db, user_id, run_kind)
        run = models.Run(user_id=user_id, lace_id=lace_id, owner_id=lace_jobs.private_to(params), kind=run_kind,
                         status=_QUEUED if open_jobs else "running",
                         started_at=None if open_jobs else datetime.now(UTC), input=params)
        db.add(run)
        await db.commit()
    if not open_jobs:
        _run_job(run)
    return JobRequest(run, len(open_jobs))


def _run_job(run: models.Run) -> None:
    run_id, user_id, lace_id, owner_id, kind = run.id, run.user_id, run.lace_id, run.owner_id, run.kind
    params = dict(run.input or {})
    job = _JOB_SEGMENTS[kind](run_id, lace_id, params)

    async def then() -> None:
        await start_next_job(lace_id, kind)
        if kind == "lace_icp" and params.get("first_look"):
            await _after_first_look_icp(user_id, lace_id)
        if kind == "lace_customers":
            await _after_customers(run_id, user_id, lace_id)
    _spawn(run_id, user_id, _job_then_wake(job, user_id, lace_id, owner_id), settings.background_run_timeout_s,
           then=then)


async def start_next_job(lace_id: uuid.UUID, run_kind: str) -> bool:
    """Start the Lace's oldest waiting job of this kind, if none of its kind
    is running. True when one started (its own end starts the next)."""
    async with AsyncSessionLocal() as db:
        await _lock_jobs(db, lace_id, run_kind)
        open_jobs = await _open_jobs(db, lace_id, run_kind)
        if not open_jobs or any(job.status != _QUEUED for job in open_jobs):
            return False
        run = open_jobs[0]
        run.status, run.started_at = "running", datetime.now(UTC)
        await db.commit()
    _run_job(run)
    return True


async def _job_then_wake(job: Coroutine, user_id: uuid.UUID, lace_id: uuid.UUID, owner_id: uuid.UUID | None) -> None:
    # Jobs queue an update even when they fail, so wake either way. A job run
    # is not a conversation run, so its own row never blocks the wake.
    try:
        await job
    finally:
        await wake_lace(user_id, lace_id, owner_id)


class _LaceJobs:
    """The jobs a Lace's tools start, for one Lace, on behalf of the person
    the turn answers (`actor_id`; None when the Lace acts on its own), from
    the team's chat or (`owner_id`) a member's private one."""

    def __init__(self, user_id: uuid.UUID, lace_id: uuid.UUID, actor_id: uuid.UUID | None,
                 owner_id: uuid.UUID | None):
        self._user_id, self._lace_id, self._actor_id, self._owner_id = user_id, lace_id, actor_id, owner_id

    async def start(self, kind: str, params: dict) -> JobStart:
        params = {**params, "actor_id": str(self._actor_id) if self._actor_id else None,
                  **({"private_to": str(self._owner_id)} if self._owner_id else {})}
        request = await request_lace_job(_TOOL_JOB_RUN_KINDS[kind], self._user_id, self._lace_id, params)
        return JobStart(id=str(request.run.id), ahead=request.ahead)

    async def running(self) -> list[RunningJob]:
        """This chat's background jobs working or waiting, oldest first: the team
        chat's, or the member's own in their private chat."""
        chat = models.Run.owner_id.is_(None) if self._owner_id is None else models.Run.owner_id == self._owner_id
        async with AsyncSessionLocal() as db:
            runs = (await db.scalars(select(models.Run).where(
                models.Run.lace_id == self._lace_id, chat, models.Run.kind.in_(list(_JOB_NAMES)),
                models.Run.status.not_in(TERMINAL_STATUSES)).order_by(models.Run.created_at))).all()
        now = datetime.now(UTC)
        return [RunningJob(what=_JOB_NAMES[run.kind], queued=run.status == _QUEUED,
                           minutes=int((now - (run.started_at or run.created_at)).total_seconds() // 60))
                for run in runs]


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
    if run.lace_id is not None and run.kind in _JOB_SEGMENTS:
        await start_next_job(run.lace_id, run.kind)
    return run


# How the Lace names each background job when telling the founder it stopped.
_JOB_NAMES = {"lace_competitors": "competitor search", "lace_monitor": "competitor check",
              "lace_accounts": "search for leads", "lace_contacts": "contact search",
              "lace_icp": "ideal customer profile", "lace_drafts": "drafting", "lace_reply": "reading of replies",
              "lace_opportunities": "opportunity search", "lace_comments": "reading of TikTok comments",
              "lace_regulations": "search for laws and regulations", "lace_refresh": "re-read of the site",
              "lace_listening": "listen on social accounts", "lace_follow_ups": "drafting of follow-ups",
              "lace_customers": "learning from your customers"}


async def _report_interrupted_jobs(run_ids: list[uuid.UUID]) -> None:
    """Tell each chat whose background job a restart cut short, so the founder
    hears of it instead of waiting on a job that is gone."""
    if not run_ids:
        return
    async with AsyncSessionLocal() as db, db.begin():
        jobs = (await db.scalars(select(models.Run).where(
            models.Run.id.in_(run_ids), models.Run.kind.in_(list(_JOB_NAMES)), models.Run.lace_id.is_not(None)))).all()
        for job in jobs:
            await lace_events.add(db, job.lace_id, f"The {_JOB_NAMES[job.kind]} was cut short by a server restart "
                                  "before it finished. Tell the founder and offer to run it again.", job.owner_id)
    for job in jobs:
        await wake_lace(job.user_id, job.lace_id, job.owner_id)


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
    await _report_interrupted_jobs([run_id for run_id in stranded if run_id not in _tasks])
    # Messages that were waiting: the turn they waited for is gone.
    async with AsyncSessionLocal() as db:
        waiting = (await db.execute(select(models.Run.lace_id).where(
            models.Run.status == _QUEUED).distinct())).scalars().all()
    for lace_id in waiting:
        await start_next_queued(lace_id)
    # Jobs that waited behind one the restart cut short.
    async with AsyncSessionLocal() as db:
        queued_jobs = (await db.execute(select(models.Run.lace_id, models.Run.kind).where(
            models.Run.status == _QUEUED, models.Run.kind.in_(list(_JOB_SEGMENTS))).distinct())).all()
    for lace_id, kind in queued_jobs:
        await start_next_job(lace_id, kind)


async def shutdown() -> None:
    """Cancel live segments on graceful shutdown; recover_after_restart marks
    them failed on the next boot."""
    for task in list(_tasks.values()):
        task.cancel()
    if _tasks:
        await asyncio.gather(*_tasks.values(), return_exceptions=True)
