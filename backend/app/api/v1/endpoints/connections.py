"""The signed-in user's connected channels (via Composio)."""

from dataclasses import asdict

from fastapi import APIRouter, status

from backend.app.api.deps import CurrentUser
from backend.app.schemas.connections import (
    ChannelResponse,
    ConnectionResponse,
    ConnectionsResponse,
    ConnectStartResponse,
)
from backend.app.services import connections as connection_service

router = APIRouter()


@router.get("", response_model=ConnectionsResponse)
async def list_connections(user: CurrentUser):
    infos = await connection_service.list_for_user(user.id)
    return ConnectionsResponse(
        channels=[
            ChannelResponse(platform=p, available=connection_service.available(p))
            for p in connection_service.TOOLKITS
        ],
        connections=[ConnectionResponse(**asdict(i)) for i in infos],
    )


@router.post("/{platform}", response_model=ConnectStartResponse)
async def start_connection(platform: str, user: CurrentUser):
    """A Connect Link to send the user to; they return to /accounts."""
    return ConnectStartResponse(redirect_url=await connection_service.start(user.id, platform))


@router.delete("/{connection_id}", status_code=status.HTTP_204_NO_CONTENT)
async def disconnect(connection_id: str, user: CurrentUser):
    await connection_service.disconnect(user.id, connection_id)
