"""The signed-in user's agent runs: find the ones still going (to reattach after
a reload), inspect one, follow its events, or cancel it."""

import json
import uuid
from collections.abc import AsyncIterator

from fastapi import APIRouter, Query
from fastapi.responses import StreamingResponse

from backend.app.api.deps import CurrentUser, DbSession
from backend.app.runs import events, manager
from backend.app.schemas.runs import RunResponse, RunStepResponse
from backend.app.services import runs as run_service

router = APIRouter()


@router.get("/active", response_model=list[RunResponse])
async def list_active_runs(user: CurrentUser, db: DbSession):
    return await run_service.list_active(db, user.id)


@router.get("/{run_id}", response_model=RunResponse)
async def get_run(run_id: uuid.UUID, user: CurrentUser, db: DbSession):
    return await run_service.get_visible(db, user.id, run_id)


# A run reports well under this many steps; the client pages with `after`.
MAX_STEPS_PER_PAGE = 200


@router.get("/{run_id}/steps", response_model=list[RunStepResponse])
async def list_run_steps(
    run_id: uuid.UUID, user: CurrentUser, db: DbSession,
    after: int = Query(default=0, ge=0), limit: int = Query(default=50, ge=1, le=MAX_STEPS_PER_PAGE),
):
    steps = await run_service.list_steps(db, user.id, run_id, after, limit)
    return [RunStepResponse(id=s.id, text=str(s.payload.get("text") or ""), created_at=s.created_at) for s in steps]


async def _ndjson(run_id: uuid.UUID, after: int) -> AsyncIterator[str]:
    async for frame in events.subscribe(run_id, after):
        yield json.dumps(frame, default=str) + "\n"
        if frame["type"] in events.TERMINAL_FRAME_TYPES:
            return


@router.get("/{run_id}/events", response_class=StreamingResponse,
            responses={200: {"content": {"application/x-ndjson": {}}}})
async def stream_run_events(run_id: uuid.UUID, user: CurrentUser, db: DbSession,
                            after: int = Query(default=0, ge=0)):
    """Every frame after the `after` cursor, one JSON object per line: the
    stored backlog, then live frames, ending after a terminal frame. Read it
    with a streaming fetch, which (unlike EventSource) sends the auth header."""
    await run_service.get_visible(db, user.id, run_id)
    return StreamingResponse(_ndjson(run_id, after), media_type="application/x-ndjson")


@router.post("/{run_id}/cancel", response_model=RunResponse)
async def cancel_run(run_id: uuid.UUID, user: CurrentUser):
    return await manager.cancel(user.id, run_id)
