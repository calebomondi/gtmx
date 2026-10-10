"""Admin role management and the audit trail. Roles live in Supabase
app_metadata (writable only with the service key); every change is recorded
in admin_audit_log."""

import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app import supabase_admin
from backend.app.database import models
from backend.app.services.errors import ConflictError
from utils.log import logger

_PAGE_SIZE = 200


async def record_audit(
    db: AsyncSession,
    *,
    actor_id: uuid.UUID | None,
    actor_email: str | None,
    action: str,
    target_type: str,
    target_id: str | None,
    before: dict | None = None,
    after: dict | None = None,
) -> None:
    """Append one audit row. Callers commit as part of their own transaction."""
    db.add(models.AdminAuditLog(
        actor_id=actor_id,
        actor_email=actor_email,
        action=action,
        target_type=target_type,
        target_id=target_id,
        before=before,
        after=after,
    ))


async def list_all_users() -> list:
    """Every Supabase user. Fine at launch scale (hundreds); page through
    `list_users` directly once that stops being true."""
    client = await supabase_admin.get_client()
    users, page = [], 1
    while True:
        batch = await client.auth.admin.list_users(page=page, per_page=_PAGE_SIZE)
        users.extend(batch)
        if len(batch) < _PAGE_SIZE:
            return users
        page += 1


async def bootstrap_admins(db: AsyncSession, emails: list[str]) -> list[str]:
    """Grant the admin role to each listed email that has an account and lacks
    it. Idempotent; an email with no account yet is skipped and picked up on a
    later startup once that person signs up. Returns the emails granted."""
    wanted = {e.strip().lower() for e in emails if e.strip()}
    if not wanted:
        return []
    client = await supabase_admin.get_client()
    granted = []
    for user in await list_all_users():
        email = (user.email or "").lower()
        if email not in wanted or supabase_admin.is_admin(user.app_metadata):
            continue
        before = dict(user.app_metadata or {})
        after = {**before, "role": supabase_admin.ADMIN_ROLE}
        await client.auth.admin.update_user_by_id(str(user.id), {"app_metadata": after})
        await record_audit(
            db, actor_id=None, actor_email="system:bootstrap", action="admin.grant",
            target_type="user", target_id=str(user.id), before=before, after=after,
        )
        granted.append(email)
    await db.commit()
    for email in sorted(wanted - {(u or "").lower() for u in granted}):
        logger.info("Admin bootstrap: %s already admin or has no account yet", email)
    return granted


async def _set_role(user_id: uuid.UUID, admin: bool) -> tuple[dict, dict]:
    client = await supabase_admin.get_client()
    user = (await client.auth.admin.get_user_by_id(str(user_id))).user
    before = dict(user.app_metadata or {})
    after = {k: v for k, v in before.items() if k != "role"}
    if admin:
        after["role"] = supabase_admin.ADMIN_ROLE
    await client.auth.admin.update_user_by_id(str(user_id), {"app_metadata": after})
    return before, after


async def grant_admin(db: AsyncSession, actor, user_id: uuid.UUID) -> None:
    before, after = await _set_role(user_id, admin=True)
    await record_audit(db, actor_id=actor.id, actor_email=actor.email, action="admin.grant",
                       target_type="user", target_id=str(user_id), before=before, after=after)
    await db.commit()


async def revoke_admin(db: AsyncSession, actor, user_id: uuid.UUID) -> None:
    """Never your own role, and never the last admin: either would lock the
    dashboard out with no way back short of the database."""
    if actor.id == user_id:
        raise ConflictError("You can't revoke your own admin role. Ask another admin.")
    admins = [u for u in await list_all_users() if supabase_admin.is_admin(u.app_metadata)]
    if not any(str(u.id) == str(user_id) for u in admins):
        raise ConflictError("This user is not an admin.")
    if len(admins) <= 1:
        raise ConflictError("The last admin can't be removed.")
    before, after = await _set_role(user_id, admin=False)
    await record_audit(db, actor_id=actor.id, actor_email=actor.email, action="admin.revoke",
                       target_type="user", target_id=str(user_id), before=before, after=after)
    await db.commit()


async def list_audit(db: AsyncSession, page: int, per_page: int, action: str | None = None,
                     target_id: str | None = None) -> tuple[list[models.AdminAuditLog], int]:
    log = models.AdminAuditLog
    filters = [col == value for col, value in ((log.action, action), (log.target_id, target_id)) if value]
    total = await db.scalar(select(func.count()).select_from(log).where(*filters))
    rows = (await db.execute(
        select(log).where(*filters).order_by(log.created_at.desc()).offset((page - 1) * per_page).limit(per_page)
    )).scalars().all()
    return list(rows), total or 0
