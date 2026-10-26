"""The closed pilot: who may use the app while settings.pilot_invite_only_since
is set. Admins; emails an admin let in (pilot_access); anyone invited onto
or on a Lace, so a pilot startup brings its own team; and accounts made
before the pilot closed. Everyone else is kept out until an admin lets them in."""

import uuid
from datetime import datetime

from sqlalchemy import exists, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.database import models
from backend.app.database.lace_models import LaceMember
from config import settings


def invite_only() -> bool:
    return settings.pilot_invite_only_since is not None


def normalized(email: str) -> str:
    return email.strip().lower()


async def may_use(db: AsyncSession, user_id: uuid.UUID, email: str | None, created_at: datetime | None,
                  is_admin: bool) -> bool:
    since = settings.pilot_invite_only_since
    if since is None or is_admin or (created_at is not None and created_at < since):
        return True
    on_a_lace = exists().where(LaceMember.user_id == user_id, LaceMember.status.in_(("invited", "active")))
    let_in = exists().where(models.PilotAccess.email == normalized(email)) if email else None
    return bool(await db.scalar(select(on_a_lace if let_in is None else on_a_lace | let_in)))
