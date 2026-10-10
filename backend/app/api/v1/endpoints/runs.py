"""The signed-in user's agent runs: find the ones still going (to reattach after
a reload), inspect one, answer its question, or cancel it."""

import uuid

from fastapi import APIRouter

from backend.app.api.deps import CurrentUser, DbSession
from backend.app.runs import manager
from backend.app.schemas.runs import RunAnswer, RunResponse
from backend.app.services import runs as run_service

router = APIRouter()


@router.get("/active", response_model=list[RunResponse])
async def list_active_runs(user: CurrentUser, db: DbSession):
    return await run_service.list_active(db, user.id)


@router.get("/{run_id}", response_model=RunResponse)
async def get_run(run_id: uuid.UUID, user: CurrentUser, db: DbSession):
    return await run_service.get_owned(db, user.id, run_id)


@router.post("/{run_id}/answer", status_code=202)
async def answer_run(run_id: uuid.UUID, payload: RunAnswer, user: CurrentUser):
    await manager.answer(user.id, run_id, payload.answer)


@router.post("/{run_id}/cancel", response_model=RunResponse)
async def cancel_run(run_id: uuid.UUID, user: CurrentUser):
    return await manager.cancel(user.id, run_id)
