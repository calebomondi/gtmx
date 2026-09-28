import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from backend.app.database import models
from backend.app.database.connect import get_db
from backend.app.schemas.workspaces import (
	WorkspaceInsightsResponse,
	WorkspaceResponse,
	WorkspaceResponseFull,
	WorkspaceUpdate,
)


router = APIRouter()


@router.get(
	"/user/{user_id}",
	response_model=list[WorkspaceResponse],
)
async def get_user_workspaces(
	user_id: uuid.UUID,
	db: Annotated[AsyncSession, Depends(get_db)],
):
	user = await db.get(models.User, user_id)
	if user is None:
		raise HTTPException(
			status_code=status.HTTP_404_NOT_FOUND,
			detail="User not found",
		)

	result = await db.execute(
		select(models.Workspace)
		.options(selectinload(models.Workspace.product_profile))
		.where(models.Workspace.user_id == user_id)
		.order_by(models.Workspace.date_created.desc())
	)
	return result.scalars().all()


@router.get(
	"/{workspace_id}",
	response_model=WorkspaceResponseFull,
)
async def get_workspace(
	workspace_id: uuid.UUID,
	db: Annotated[AsyncSession, Depends(get_db)],
):
	result = await db.execute(
		select(models.Workspace)
		.options(
			selectinload(models.Workspace.product_profile)
			.selectinload(models.ProductProfile.features)
		)
		.where(models.Workspace.id == workspace_id)
	)
	workspace = result.scalar_one_or_none()

	if workspace is None:
		raise HTTPException(
			status_code=status.HTTP_404_NOT_FOUND,
			detail="Workspace not found",
		)

	return workspace


@router.get(
	"/{workspace_id}/insights",
	response_model=WorkspaceInsightsResponse,
)
async def get_workspace_insights(
	workspace_id: uuid.UUID,
	db: Annotated[AsyncSession, Depends(get_db)],
):
	"""Final run insights (domain/market/competition/ICP/team + offer snapshot)
	persisted at discovery completion; `insights` is null when the run never
	finished or predates persistence."""
	workspace = await _get_workspace_or_404(workspace_id, db)
	profile = workspace.product_profile
	return WorkspaceInsightsResponse(
		insights=profile.insights if profile is not None else None
	)


async def _get_workspace_or_404(
	workspace_id: uuid.UUID,
	db: AsyncSession,
) -> models.Workspace:
	result = await db.execute(
		select(models.Workspace)
		.options(selectinload(models.Workspace.product_profile))
		.where(models.Workspace.id == workspace_id)
	)
	workspace = result.scalar_one_or_none()
	if workspace is None:
		raise HTTPException(
			status_code=status.HTTP_404_NOT_FOUND,
			detail="Workspace not found",
		)
	return workspace


@router.patch(
	"/{workspace_id}",
	response_model=WorkspaceResponse,
)
async def update_workspace(
	workspace_id: uuid.UUID,
	update: WorkspaceUpdate,
	db: Annotated[AsyncSession, Depends(get_db)],
):
	"""Rename the workspace (its user-owned label) and/or toggle its pin."""
	workspace = await _get_workspace_or_404(workspace_id, db)

	if "name" in update.model_fields_set:
		name = (update.name or "").strip()
		if not name:
			raise HTTPException(
				status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
				detail="Workspace name cannot be empty.",
			)
		workspace.name = name
	if "pinned" in update.model_fields_set and update.pinned is not None:
		workspace.pinned = update.pinned

	# expire_on_commit=False: the instance (and its eagerly-loaded profile)
	# stays usable for the response without a refresh.
	await db.commit()
	return workspace


@router.delete(
	"/{workspace_id}",
	status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_workspace(
	workspace_id: uuid.UUID,
	db: Annotated[AsyncSession, Depends(get_db)],
):
	"""Delete the workspace; product profile + features cascade at the ORM
	(and DB) level."""
	workspace = await _get_workspace_or_404(workspace_id, db)
	await db.delete(workspace)
	await db.commit()
