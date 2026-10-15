"""Request/response models for channel connections."""

from datetime import datetime

from pydantic import BaseModel


class ChannelResponse(BaseModel):
    platform: str
    # False until the app-level OAuth setup exists for this channel.
    available: bool


class ConnectionResponse(BaseModel):
    id: str
    platform: str
    status: str  # live | pending | needs_attention
    display_name: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


class ConnectionsResponse(BaseModel):
    channels: list[ChannelResponse]
    connections: list[ConnectionResponse]


class ConnectStartResponse(BaseModel):
    redirect_url: str
