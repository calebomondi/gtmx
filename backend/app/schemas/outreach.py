"""Request/response models for outreach."""

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from backend.app.schemas.runs import RunResponse


class OutreachMessageResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    account_id: uuid.UUID | None = None
    channel: str
    recipient_name: str | None = None
    recipient_company: str
    recipient_address: str | None = None
    subject: str | None = None
    body: str
    status: str
    error: str | None = None
    sent_at: datetime | None = None
    created_at: datetime
    updated_at: datetime


class OutreachListResponse(BaseModel):
    messages: list[OutreachMessageResponse]
    # The drafting run in progress, if any.
    drafting_run: RunResponse | None = None


class DraftRequest(BaseModel):
    account_ids: list[uuid.UUID] = Field(min_length=1, max_length=25)
    channel: Literal["email", "linkedin"] = "email"


class MessageUpdate(BaseModel):
    subject: str | None = Field(default=None, max_length=255)
    body: str | None = None
    recipient_address: str | None = Field(default=None, max_length=320)
    recipient_name: str | None = Field(default=None, max_length=255)
