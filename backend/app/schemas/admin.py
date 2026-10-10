"""Response models for /api/v1/admin/*."""

import uuid
from datetime import date, datetime
from typing import Generic, TypeVar

from pydantic import BaseModel, Field

from backend.app.schemas.signals import SignalResponse

T = TypeVar("T")


class DayMetrics(BaseModel):
    day: date
    runs_started: int = 0
    runs_failed: int = 0
    active_users: int = 0
    llm_cost_usd: float = 0.0
    api_cost_usd: float = 0.0


class KindMetrics(BaseModel):
    kind: str
    runs: int
    failed: int
    avg_duration_s: float | None = None


class CostLine(BaseModel):
    """One priced line: an LLM model or an external API operation."""

    name: str
    calls: int
    failed_calls: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    cost_usd: float | None = Field(default=None, description="null when no price is configured")


class AdminMetrics(BaseModel):
    days: int
    total_users: int
    active_users: int = Field(description="Distinct users who started a run in the window")
    runs_by_status: dict[str, int]
    runs_by_kind: list[KindMetrics]
    success_rate: float | None = Field(description="completed / (completed + failed); null with no finished runs")
    avg_duration_s: float | None
    llm_cost_usd: float
    api_cost_usd: float
    llm_costs: list[CostLine]
    api_costs: list[CostLine]
    unpriced: list[str] = Field(description="Models/operations with usage but no configured price")
    series: list[DayMetrics]


class Page(BaseModel, Generic[T]):
    items: list[T]
    total: int
    page: int
    per_page: int


class AdminUserRow(BaseModel):
    id: uuid.UUID
    email: str | None
    name: str | None = None
    created_at: datetime | None = None
    last_sign_in_at: datetime | None = None
    is_admin: bool = False
    suspended: bool = False
    workspaces: int = 0
    runs: int = 0
    last_run_at: datetime | None = None


class AdminWorkspaceRow(BaseModel):
    id: uuid.UUID
    name: str | None
    user_id: uuid.UUID
    user_email: str | None = None
    archived: bool
    date_created: datetime
    last_activity: datetime
    competitors: int = 0
    accounts: int = 0
    runs: int = 0


class AdminRunRow(BaseModel):
    id: uuid.UUID
    kind: str
    status: str
    user_id: uuid.UUID
    user_email: str | None = None
    workspace_id: uuid.UUID | None = None
    workspace_name: str | None = None
    error: str | None = None
    created_at: datetime
    started_at: datetime | None = None
    finished_at: datetime | None = None
    duration_s: float | None = None
    cost_usd: float | None = Field(default=None, description="null when any of its usage is unpriced")


class AdminRunEvent(BaseModel):
    id: int
    type: str
    payload: dict
    created_at: datetime


class AdminRunDetail(AdminRunRow):
    input: dict | None = None
    progress: dict | None = None
    events: list[AdminRunEvent]
    events_truncated: bool = False
    llm_costs: list[CostLine]
    api_costs: list[CostLine]


class AdminUserDetail(AdminUserRow):
    spend_usd: float
    recent_runs: list[AdminRunRow]
    workspace_list: list[AdminWorkspaceRow]


class AdminSignalRow(SignalResponse):
    user_id: uuid.UUID
    user_email: str | None = None
