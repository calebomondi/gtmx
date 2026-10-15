"""The signed-in user's agent runs: find the ones still going (to reattach after
a reload), inspect one, answer its question, or cancel it."""

import uuid

from fastapi import APIRouter, Query

from backend.app.api.deps import CurrentUser, DbSession
from backend.app.runs import manager
from backend.app.schemas.runs import RunAnswer, RunResponse, RunStepResponse
from backend.app.services import runs as run_service

router = APIRouter()


@router.get("/active", response_model=list[RunResponse])
async def list_active_runs(user: CurrentUser, db: DbSession):
    return await run_service.list_active(db, user.id)


@router.get("/{run_id}", response_model=RunResponse)
async def get_run(run_id: uuid.UUID, user: CurrentUser, db: DbSession):
    return await run_service.get_owned(db, user.id, run_id)


# A run reports well under this many steps; the client pages with `after`.
MAX_STEPS_PER_PAGE = 200


@router.get("/{run_id}/steps", response_model=list[RunStepResponse])
async def list_run_steps(
    run_id: uuid.UUID, user: CurrentUser, db: DbSession,
    after: int = Query(default=0, ge=0), limit: int = Query(default=50, ge=1, le=MAX_STEPS_PER_PAGE),
):
    steps = await run_service.list_steps(db, user.id, run_id, after, limit)
    return [RunStepResponse(id=s.id, text=str(s.payload.get("text") or ""), created_at=s.created_at) for s in steps]


@router.post("/{run_id}/answer", status_code=202)
async def answer_run(run_id: uuid.UUID, payload: RunAnswer, user: CurrentUser):
    await manager.answer(user.id, run_id, payload.answer)


@router.post("/{run_id}/cancel", response_model=RunResponse)
async def cancel_run(run_id: uuid.UUID, user: CurrentUser):
    return await manager.cancel(user.id, run_id)
