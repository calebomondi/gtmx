"""Admin views of users and workspaces. Identity comes from Supabase (there
is no local users table); activity counts come from our own tables."""

import uuid
from datetime import UTC, datetime

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app import supabase_admin
from backend.app.database import models
from backend.app.schemas.admin import AdminUserRow, AdminWorkspaceRow, Page
from backend.app.services import admin as admin_service
from backend.app.services.errors import NotFoundError


def _suspended(user) -> bool:
    banned = getattr(user, "banned_until", None)
    if isinstance(banned, str):
        banned = datetime.fromisoformat(banned.replace("Z", "+00:00"))
    return banned is not None and banned > datetime.now(UTC)


def user_row(user, counts: dict | None = None) -> AdminUserRow:
    meta = getattr(user, "user_metadata", None) or {}
    return AdminUserRow(
        id=uuid.UUID(str(user.id)),
        email=user.email,
        name=meta.get("full_name") or meta.get("name"),
        created_at=getattr(user, "created_at", None),
        last_sign_in_at=getattr(user, "last_sign_in_at", None),
        is_admin=supabase_admin.is_admin(user.app_metadata),
        suspended=_suspended(user),
        **(counts or {}),
    )


async def emails_by_id() -> dict[uuid.UUID, str | None]:
    return {uuid.UUID(str(u.id)): u.email for u in await admin_service.list_all_users()}


async def _activity(db: AsyncSession, user_ids: list[uuid.UUID]) -> dict[uuid.UUID, dict]:
    counts = {uid: {} for uid in user_ids}
    for uid, n in (await db.execute(
        select(models.Workspace.user_id, func.count()).where(models.Workspace.user_id.in_(user_ids))
        .group_by(models.Workspace.user_id)
    )).all():
        counts[uid]["workspaces"] = n
    for uid, n, last in (await db.execute(
        select(models.Run.user_id, func.count(), func.max(models.Run.created_at))
        .where(models.Run.user_id.in_(user_ids)).group_by(models.Run.user_id)
    )).all():
        counts[uid] |= {"runs": n, "last_run_at": last}
    return counts


async def list_users(db: AsyncSession, page: int, per_page: int, q: str | None) -> Page[AdminUserRow]:
    users = await admin_service.list_all_users()
    if q:
        needle = q.strip().lower()
        users = [u for u in users if needle in (u.email or "").lower()
                 or needle in str((u.user_metadata or {}).get("full_name") or "").lower()]
    users.sort(key=lambda u: str(getattr(u, "created_at", "") or ""), reverse=True)
    window = users[(page - 1) * per_page: page * per_page]
    activity = await _activity(db, [uuid.UUID(str(u.id)) for u in window])
    return Page(
        items=[user_row(u, activity[uuid.UUID(str(u.id))]) for u in window],
        total=len(users), page=page, per_page=per_page,
    )


async def get_supabase_user(user_id: uuid.UUID):
    client = await supabase_admin.get_client()
    try:
        response = await client.auth.admin.get_user_by_id(str(user_id))
    except Exception as exc:  # the client raises its own AuthApiError for unknown ids
        raise NotFoundError("User not found.") from exc
    if response is None or response.user is None:
        raise NotFoundError("User not found.")
    return response.user


async def user_activity(db: AsyncSession, user_id: uuid.UUID) -> dict:
    return (await _activity(db, [user_id]))[user_id]


async def list_workspaces(
    db: AsyncSession, page: int, per_page: int, q: str | None = None, user_id: uuid.UUID | None = None,
) -> Page[AdminWorkspaceRow]:
    w = models.Workspace
    filters = []
    if q:
        filters.append(or_(w.name.ilike(f"%{q.strip()}%")))
    if user_id:
        filters.append(w.user_id == user_id)
    total = await db.scalar(select(func.count()).select_from(w).where(*filters))
    competitors = select(func.count()).where(models.Competitor.workspace_id == w.id).scalar_subquery()
    accounts = select(func.count()).where(models.Account.workspace_id == w.id).scalar_subquery()
    runs = select(func.count()).where(models.Run.workspace_id == w.id).scalar_subquery()
    rows = (await db.execute(
        select(w, competitors, accounts, runs).where(*filters)
        .order_by(w.last_activity.desc()).offset((page - 1) * per_page).limit(per_page)
    )).all()
    emails = await emails_by_id() if rows else {}
    return Page(
        items=[
            AdminWorkspaceRow(
                id=ws.id, name=ws.name, user_id=ws.user_id, user_email=emails.get(ws.user_id),
                archived=ws.archived, date_created=ws.date_created, last_activity=ws.last_activity,
                competitors=nc, accounts=na, runs=nr,
            )
            for ws, nc, na, nr in rows
        ],
        total=total or 0, page=page, per_page=per_page,
    )
