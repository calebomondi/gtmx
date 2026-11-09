"""Each Lace's copy of the founder's CRM (lace_crm_records), refreshed once a
day: the companies and people in it, and where each stands (customer, open
deal, lead, or just on file). Account searches and drafting check it, so a
Lace never treats a customer or an open deal as a cold lead.

Read-only: nothing is written to the CRM here. The copy is replaced whole at
each sync, so a record deleted in the CRM leaves it.
"""

import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import delete, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from agents.helpers import name_key
from agents.lace.apps import AppError
from backend.app.database.connect import AsyncSessionLocal
from backend.app.database.lace_models import Lace, LaceCrmRecord
from backend.app.services.crm_match import email_domain, match_accounts, site_domain
from backend.app.services.lace_apps import DbLaceApps
from config import settings
from utils.log import logger

def rows_for(lace_id: uuid.UUID, crm: str, records: list[dict], now: datetime) -> list[LaceCrmRecord]:
    """The CRM's records as rows to store, with their match keys. A record
    with no site of its own takes the domain of a company of the same name in
    the CRM (a deal names its company, the company has the website). One with
    nothing to match it by (no name, email or site) is left out."""
    sites = {name_key(r.get("company")): d for r in records
             if name_key(r.get("company")) and (d := site_domain(r.get("website")))}
    rows = []
    for r in records:
        company_key = name_key(r.get("company")) or None
        domain = site_domain(r.get("website")) or email_domain(r.get("email")) or sites.get(company_key or "")
        if not (domain or company_key or r.get("email")):
            continue
        rows.append(LaceCrmRecord(
            lace_id=lace_id, crm=crm, kind=r["kind"], name=(r.get("name") or None) and r["name"][:255],
            company=(r.get("company") or None) and r["company"][:255], email=(r.get("email") or None) and r["email"][:320],
            domain=domain and domain[:255], company_key=company_key and company_key[:255], status=r["status"],
            stage=(r.get("stage") or None) and r["stage"][:120], synced_at=now))
    return rows


async def replace(db: AsyncSession, lace: Lace, crm: str | None, records: list[dict], now: datetime) -> int:
    """Swap the Lace's copy for this one (none without a CRM). The caller
    commits. Returns how many records it now holds."""
    await db.execute(delete(LaceCrmRecord).where(LaceCrmRecord.lace_id == lace.id))
    rows = rows_for(lace.id, crm, records, now) if crm else []
    db.add_all(rows)
    lace.crm_synced_at = now
    return len(rows)


async def laces_due(db: AsyncSession, now: datetime, limit: int) -> list[uuid.UUID]:
    """Active Laces whose copy is missing or older than the sync interval,
    the stalest first, bounded."""
    stale = now - timedelta(hours=settings.crm_sync_every_h)
    return list((await db.scalars(select(Lace.id).where(
        Lace.status == "active", or_(Lace.crm_synced_at.is_(None), Lace.crm_synced_at < stale),
    ).order_by(Lace.crm_synced_at.asc().nulls_first()).limit(limit))).all())


async def sync_lace(lace_id: uuid.UUID, now: datetime | None = None) -> int | None:
    """Refresh one Lace's copy of its CRM. Returns how many records it holds,
    or None when the CRM couldn't be read (tried again at the next sweep)."""
    now = now or datetime.now(UTC)
    try:
        found = await DbLaceApps(AsyncSessionLocal, lace_id).crm_snapshot()
    except AppError as exc:
        logger.warning("CRM sync for Lace %s skipped, tried again next sweep: %s", lace_id, exc)
        return None
    crm, records = found if found else (None, [])
    async with AsyncSessionLocal() as db, db.begin():
        lace = await db.get(Lace, lace_id)
        if lace is None:
            return None
        held = await replace(db, lace, crm, records, now)
        await db.flush()
        await match_accounts(db, lace_id, now=now)
        return held
