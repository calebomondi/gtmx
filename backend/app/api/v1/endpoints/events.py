"""The customer app's event log: batches of what the user did."""

from fastapi import APIRouter

from backend.app.api.deps import CurrentUser, DbSession
from backend.app.schemas.events import EventBatch, EventsRecorded
from backend.app.services import events as events_service

router = APIRouter()


@router.post("", response_model=EventsRecorded)
async def record_events(payload: EventBatch, user: CurrentUser, db: DbSession):
    return EventsRecorded(recorded=await events_service.record(db, user.id, payload.events))
