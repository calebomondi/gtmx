"""Request/response models for the customer app's Search Anything."""

import uuid
from typing import Literal

from pydantic import BaseModel, Field

SearchKind = Literal["workspace", "project", "competitor", "account", "signal"]


class SearchHit(BaseModel):
    kind: SearchKind
    id: uuid.UUID
    title: str
    subtitle: str | None = None
    workspace_id: uuid.UUID | None = Field(default=None, description="The workspace a hit lives in (or is)")
    archived: bool = Field(default=False, description="The workspace or project is archived")
    offer_type: Literal["product", "service"] | None = None


class SearchResponse(BaseModel):
    hits: list[SearchHit] = Field(description="Grouped by kind, best matches first within each kind")
