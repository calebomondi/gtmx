"""The closed pilot's guest list as admins keep it: let emails in (typed in,
or approved from the waitlist) and take them off. Every change writes an
admin_audit_log row."""

import uuid

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.database import models
from backend.app.schemas.admin import Page
from backend.app.schemas.pilot import PilotAccessRow, PilotSource
from backend.app.services.admin import record_audit
from backend.app.services.admin_directory import emails_by_id
from backend.app.services.errors import NotFoundError
from backend.app.services.pilot import normalized

_P = models.PilotAccess


async def list_access(db: AsyncSession, page: int, per_page: int, q: str | None = None) -> Page[PilotAccessRow]:
    """Newest first, each with whether that person has signed up yet."""
    filters = [_P.email.ilike(f"%{q.strip().lower()}%")] if q and q.strip() else []
    total = await db.scalar(select(func.count()).select_from(_P).where(*filters))
    rows = (await db.scalars(select(_P).where(*filters).order_by(_P.created_at.desc())
                             .offset((page - 1) * per_page).limit(per_page))).all()
    accounts = {normalized(e) for e in (await emails_by_id()).values() if e} if rows else set()
    return Page(items=[PilotAccessRow.model_validate(r).model_copy(update={"signed_up": r.email in accounts})
                       for r in rows], total=total or 0, page=page, per_page=per_page)


async def let_in(db: AsyncSession, actor, emails: list[str], source: PilotSource) -> int:
    """Let these emails in; ones already in are left as they are. The caller commits."""
    wanted = sorted({normalized(e) for e in emails})
    added = (await db.scalars(insert(_P).values([
        {"id": uuid.uuid4(), "email": e, "source": source, "granted_by": actor.id, "granted_by_email": actor.email}
        for e in wanted]).on_conflict_do_nothing(index_elements=["email"]).returning(_P.email))).all()
    if added:
        await record_audit(db, actor_id=actor.id, actor_email=actor.email, action="pilot.let_in",
                           target_type="pilot_access", target_id=None, before=None,
                           after={"emails": list(added), "source": source})
    return len(added)


async def add(db: AsyncSession, actor, emails: list[str]) -> int:
    added = await let_in(db, actor, emails, "admin")
    await db.commit()
    return added


async def remove(db: AsyncSession, actor, access_id: uuid.UUID) -> None:
    """Take an email off the list. Someone already on a Lace keeps using it."""
    row = await db.get(_P, access_id)
    if row is None:
        raise NotFoundError("Not on the pilot list.")
    await db.delete(row)
    await record_audit(db, actor_id=actor.id, actor_email=actor.email, action="pilot.remove",
                       target_type="pilot_access", target_id=str(access_id),
                       before={"email": row.email, "source": row.source}, after=None)
    await db.commit()


async def approve_signup(db: AsyncSession, actor, signup_id: uuid.UUID) -> models.WaitlistSignup:
    """A waitlist signup is let in and marked invited."""
    signup = await db.get(models.WaitlistSignup, signup_id)
    if signup is None:
        raise NotFoundError("Signup not found")
    await let_in(db, actor, [signup.email], "waitlist")
    if signup.status in ("new", "contacted"):
        before, signup.status = signup.status, "invited"
        await record_audit(db, actor_id=actor.id, actor_email=actor.email, action="waitlist.status",
                           target_type="waitlist_signup", target_id=str(signup_id),
                           before={"status": before, "email": signup.email},
                           after={"status": "invited", "email": signup.email})
    await db.commit()
    await db.refresh(signup)
    return signup
