"""Customer-app heartbeats: how long people actively use the app."""

from fastapi import APIRouter

from backend.app.api.deps import CurrentUser, DbSession
from backend.app.schemas.activity import HeartbeatRequest, HeartbeatResponse
from backend.app.services import activity as activity_service
from config import settings

router = APIRouter()


@router.post("/heartbeat", response_model=HeartbeatResponse)
async def heartbeat(payload: HeartbeatRequest, user: CurrentUser, db: DbSession):
    """Sent while the user is active. Another user's workspace id is a 404."""
    await activity_service.record_heartbeat(db, user.id, payload.workspace_id)
    return HeartbeatResponse(next_beat_s=settings.activity_heartbeat_s)
