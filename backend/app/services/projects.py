"""Projects: a user-owned grouping of workspaces, ordered in 'Priority' and
'Other' buckets. Archiving a project archives its workspaces with it."""

import uuid
from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from backend.app.database import models
from backend.app.naming import title_case
from backend.app.services.errors import ConflictError, InvalidInputError, NotFoundError


def _with_workspaces():
    return selectinload(models.Project.workspaces).selectinload(models.Workspace.product_profile)


def _normalized_name(raw: str | None) -> tuple[str, str]:
    """(Title Case display name, lowercase uniqueness key)."""
    name = title_case(raw)
    if not name:
        raise InvalidInputError("Project name cannot be empty.")
    return name, name.lower()


async def _ensure_name_free(
    db: AsyncSession, owner_id: uuid.UUID, name_key: str, *, exclude_id: uuid.UUID | None = None
) -> None:
    query = select(models.Project.id).where(
        models.Project.user_id == owner_id,
        models.Project.name_key == name_key,
    )
    if exclude_id is not None:
        query = query.where(models.Project.id != exclude_id)
    if (await db.execute(query)).first() is not None:
        raise ConflictError("A project with this name already exists.")


async def list_for_owner(db: AsyncSession, owner_id: uuid.UUID, *, archived: bool) -> list[models.Project]:
    result = await db.execute(
        select(models.Project)
        .options(_with_workspaces())
        .where(
            models.Project.user_id == owner_id,
            models.Project.archived.is_(archived),
        )
        .order_by(
            models.Project.priority.desc(),
            models.Project.position.asc(),
            models.Project.date_created.desc(),
        )
    )
    return list(result.scalars().all())


async def get_owned(db: AsyncSession, owner_id: uuid.UUID, project_id: uuid.UUID) -> models.Project:
    """The project with its member workspaces, if `owner_id` owns it."""
    result = await db.execute(
        select(models.Project)
        .options(_with_workspaces())
        .where(
            models.Project.id == project_id,
            models.Project.user_id == owner_id,
        )
    )
    project = result.scalar_one_or_none()
    if project is None:
        raise NotFoundError("Project not found")
    return project


async def create(db: AsyncSession, owner_id: uuid.UUID, raw_name: str) -> models.Project:
    """New project at the end of the 'Other' bucket."""
    name, name_key = _normalized_name(raw_name)
    await _ensure_name_free(db, owner_id, name_key)

    # Explicit None check: `max() or 0` would treat a legitimate trailing
    # position of 0 as empty and hand out a duplicate position.
    max_position = await db.scalar(
        select(func.max(models.Project.position)).where(
            models.Project.user_id == owner_id,
            models.Project.priority.is_(False),
        )
    )
    project = models.Project(
        id=uuid.uuid4(),
        user_id=owner_id,
        name=name,
        name_key=name_key,
        priority=False,
        position=0 if max_position is None else max_position + 1,
        workspaces=[],
    )
    db.add(project)
    await db.commit()
    return project


async def reorder(
    db: AsyncSession, owner_id: uuid.UUID, priority: list[uuid.UUID], other: list[uuid.UUID]
) -> None:
    """Persist the two-bucket drag order. Listed projects move to that bucket
    with a rewritten position; unlisted (or other users') ids are ignored."""
    ids = [*priority, *other]
    if not ids:
        return
    result = await db.execute(
        select(models.Project).where(
            models.Project.user_id == owner_id,
            models.Project.id.in_(ids),
        )
    )
    projects = {p.id: p for p in result.scalars().all()}
    now = datetime.now(UTC)
    for is_priority, bucket in ((True, priority), (False, other)):
        for index, project_id in enumerate(bucket):
            project = projects.get(project_id)
            if project is None:
                continue
            project.priority = is_priority
            project.position = index
            project.last_activity = now
    await db.commit()


async def rename(db: AsyncSession, project: models.Project, raw_name: str) -> models.Project:
    name, name_key = _normalized_name(raw_name)
    await _ensure_name_free(db, project.user_id, name_key, exclude_id=project.id)
    project.name = name
    project.name_key = name_key
    project.last_activity = datetime.now(UTC)
    await db.commit()
    return project


async def set_archived(db: AsyncSession, project: models.Project, archived: bool) -> models.Project:
    """Archive or restore the project together with every member workspace;
    membership is kept so a restore brings the whole group back."""
    now = datetime.now(UTC)
    project.archived = archived
    project.archived_at = now if archived else None
    project.last_activity = now
    for workspace in project.workspaces or []:
        workspace.archived = archived
        workspace.archived_at = now if archived else None
    await db.commit()
    return project


async def delete(db: AsyncSession, project: models.Project) -> None:
    """Only an empty project can be deleted -- archived workspaces still count,
    since they stay linked for restore."""
    member_count = len(project.workspaces or [])
    if member_count:
        raise ConflictError(
            f"Project has {member_count} workspace(s). "
            "Delete or unlink them before deleting the project."
        )
    await db.delete(project)
    await db.commit()
