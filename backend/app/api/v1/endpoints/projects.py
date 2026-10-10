from fastapi import APIRouter, status

from backend.app.api.deps import DbSession, MatchingUser, OwnedProject
from backend.app.schemas.projects import (
    ProjectCreate,
    ProjectDetailResponse,
    ProjectOrder,
    ProjectResponse,
    ProjectUpdate,
)
from backend.app.services import projects as project_service

router = APIRouter()


@router.get("/user/{user_id}", response_model=list[ProjectResponse])
async def list_projects(user: MatchingUser, db: DbSession, archived: bool = False):
    """Live projects by default; pass `?archived=true` for the archive page."""
    return await project_service.list_for_owner(db, user.id, archived=archived)


@router.post("/user/{user_id}", response_model=ProjectResponse, status_code=status.HTTP_201_CREATED)
async def create_project(user: MatchingUser, payload: ProjectCreate, db: DbSession):
    return await project_service.create(db, user.id, payload.name)


@router.put("/user/{user_id}/order", status_code=status.HTTP_204_NO_CONTENT)
async def order_projects(user: MatchingUser, payload: ProjectOrder, db: DbSession):
    """Persist the two-bucket drag order."""
    await project_service.reorder(db, user.id, payload.priority, payload.other)


@router.get("/{project_id}", response_model=ProjectDetailResponse)
async def get_project(project: OwnedProject):
    """Project plus its member workspaces (each carries `archived`)."""
    return project


@router.patch("/{project_id}", response_model=ProjectResponse)
async def update_project(project: OwnedProject, payload: ProjectUpdate, db: DbSession):
    """Rename the project (Title Case, unique per user)."""
    if "name" in payload.model_fields_set:
        return await project_service.rename(db, project, payload.name)
    return project


@router.post("/{project_id}/archive", response_model=ProjectDetailResponse)
async def archive_project(project: OwnedProject, db: DbSession):
    """Archive the project and every member workspace."""
    return await project_service.set_archived(db, project, True)


@router.post("/{project_id}/restore", response_model=ProjectDetailResponse)
async def restore_project(project: OwnedProject, db: DbSession):
    """Restore the project and all of its archived workspaces."""
    return await project_service.set_archived(db, project, False)


@router.delete("/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_project(project: OwnedProject, db: DbSession):
    """Only an empty project can be deleted (archived members still count)."""
    await project_service.delete(db, project)
