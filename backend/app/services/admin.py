"""Admin role management and the audit trail. Roles live in Supabase
app_metadata (writable only with the service key); every change is recorded
in admin_audit_log."""

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from backend.app import supabase_admin
from backend.app.database import models
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


async def _all_users(client) -> list:
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
    for user in await _all_users(client):
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
