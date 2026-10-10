"""Run events: persisted to run_events, fanned out to live subscribers.

A subscriber replays everything after its cursor from the database, then
follows live frames. The live queue is registered BEFORE the replay query and
frames are de-duplicated by id, so a frame published mid-replay is neither lost
nor delivered twice.
"""

import asyncio
import uuid
from collections import defaultdict
from collections.abc import AsyncIterator

from sqlalchemy import select

from backend.app.database import models
from backend.app.database.connect import AsyncSessionLocal

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
            if frame["event_id"] <= last_id:
                continue
            last_id = frame["event_id"]
            yield frame
    finally:
        _subscribers[run_id].discard(queue)
        if not _subscribers[run_id]:
            _subscribers.pop(run_id, None)
