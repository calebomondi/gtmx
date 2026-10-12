"""The signed-in user's connected channels (via Composio)."""

from dataclasses import asdict

from fastapi import APIRouter, Header, status

from backend.app.api.deps import CurrentUser, DbSession
from backend.app.schemas.connections import (
    ChannelResponse,
    ConnectionResponse,
    ConnectionsResponse,
    ConnectStartResponse,
)
from backend.app.services import connections as connection_service

router = APIRouter()


@router.get("", response_model=ConnectionsResponse)
async def list_connections(user: CurrentUser, db: DbSession):
    infos = await connection_service.list_for_user(db, user.id)
    return ConnectionsResponse(
        channels=[
            ChannelResponse(platform=p, available=connection_service.available(p))
            for p in connection_service.TOOLKITS
        ],
        connections=[ConnectionResponse(**asdict(i)) for i in infos],
    )


@router.post("/{platform}", response_model=ConnectStartResponse)
async def start_connection(platform: str, user: CurrentUser, origin: str | None = Header(default=None)):
    """A Connect Link to send the user to; they return to /accounts on the
    origin they started from."""
    return ConnectStartResponse(redirect_url=await connection_service.start(user.id, platform, origin))


@router.delete("/{connection_id}", status_code=status.HTTP_204_NO_CONTENT)
async def disconnect(connection_id: str, user: CurrentUser, db: DbSession):
    await connection_service.disconnect(db, user.id, connection_id)
