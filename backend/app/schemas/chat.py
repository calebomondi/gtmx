"""Request/response models for workspace chat."""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from backend.app.schemas.runs import RunResponse


class ChatMessageResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    role: str
    content: str
    specialist_domain: str | None = None
    suggestions: list[str] = Field(default_factory=list, description="Follow-up questions offered under an assistant answer")
    created_at: datetime

    @field_validator("suggestions", mode="before")
    @classmethod
    def _none_is_empty(cls, value):
        return value or []


class ChatThreadResponse(BaseModel):
    messages: list[ChatMessageResponse]
    # The reply in progress, or the last reply that failed (so the UI can say so).
    reply_run: RunResponse | None = None


class ChatSendRequest(BaseModel):
    message: str = Field(min_length=1)


class ChatSendResponse(BaseModel):
    message: ChatMessageResponse
    reply_run: RunResponse
