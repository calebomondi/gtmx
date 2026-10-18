"""Run events: persisted to run_events, fanned out to live subscribers.

A subscriber replays everything after its cursor from the database, then
follows live frames. The live queue is registered BEFORE the replay query and
frames are de-duplicated by id, so a frame published mid-replay is neither lost
nor delivered twice.
"""

import asyncio
import uuid
from collections import defaultdict
from collections.abc import AsyncIterator, Iterator
from contextlib import contextmanager

from sqlalchemy import select

from backend.app.database import models
from backend.app.database.connect import AsyncSessionLocal
from utils import progress
from utils.log import logger

# Frames after which a run stops emitting until something resumes it.
TERMINAL_FRAME_TYPES = frozenset({"complete", "error", "cancelled"})

_subscribers: dict[uuid.UUID, set[asyncio.Queue]] = defaultdict(set)


def _frame(event: models.RunEvent) -> dict:
    # `session_id` keeps the pre-run-manager frame shape the client already reads.
    return {
        **event.payload,
        "type": event.type,
        "event_id": event.id,
        "run_id": str(event.run_id),
        "session_id": str(event.run_id),
    }


async def publish(run_id: uuid.UUID, type_: str, payload: dict | None = None) -> dict:
    """Persist a frame, then hand it to every live subscriber of the run."""
    async with AsyncSessionLocal() as db:
        event = models.RunEvent(run_id=run_id, type=type_, payload=payload or {})
        db.add(event)
        await db.commit()
        frame = _frame(event)
    for queue in list(_subscribers.get(run_id, ())):
        queue.put_nowait(frame)
    return frame


def broadcast(run_id: uuid.UUID, type_: str, payload: dict | None = None) -> None:
    """Hand a frame to live subscribers only, without storing it: for frames
    too many to persist (a reply's tokens). It has no event_id, so it never
    moves a subscriber's cursor; a client that reconnects gets the stored
    frames, including the final message, instead."""
    frame = {**(payload or {}), "type": type_, "event_id": None, "run_id": str(run_id)}
    for queue in list(_subscribers.get(run_id, ())):
        queue.put_nowait(frame)


async def subscribe(run_id: uuid.UUID, after_id: int = 0) -> AsyncIterator[dict]:
    """Every frame of the run with id > after_id: the stored backlog, then live."""
    queue: asyncio.Queue = asyncio.Queue()
    _subscribers[run_id].add(queue)
    try:
        last_id = after_id
        async with AsyncSessionLocal() as db:
            backlog = (await db.execute(
                select(models.RunEvent)
                .where(models.RunEvent.run_id == run_id, models.RunEvent.id > after_id)
                .order_by(models.RunEvent.id)
            )).scalars().all()
        for event in backlog:
            last_id = event.id
            yield _frame(event)
        while True:
            frame = await queue.get()
            if frame["event_id"] is None:  # live-only: no cursor to check or move
                yield frame
                continue
            if frame["event_id"] <= last_id:
                continue
            last_id = frame["event_id"]
            yield frame
    finally:
        _subscribers[run_id].discard(queue)
        if not _subscribers[run_id]:
            _subscribers.pop(run_id, None)


@contextmanager
def reporting_steps(run_id: uuid.UUID) -> Iterator[None]:
    """While inside, agent progress steps (`utils.progress.report`) are saved
    as the run's "step" frames, in the order reported. Steps come from worker
    threads, so each is handed to this event loop; the agent never waits for
    one to be written."""
    loop = asyncio.get_running_loop()
    # One step at a time, in the order reported: each save is its own task and
    # session, and two quick steps could otherwise commit (and get ids) out of
    # order. Tasks reach this lock in submission order, and it is FIFO.
    in_order = asyncio.Lock()

    async def save(text: str) -> None:
        async with in_order:
            await publish(run_id, "step", {"text": text})

    def publish_step(text: str) -> None:
        future = asyncio.run_coroutine_threadsafe(save(text), loop)
        future.add_done_callback(_log_failure)

    token = progress.current_reporter.set(publish_step)
    try:
        yield
    finally:
        progress.current_reporter.reset(token)


def _log_failure(future) -> None:
    if not future.cancelled() and future.exception() is not None:
        logger.warning("Could not save a progress step: %s", future.exception())

