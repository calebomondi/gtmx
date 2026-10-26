"""Request and response models for the app's feedback button."""

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

FEEDBACK_MAX_CHARS = 2000

FeedbackStatus = Literal["new", "read"]


class FeedbackCreate(BaseModel):
    text: str = Field(min_length=1, max_length=FEEDBACK_MAX_CHARS)
    path: str | None = Field(default=None, max_length=512, description="The page they were on")
    lace_id: uuid.UUID | None = Field(default=None, description="The Lace they had open, if any")


class FeedbackResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    created_at: datetime


class AdminFeedbackRow(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    user_id: uuid.UUID
    email: str | None
    lace_id: uuid.UUID | None
    lace_name: str | None = None
    path: str | None
    text: str
    status: FeedbackStatus
    created_at: datetime
    read_at: datetime | None


class FeedbackStatusUpdate(BaseModel):
    status: FeedbackStatus
