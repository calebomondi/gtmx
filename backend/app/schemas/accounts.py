"""Request/response models for the account-discovery endpoints."""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class AccountResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    workspace_id: uuid.UUID
    run_id: uuid.UUID | None = None
    name: str
    account_type: str = "company"
    website: str | None = None
    domain: str | None = None
    platform: str | None = None
    venue: str | None = None
    event_date: str | None = None
    member_size: str | None = None
    industry: str | None = None
    size: str | None = None
    geo: str | None = None
    tech_stack: list[str] = []
    recent_news: list[str] = []
    key_contacts: list[dict] = []
    pain_signals: list[str] = []
    hiring_signals: list[str] = []
    sources: list[dict] = []
    source_queries: list[str] = []
    score: float | None = None
    score_breakdown: str | None = None
    why_selected: list[str] = []
    why_reach_out: list[str] = []
    trigger_event: dict | None = None
    selected: bool = False
    created_at: datetime


class AccountListResponse(BaseModel):
    accounts: list[AccountResponse]
    total: int


class AccountUpdateRequest(BaseModel):
    selected: bool | None = None


class AccountRunResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    workspace_id: uuid.UUID
    status: str = Field(description="pending | running | completed | failed")
    error: str | None = None
    candidates_seen: int = 0
    found: int = 0
    started_at: datetime | None = None
    finished_at: datetime | None = None
    created_at: datetime


class AccountRunStartResponse(BaseModel):
    run: AccountRunResponse
    already_tracked: int = 0
