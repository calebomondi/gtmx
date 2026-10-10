
from fastapi import APIRouter, status

from backend.app.api.deps import DbSession, MatchingUser, OwnedWorkspace
from backend.app.schemas.workspaces import (
    WorkspaceInsightsResponse,
    WorkspaceResponse,
    WorkspaceResponseFull,
    WorkspaceUpdate,
)
from backend.app.services import workspaces as workspace_service

router = APIRouter()


@router.get("/user/{user_id}", response_model=list[WorkspaceResponse])
async def get_user_workspaces(user: MatchingUser, db: DbSession, archived: bool = False):
    """Live workspaces by default; pass `?archived=true` for the archive page."""
    return await workspace_service.list_for_owner(db, user.id, archived=archived)


@router.get("/{workspace_id}", response_model=WorkspaceResponseFull)
async def get_workspace(workspace: OwnedWorkspace, db: DbSession):
    return await workspace_service.get_owned(db, workspace.user_id, workspace.id, with_features=True)


@router.get("/{workspace_id}/insights", response_model=WorkspaceInsightsResponse)
async def get_workspace_insights(workspace: OwnedWorkspace):
    """Final run insights (domain/market/competition/ICP/team + offer snapshot)
    persisted at discovery completion; `insights` is null when the run never
    finished."""
    profile = workspace.product_profile
    return WorkspaceInsightsResponse(insights=profile.insights if profile is not None else None)


@router.patch("/{workspace_id}", response_model=WorkspaceResponse)
async def update_workspace(workspace: OwnedWorkspace, update: WorkspaceUpdate, db: DbSession):
    """Rename the workspace, toggle its pin, and/or set or clear its project."""
    return await workspace_service.update(db, workspace, update.model_dump(exclude_unset=True))


@router.post("/{workspace_id}/archive", response_model=WorkspaceResponse)
async def archive_workspace(workspace: OwnedWorkspace, db: DbSession):
    """Hide from lists, feeds and agent tracking; restore brings it back."""
    return await workspace_service.archive(db, workspace)


@router.post("/{workspace_id}/restore", response_model=WorkspaceResponse)
async def restore_workspace(workspace: OwnedWorkspace, db: DbSession):
    return await workspace_service.restore(db, workspace)


@router.delete("/{workspace_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_workspace(workspace: OwnedWorkspace, db: DbSession):
    await workspace_service.delete(db, workspace)
