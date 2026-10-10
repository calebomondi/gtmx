"""Request/response models for the feed."""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class SignalResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    workspace_id: uuid.UUID
    workspace_name: str | None = None
    run_id: uuid.UUID | None = None
    category: str
    title: str
    entity: str
    summary: str
    body: str | None = None
    reason: str
    source_url: str | None = None
    hot: bool
    read: bool
    pinned: bool
    created_at: datetime

    @classmethod
    def from_signal(cls, signal) -> "SignalResponse":
        response = cls.model_validate(signal)
        response.workspace_name = signal.workspace.name if signal.workspace else None
        return response


class SignalUpdate(BaseModel):
    read: bool | None = None
    pinned: bool | None = None
    dismissed: bool | None = None
