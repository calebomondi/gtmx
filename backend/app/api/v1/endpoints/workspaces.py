import uuid
from datetime import datetime, UTC
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from backend.app.database import models
from backend.app.database.connect import get_db
from backend.app.naming import title_case
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
	archived: bool = False,
	db: Annotated[AsyncSession, Depends(get_db)] = None,
):
	"""Live workspaces by default; pass `?archived=true` for the archive page."""
	user = await db.get(models.User, user_id)
	if user is None:
		raise HTTPException(
			status_code=status.HTTP_404_NOT_FOUND,
			detail="User not found",
		)

	result = await db.execute(
		select(models.Workspace)
		.options(selectinload(models.Workspace.product_profile))
		.where(
			models.Workspace.user_id == user_id,
			models.Workspace.archived.is_(archived),
		)
		.order_by(
			models.Workspace.archived.asc(),
			models.Workspace.pinned.desc(),
			models.Workspace.last_activity.desc(),
		)
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
	"""Rename the workspace (its user-owned label), toggle its pin, and/or set
	or clear its project membership."""
	workspace = await _get_workspace_or_404(workspace_id, db)

	if "name" in update.model_fields_set:
		name = title_case(update.name)
		if not name:
			raise HTTPException(
				status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
				detail="Workspace name cannot be empty.",
			)
		workspace.name = name
	if "pinned" in update.model_fields_set and update.pinned is not None:
		workspace.pinned = update.pinned
	if "project_id" in update.model_fields_set:
		if update.project_id is not None:
			project = await db.get(models.Project, update.project_id)
			if project is None or project.user_id != workspace.user_id:
				raise HTTPException(
					status_code=status.HTTP_404_NOT_FOUND,
					detail="Project not found",
				)
		workspace.project_id = update.project_id

	# expire_on_commit=False: the instance (and its eagerly-loaded profile)
	# stays usable for the response without a refresh.
	await db.commit()
	return workspace


@router.post(
	"/{workspace_id}/archive",
	response_model=WorkspaceResponse,
)
async def archive_workspace(
	workspace_id: uuid.UUID,
	db: Annotated[AsyncSession, Depends(get_db)],
):
	"""Archive a workspace: excluded from feeds and agent tracking, hidden from
	the main lists, kept linked to its project for restore."""
	workspace = await _get_workspace_or_404(workspace_id, db)
	if not workspace.archived:
		workspace.archived = True
		workspace.archived_at = datetime.now(UTC)
		await db.commit()
	return workspace


@router.post(
	"/{workspace_id}/restore",
	response_model=WorkspaceResponse,
)
async def restore_workspace(
	workspace_id: uuid.UUID,
	db: Annotated[AsyncSession, Depends(get_db)],
):
	"""Bring an archived workspace back to live (it returns to its previous
	project, if it had one)."""
	workspace = await _get_workspace_or_404(workspace_id, db)
	if workspace.archived:
		workspace.archived = False
		workspace.archived_at = None
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
