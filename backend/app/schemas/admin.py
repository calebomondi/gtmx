"""Response models for /api/v1/admin/*."""

from datetime import date

from pydantic import BaseModel, Field


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
