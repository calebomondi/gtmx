"""Response models for /api/v1/admin/*."""

import uuid
from datetime import date, datetime
from typing import Generic, TypeVar

from pydantic import BaseModel, ConfigDict, Field

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


class UserSpend(BaseModel):
    user_id: uuid.UUID
    email: str | None = None
    runs: int
    cost_usd: float


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
    discovery_p50_s: float | None = Field(default=None, description="Median completed discovery duration")
    discovery_p90_s: float | None = None
    spend_per_active_user_usd: float | None = Field(default=None, description="Priced spend / active users")
    cost_per_completed_discovery_usd: float | None = Field(
        default=None, description="Priced spend of completed discovery runs / their count",
    )
    top_spenders: list[UserSpend] = Field(default_factory=list, description="Priced spend, highest first")


class EngagementDay(BaseModel):
    day: date
    new_users: int = 0
    active_users: int = Field(default=0, description="Used the app or started a run")
    active_seconds: int = 0
    workspaces_created: int = 0
    products_created: int = 0
    services_created: int = 0
    projects_created: int = 0
    workspaces_interacted: int = 0
    chat_messages: int = 0
    competitor_runs: int = 0
    account_runs: int = 0
    outreach_drafted: int = 0
    outreach_sent: int = 0


class TopWorkspace(BaseModel):
    id: uuid.UUID
    name: str | None
    user_id: uuid.UUID
    user_email: str | None = None
    offer_type: str | None = None
    active_seconds: int
    visits: int


class EngagementMetrics(BaseModel):
    days: int
    total_users: int
    new_users: int
    weekly_active_users: int = Field(description="Last 7 days, whatever the window")
    monthly_active_users: int = Field(description="Last 30 days, whatever the window")
    stickiness: float | None = Field(description="Average daily actives over the last 30 days / monthly actives")
    returning_users: int = Field(description="Active on 2+ different days in the last 7 days")
    sessions: int
    active_time_users: int = Field(description="Users with any tracked time in the window")
    total_active_seconds: int
    avg_active_seconds_per_user: float | None
    avg_session_seconds: float | None
    workspaces_total: int
    workspaces_created: int
    projects_total: int
    projects_created: int
    avg_workspaces_per_user: float | None
    avg_projects_per_user: float | None
    offer_types: dict[str, int] = Field(description="All workspaces: product / service / unknown")
    top_workspaces: list[TopWorkspace]
    series: list[EngagementDay]


class FunnelStep(BaseModel):
    key: str
    label: str
    users: int


class InterviewDropOff(BaseModel):
    question: str = Field(description="The interview step (interrupt type) the run stopped at")
    runs: int


class FailureReason(BaseModel):
    message: str
    runs: int
    last_at: datetime


class FunnelMetrics(BaseModel):
    days: int
    steps: list[FunnelStep] = Field(description="All time: how many users reached each step")
    discoveries_started: int
    discoveries_completed: int
    interview_dropoffs: list[InterviewDropOff] = Field(description="Abandoned discoveries in the window")
    failure_reasons: list[FailureReason]


class PlatformUsage(BaseModel):
    platform: str
    connected_users: int
    sends: int = Field(description="Outreach sent through it in the window")
    senders: int


class ConnectionMetrics(BaseModel):
    days: int
    error: str | None = Field(default=None, description="Set when Composio couldn't be read; sends still count")
    users_with_connections: int
    avg_connections_per_user: float | None
    platforms: list[PlatformUsage]


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
    projects: int = 0
    runs: int = 0
    last_run_at: datetime | None = None
    last_seen_at: datetime | None = Field(default=None, description="Last customer-app heartbeat")
    active_seconds_30d: int = 0
    connections: int | None = Field(default=None, description="Live connected accounts; null if Composio failed")


class AdminWorkspaceRow(BaseModel):
    id: uuid.UUID
    name: str | None
    offer_type: str | None = None
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


class UserConnection(BaseModel):
    platform: str
    status: str
    display_name: str | None = None
    sends: int = Field(description="Outreach sent through this platform, all time")


class ActivityDay(BaseModel):
    day: date
    active_seconds: int


class AdminUserDetail(AdminUserRow):
    spend_usd: float
    recent_runs: list[AdminRunRow]
    workspace_list: list[AdminWorkspaceRow]
    connection_list: list[UserConnection] = Field(default_factory=list)
    connections_error: str | None = None
    activity: list[ActivityDay] = Field(default_factory=list, description="Last 30 days")
    top_workspaces: list[TopWorkspace] = Field(default_factory=list, description="Most time, last 30 days")


class AdminSignalRow(SignalResponse):
    user_id: uuid.UUID
    user_email: str | None = None


class QuotaRow(BaseModel):
    kind: str
    default_cap: int
    override: int | None = None


class QuotaUpdate(BaseModel):
    kind: str
    daily_cap: int | None = Field(ge=0, le=10_000, description="null removes the override")


class SuspendRequest(BaseModel):
    reason: str = Field(min_length=3, max_length=500)


class AuditRow(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    actor_id: uuid.UUID | None
    actor_email: str | None
    action: str
    target_type: str
    target_id: str | None
    before: dict | None
    after: dict | None
    created_at: datetime
