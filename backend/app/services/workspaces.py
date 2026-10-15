"""Workspaces: one offer (product or service) under research, owned by a user."""

import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from backend.app.database import models
from backend.app.naming import title_case
from backend.app.services.errors import InvalidInputError, NotFoundError


async def list_for_owner(db: AsyncSession, owner_id: uuid.UUID, *, archived: bool) -> list[models.Workspace]:
    """Live workspaces, or archived ones for the archive page."""
    result = await db.execute(
        select(models.Workspace)
        .options(selectinload(models.Workspace.product_profile))
        .where(
            models.Workspace.user_id == owner_id,
            models.Workspace.archived.is_(archived),
        )
        .order_by(
            models.Workspace.pinned.desc(),
            models.Workspace.last_activity.desc(),
        )
    )
    return list(result.scalars().all())


async def get_owned(
    db: AsyncSession,
    owner_id: uuid.UUID,
    workspace_id: uuid.UUID,
    *,
    with_features: bool = False,
) -> models.Workspace:
    """The workspace if `owner_id` owns it. Someone else's workspace raises the
    same NotFoundError as a missing one."""
    profile = selectinload(models.Workspace.product_profile)
    if with_features:
        profile = profile.selectinload(models.ProductProfile.features)
    result = await db.execute(
        select(models.Workspace)
        .options(profile)
        .where(
            models.Workspace.id == workspace_id,
            models.Workspace.user_id == owner_id,
        )
    )
    workspace = result.scalar_one_or_none()
    if workspace is None:
        raise NotFoundError("Workspace not found")
    return workspace


async def update(db: AsyncSession, workspace: models.Workspace, changes: dict[str, Any]) -> models.Workspace:
    """Apply the fields the client actually sent: rename (Title Case), pin, and
    set or clear project membership (the project must belong to the same user)."""
    if "name" in changes:
        name = title_case(changes["name"])
        if not name:
            raise InvalidInputError("Workspace name cannot be empty.")
        workspace.name = name
    if changes.get("pinned") is not None:
        workspace.pinned = changes["pinned"]
    if "project_id" in changes:
        project_id = changes["project_id"]
        if project_id is not None:
            project = await db.get(models.Project, project_id)
            if project is None or project.user_id != workspace.user_id:
                raise NotFoundError("Project not found")
        workspace.project_id = project_id
    # expire_on_commit=False: the instance (and its eagerly-loaded profile)
    # stays usable for the response without a refresh.
    await db.commit()
    return workspace


async def archive(db: AsyncSession, workspace: models.Workspace) -> models.Workspace:
    """Hide from lists, feeds and agent tracking; keep project membership so a
    restore brings it back where it was."""
    if not workspace.archived:
        workspace.archived = True
        workspace.archived_at = datetime.now(UTC)
        await db.commit()
    return workspace


async def restore(db: AsyncSession, workspace: models.Workspace) -> models.Workspace:
    if workspace.archived:
        workspace.archived = False
        workspace.archived_at = None
        await db.commit()
    return workspace


async def delete(db: AsyncSession, workspace: models.Workspace) -> None:
    """Profile, features, competitors, accounts and runs cascade."""
    await db.delete(workspace)
    await db.commit()


async def create_from_discovery(db: AsyncSession, owner_id: uuid.UUID, values: dict) -> uuid.UUID:
    """Persist the offer the discovery intake settled on. `values` is the agent
    session state (loose offer_* keys, features as plain strings)."""
    offer_name = (values.get("offer_name") or "").strip() or None
    workspace = models.Workspace(
        user_id=owner_id, name=title_case(offer_name), offer_type=values.get("offer_type"),
    )
    db.add(models.ProductProfile(
        workspace=workspace,
        product_name=offer_name,
        product_url=values.get("website_url"),
        product_description=values.get("offer_description"),
        problem_solved=values.get("problem"),
        how_it_works=values.get("how_it_works"),
        target_geo=list(values.get("target_market") or []),
        confirmed=bool(values.get("confirmed")),
        features=[models.ProductFeature(name=f) for f in values.get("features") or []],
    ))
    await db.commit()
    return workspace.id


async def save_insights(db: AsyncSession, workspace_id: uuid.UUID, insights: dict) -> None:
    """Store a finished run's results so the workspace tabs survive a refresh."""
    result = await db.execute(
        select(models.ProductProfile).where(models.ProductProfile.workspace_id == workspace_id)
    )
    profile = result.scalar_one_or_none()
    if profile is not None:
        profile.insights = insights
        await db.commit()


async def get_insights(db: AsyncSession, workspace_id: uuid.UUID) -> dict | None:
    result = await db.execute(
        select(models.ProductProfile.insights).where(models.ProductProfile.workspace_id == workspace_id)
    )
    return result.scalar_one_or_none()
