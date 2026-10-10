"""The signed-in user's feed: every workspace (home) or one workspace."""

import uuid

from fastapi import APIRouter

from backend.app.api.deps import CurrentUser, DbSession
from backend.app.schemas.signals import SignalResponse, SignalUpdate
from backend.app.services import signals as signal_service

router = APIRouter()


@router.get("", response_model=list[SignalResponse])
async def list_signals(user: CurrentUser, db: DbSession, workspace_id: uuid.UUID | None = None):
    """Newest first, dismissed excluded. Another user's workspace id simply
    matches nothing."""
    signals = await signal_service.list_for_owner(db, user.id, workspace_id)
    return [SignalResponse.from_signal(s) for s in signals]


@router.patch("/{signal_id}", response_model=SignalResponse)
async def update_signal(signal_id: uuid.UUID, payload: SignalUpdate, user: CurrentUser, db: DbSession):
    """Mark read, pin/unpin, or dismiss."""
    signal = await signal_service.update_owned(db, user.id, signal_id, payload.model_dump(exclude_unset=True))
    return SignalResponse.from_signal(signal)
