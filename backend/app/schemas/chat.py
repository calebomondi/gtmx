"""Request/response models for workspace chat."""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from backend.app.schemas.runs import RunResponse


class ChatMessageResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    role: str
    content: str
    created_at: datetime


class ChatThreadResponse(BaseModel):
    messages: list[ChatMessageResponse]
    # The reply in progress, or the last reply that failed (so the UI can say so).
    reply_run: RunResponse | None = None


class ChatSendRequest(BaseModel):
    message: str = Field(min_length=1)


class ChatSendResponse(BaseModel):
    message: ChatMessageResponse
    reply_run: RunResponse
