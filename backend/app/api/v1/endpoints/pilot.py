"""Public: whether the app is in its closed pilot, for the sign-up page."""

from fastapi import APIRouter

from backend.app.schemas.pilot import PilotStatus
from backend.app.services import pilot

router = APIRouter()


@router.get("", response_model=PilotStatus)
async def pilot_status():
    return PilotStatus(invite_only=pilot.invite_only())
