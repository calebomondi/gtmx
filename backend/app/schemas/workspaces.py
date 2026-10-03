import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class WorkspaceUpdate(BaseModel):
	"""Partial update: only fields present in the payload are applied."""
	name: str | None = Field(default=None, min_length=1, max_length=100)
	pinned: bool | None = None
	project_id: uuid.UUID | None = None


class WorkspaceResponse(BaseModel):
	model_config = ConfigDict(from_attributes=True)

	id: uuid.UUID
	user_id: uuid.UUID
	name: str | None = None
	pinned: bool = False
	product_name: str | None = None
	project_id: uuid.UUID | None = None
	archived: bool = False
	archived_at: datetime | None = None
	date_created: datetime
	last_activity: datetime

class WorkspaceResponseFull(BaseModel):
	model_config = ConfigDict(from_attributes=True)

	id: uuid.UUID
	user_id: uuid.UUID
	name: str | None = None
	pinned: bool = False
	product_name: str | None = None
	project_id: uuid.UUID | None = None
	archived: bool = False
	archived_at: datetime | None = None
	date_created: datetime
	last_activity: datetime
	product_profile: "ProductProfileResponse | None" = None

class ProductFeatureResponse(BaseModel):
	model_config = ConfigDict(from_attributes=True)

	id: uuid.UUID
	name: str
	description: str | None
	differentiator: str | None

class ProductProfileResponse(BaseModel):
	model_config = ConfigDict(from_attributes=True)

	id: uuid.UUID
	workspace_id: uuid.UUID
	product_name: str | None
	product_url: str | None
	product_description: str | None
	intent: str | None
	problem_solved: str | None
	how_it_works: str | None
	target_geo: list[str]
	confirmed: bool
	features: list[ProductFeatureResponse]


class WorkspaceInsights(BaseModel):
	"""Final agent-run results persisted when discovery completes. Nested dict
	fields mirror the frontend DTOs (MarketDataDto, CompetitionDataDto, ...)."""
	offer_snapshot: dict | None = None
	offer_type: Literal["product", "service"] | None = Field(
		default=None,
		description="Asserted at intake, not classified. Persisted so the "
		"standalone competitor agent, which runs later from the workspace, "
		"hunts in the right noun",
	)
	confirmed: bool = False
	domain_understanding: str | None = None
	market_fit_understanding: str | None = None
	market_data: dict | None = None
	# The offer-vs-standard SWOD. Its former `competitors` name list is gone --
	# the competition stage emits archetypes now (see ideal_competitor_profile).
	competition_data: dict | None = None
	# The competition stage's primary output: archetypes of what a perfect
	# competitor looks like, naming no real company.
	ideal_competitor_profile: dict | None = None
	icp: dict | None = None
	specialists: list | None = None
	completed_at: str | None = None


class WorkspaceInsightsResponse(BaseModel):
	insights: WorkspaceInsights | None = None
