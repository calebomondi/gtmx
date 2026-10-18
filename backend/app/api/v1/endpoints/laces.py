"""The signed-in user's Laces: create one (which starts it reading the site),
list them, read what one knows, read its conversation, and send it a message.
Work happens in runs; follow them at /runs/{run_id}/events."""

from fastapi import APIRouter, Query, status

from backend.app.api.deps import CurrentUser, DbSession, OwnedLace
from backend.app.runs import lace as lace_runs
from backend.app.runs import manager
from backend.app.schemas.laces import (
    FactResponse,
    LaceCreateRequest,
    LaceCreateResponse,
    LaceMessage,
    LaceMessageRequest,
    LaceResponse,
    LaceTurnResponse,
)
from backend.app.services import laces as lace_service
from agents.schemas.lace import FactTopic

router = APIRouter()

MAX_LACES_PER_PAGE = 50
MAX_FACTS_PER_PAGE = 200
MAX_MESSAGES_PER_PAGE = 200


@router.post("", response_model=LaceCreateResponse, status_code=status.HTTP_201_CREATED)
async def create_lace(payload: LaceCreateRequest, user: CurrentUser, db: DbSession):
    lace = await lace_service.create(db, user.id, payload.name, payload.website)
    run = await manager.start_lace_onboarding(user.id, lace.id)
    return LaceCreateResponse(lace=LaceResponse.model_validate(lace), run_id=run.id)


@router.get("", response_model=list[LaceResponse])
async def list_laces(user: CurrentUser, db: DbSession,
                     limit: int = Query(default=20, ge=1, le=MAX_LACES_PER_PAGE)):
    return await lace_service.list_for_user(db, user.id, limit)


@router.get("/{lace_id}", response_model=LaceResponse)
async def get_lace(lace: OwnedLace):
    return lace


@router.get("/{lace_id}/facts", response_model=list[FactResponse])
async def list_facts(lace: OwnedLace, db: DbSession, topic: FactTopic | None = None,
                     limit: int = Query(default=100, ge=1, le=MAX_FACTS_PER_PAGE)):
    return await lace_service.list_facts(db, lace.id, topic, limit)


@router.get("/{lace_id}/messages", response_model=list[LaceMessage])
async def list_messages(lace: OwnedLace, limit: int = Query(default=100, ge=1, le=MAX_MESSAGES_PER_PAGE)):
    return await lace_runs.history(lace.id, limit)


@router.post("/{lace_id}/messages", response_model=LaceTurnResponse, status_code=status.HTTP_202_ACCEPTED)
async def send_message(lace: OwnedLace, payload: LaceMessageRequest, user: CurrentUser):
    run = await manager.start_lace_turn(user.id, lace.id, payload.text)
    return LaceTurnResponse(run_id=run.id)
