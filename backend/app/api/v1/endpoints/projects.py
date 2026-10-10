import uuid
from datetime import datetime, UTC
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from backend.app.api.deps import AuthUser, require_matching_user
from backend.app.database import models
from backend.app.database.connect import get_db
from backend.app.naming import title_case
from backend.app.schemas.projects import (
    ProjectCreate,
    ProjectDetailResponse,
    ProjectOrder,
    ProjectResponse,
    ProjectUpdate,
)

router = APIRouter()



def _load_options():
    return (
        selectinload(models.Project.workspaces)
        .selectinload(models.Workspace.product_profile)
    )


async def _get_project_or_404(
    project_id: uuid.UUID,
    db: AsyncSession,
) -> models.Project:
    result = await db.execute(
        select(models.Project)
        .options(_load_options())
        .where(models.Project.id == project_id)
    )
    project = result.scalar_one_or_none()
    if project is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found",
        )
    return project


async def _find_project_by_name_key(
    user_id: uuid.UUID,
    name_key: str,
    db: AsyncSession,
    exclude_id: uuid.UUID | None = None,
) -> models.Project | None:
    query = select(models.Project).where(
        models.Project.user_id == user_id,
        models.Project.name_key == name_key,
    )
    if exclude_id is not None:
        query = query.where(models.Project.id != exclude_id)
    result = await db.execute(query)
    return result.scalar_one_or_none()


@router.get(
    "/user/{user_id}",
    response_model=list[ProjectResponse],
)
async def list_projects(
    user_id: uuid.UUID,
    archived: bool = False,
    db: Annotated[AsyncSession, Depends(get_db)] = None,
    _current_user: Annotated[AuthUser, Depends(require_matching_user)] = None,
):
    """Live projects by default; pass `?archived=true` for the archive page."""
    result = await db.execute(
        select(models.Project)
        .options(_load_options())
        .where(
            models.Project.user_id == user_id,
            models.Project.archived.is_(archived),
        )
        .order_by(
            models.Project.priority.desc(),
            models.Project.position.asc(),
            models.Project.date_created.desc(),
        )
    )
    return result.scalars().all()


@router.post(
    "/user/{user_id}",
    response_model=ProjectResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_project(
    user_id: uuid.UUID,
    payload: ProjectCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    _current_user: Annotated[AuthUser, Depends(require_matching_user)] = None,
):
    name = title_case(payload.name)
    if not name:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Project name cannot be empty.",
        )

    name_key = name.lower()
    if await _find_project_by_name_key(user_id, name_key, db):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A project with this name already exists.",
        )

    # Append at the end of the default ('Other') bucket, 0-based. Note the
    # explicit None check: `max() or 0` would treat a legitimate trailing
    # position of 0 as empty and hand the new project a duplicate position.
    result = await db.execute(
        select(func.max(models.Project.position)).where(
            models.Project.user_id == user_id,
            models.Project.priority.is_(False),
        )
    )
    max_position = result.scalar()

    project = models.Project(
        id=uuid.uuid4(),
        user_id=user_id,
        name=name,
        name_key=name_key,
        priority=False,
        position=0 if max_position is None else max_position + 1,
        workspaces=[],
    )
    db.add(project)
    await db.commit()
    return project


@router.put(
    "/user/{user_id}/order",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def order_projects(
    user_id: uuid.UUID,
    payload: ProjectOrder,
    db: Annotated[AsyncSession, Depends(get_db)],
    _current_user: Annotated[AuthUser, Depends(require_matching_user)] = None,
):
    """Persist the two-bucket drag order. Projects listed move to that bucket
    with a rewritten position; unlisted projects are left untouched."""
    ids = [*payload.priority, *payload.other]
    if not ids:
        return

    result = await db.execute(
        select(models.Project).where(
            models.Project.user_id == user_id,
            models.Project.id.in_(ids),
        )
    )
    projects = {p.id: p for p in result.scalars().all()}
    now = datetime.now(UTC)

    for index, project_id in enumerate(payload.priority):
        project = projects.get(project_id)
        if project is None:
            continue
        project.priority = True
        project.position = index
        project.last_activity = now

    for index, project_id in enumerate(payload.other):
        project = projects.get(project_id)
        if project is None:
            continue
        project.priority = False
        project.position = index
        project.last_activity = now

    await db.commit()


@router.get(
    "/{project_id}",
    response_model=ProjectDetailResponse,
)
async def get_project(
    project_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Project plus its member workspaces (each carries `archived`; the
    frontend filters live/archived per surface)."""
    return await _get_project_or_404(project_id, db)


@router.patch(
    "/{project_id}",
    response_model=ProjectResponse,
)
async def update_project(
    project_id: uuid.UUID,
    payload: ProjectUpdate,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Rename the project (Title Case, unique per user)."""
    project = await _get_project_or_404(project_id, db)
    if "name" in payload.model_fields_set:
        name = title_case(payload.name)
        if not name:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Project name cannot be empty.",
            )
        name_key = name.lower()
        if await _find_project_by_name_key(
            project.user_id, name_key, db, exclude_id=project.id
        ):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="A project with this name already exists.",
            )
        project.name = name
        project.name_key = name_key
        project.last_activity = datetime.now(UTC)

    await db.commit()
    return project


@router.post(
    "/{project_id}/archive",
    response_model=ProjectDetailResponse,
)
async def archive_project(
    project_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Archive the project and auto-archive every member workspace. Archiving
    preserves membership so restore can bring the whole group back."""
    project = await _get_project_or_404(project_id, db)
    now = datetime.now(UTC)
    project.archived = True
    project.archived_at = now
    project.last_activity = now
    for workspace in project.workspaces or []:
        workspace.archived = True
        workspace.archived_at = now
    await db.commit()
    return project


@router.post(
    "/{project_id}/restore",
    response_model=ProjectDetailResponse,
)
async def restore_project(
    project_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Restore the project and all of its archived workspaces."""
    project = await _get_project_or_404(project_id, db)
    now = datetime.now(UTC)
    project.archived = False
    project.archived_at = None
    project.last_activity = now
    for workspace in project.workspaces or []:
        workspace.archived = False
        workspace.archived_at = None
    await db.commit()
    return project


@router.delete(
    "/{project_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_project(
    project_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Delete a project. It must be fully empty first — archived workspaces
    still count as members (they were kept linked for restore)."""
    project = await _get_project_or_404(project_id, db)
    member_count = len(project.workspaces or [])
    if member_count > 0:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"Project has {member_count} workspace(s). "
                "Delete or unlink them before deleting the project."
            ),
        )
    await db.delete(project)
    await db.commit()