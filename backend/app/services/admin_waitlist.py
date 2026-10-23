"""The waitlist as the team sees it: who signed up, what they want, who asked
for the pilot, and moving people through contacted -> invited -> onboarded.
Every status change writes an admin_audit_log row."""

import csv
import io
import uuid
from datetime import UTC, date, datetime, timedelta

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.database import models
from backend.app.schemas.admin import Page
from backend.app.schemas.waitlist import SignupsOnDay, WaitlistSignupRow, WaitlistStats
from backend.app.services import waitlist
from backend.app.services.admin import record_audit
from backend.app.services.errors import NotFoundError

STATS_DAYS = 30
# A CSV is built in memory; far above launch scale, and a bound all the same.
MAX_EXPORT_ROWS = 20_000
EXPORT_COLUMNS = ("email", "name", "company", "website", "role", "stage", "sells_to", "countries", "wants_pilot",
                  "expectations", "status", "utm_source", "utm_medium", "utm_campaign", "referrer", "created_at")

_W = models.WaitlistSignup


def _filters(q: str | None, pilot: bool | None, status: str | None) -> list:
    filters = []
    if q and q.strip():
        like = f"%{q.strip()}%"
        filters.append(or_(_W.email.ilike(like), _W.name.ilike(like), _W.company.ilike(like)))
    if pilot is not None:
        filters.append(_W.wants_pilot.is_(pilot))
    if status:
        filters.append(_W.status == status)
    return filters


async def list_signups(db: AsyncSession, page: int, per_page: int, q: str | None = None,
                       pilot: bool | None = None, status: str | None = None) -> Page[WaitlistSignupRow]:
    filters = _filters(q, pilot, status)
    total = await db.scalar(select(func.count()).select_from(_W).where(*filters)) or 0
    rows = (await db.scalars(
        select(_W).where(*filters).order_by(_W.created_at.desc()).offset((page - 1) * per_page).limit(per_page)
    )).all()
    return Page(items=[WaitlistSignupRow.model_validate(r) for r in rows], total=total, page=page, per_page=per_page)


async def stats(db: AsyncSession) -> WaitlistStats:
    today = datetime.now(UTC).date()
    first = today - timedelta(days=STATS_DAYS - 1)
    day = func.date(func.timezone("UTC", _W.created_at))
    per_day = dict((await db.execute(
        select(day, func.count()).where(_W.created_at >= datetime.combine(first, datetime.min.time(), UTC))
        .group_by(day)
    )).all())
    by_day = [SignupsOnDay(day=d, signups=per_day.get(d, 0)) for d in (first + timedelta(days=i) for i in range(STATS_DAYS))]

    async def counts(column) -> dict[str, int]:
        rows = (await db.execute(select(column, func.count()).group_by(column))).all()
        return {(value or "unknown"): n for value, n in rows}

    return WaitlistStats(
        total=await db.scalar(select(func.count()).select_from(_W)) or 0,
        last_7_days=sum(d.signups for d in by_day[-7:]),
        pilot=await waitlist.pilot_spots(db),
        by_day=by_day,
        by_stage=await counts(_W.stage),
        by_sells_to=await counts(_W.sells_to),
    )


async def set_status(db: AsyncSession, actor, signup_id: uuid.UUID, status: str) -> WaitlistSignupRow:
    signup = await db.get(_W, signup_id)
    if signup is None:
        raise NotFoundError("Signup not found")
    before = signup.status
    signup.status = status
    await record_audit(db, actor_id=actor.id, actor_email=actor.email, action="waitlist.status",
                       target_type="waitlist_signup", target_id=str(signup_id),
                       before={"status": before, "email": signup.email}, after={"status": status, "email": signup.email})
    await db.commit()
    await db.refresh(signup)
    return WaitlistSignupRow.model_validate(signup)


async def export_csv(db: AsyncSession, pilot: bool | None = None, status: str | None = None) -> str:
    rows = (await db.scalars(
        select(_W).where(*_filters(None, pilot, status)).order_by(_W.created_at).limit(MAX_EXPORT_ROWS)
    )).all()
    out = io.StringIO()
    writer = csv.writer(out)
    writer.writerow(EXPORT_COLUMNS)
    for r in rows:
        source = r.source or {}
        writer.writerow([
            r.email, r.name or "", r.company or "", r.website or "", r.role or "", r.stage or "", r.sells_to or "",
            "; ".join(r.countries or []), "yes" if r.wants_pilot else "no", r.expectations or "", r.status,
            source.get("utm_source", ""), source.get("utm_medium", ""), source.get("utm_campaign", ""),
            source.get("referrer", ""), r.created_at.isoformat(),
        ])
    return out.getvalue()


def export_filename() -> str:
    return f"thalace-waitlist-{date.today().isoformat()}.csv"
