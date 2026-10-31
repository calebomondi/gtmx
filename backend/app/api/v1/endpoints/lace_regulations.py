"""Where a Lace's startup is registered and operates, and the laws,
regulations, bills and filing obligations its searches found there."""

import uuid

from fastapi import APIRouter, Query

from agents.schemas.regulations import RegulationStatus
from backend.app.api.deps import CurrentUser, DbSession, MemberLace
from backend.app.schemas.lace_regulations import (
    JurisdictionResponse, JurisdictionUpdate, RegulationResponse, RegulationUpdateRequest,
)
from backend.app.services import lace_regulations

router = APIRouter()

# Regulations listed at once.
MAX_REGULATIONS_PER_PAGE = 100


@router.get("/{lace_id}/jurisdiction", response_model=JurisdictionResponse)
async def get_jurisdiction(lace: MemberLace):
    return lace


@router.put("/{lace_id}/jurisdiction", response_model=JurisdictionResponse)
async def set_jurisdiction(lace: MemberLace, payload: JurisdictionUpdate, db: DbSession):
    """Confirm where the startup is registered and operates; its searches cover only these places."""
    await lace_regulations.set_jurisdiction(db, lace.id, payload.registered_in, payload.operates_in)
    await db.commit()
    return lace


@router.get("/{lace_id}/regulations", response_model=list[RegulationResponse])
async def list_regulations(lace: MemberLace, db: DbSession,
                           shown: RegulationStatus = Query(default="tracked", alias="status"),
                           limit: int = Query(default=50, ge=1, le=MAX_REGULATIONS_PER_PAGE)):
    """The team's: tracked ones by the soonest next date, the rest newest first."""
    return await lace_regulations.list_for_lace(db, lace.id, shown, limit)


@router.patch("/{lace_id}/regulations/{regulation_id}", response_model=RegulationResponse)
async def update_regulation(lace: MemberLace, regulation_id: uuid.UUID, payload: RegulationUpdateRequest,
                            user: CurrentUser, db: DbSession):
    return await lace_regulations.set_one_status(db, lace.id, regulation_id, payload.status, user.id)
