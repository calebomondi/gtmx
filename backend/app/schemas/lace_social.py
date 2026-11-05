"""The founder's social posts and what a Lace's listen kept, as the API shows them."""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict

from agents.schemas.listening import HeardKind, HeardStatus, SocialPlatform


class SocialPostResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    platform: SocialPlatform
    url: str
    text: str
    posted_at: datetime | None
    views: int | None
    likes: int | None
    comments: int | None
    shares: int | None
    read_at: datetime


class SocialItemResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    platform: SocialPlatform
    author: str | None
    text: str
    url: str | None
    said_at: datetime | None
    verdict: HeardKind
    note: str
    status: HeardStatus
    heard_at: datetime


class SocialItemUpdate(BaseModel):
    status: HeardStatus
