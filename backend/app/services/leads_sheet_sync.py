"""Keeping each Lace's leads sheet (services.leads_sheet) up to date, once
a day: the leads saved since its last sync that aren't in it yet are added
at the end of its first tab, as the founder's standing approval."""

import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import exists, select
from sqlalchemy.ext.asyncio import AsyncSession

from agents.lace.apps import AppError
from backend.app.database.connect import AsyncSessionLocal
from backend.app.database.lace_models import Lace, LaceApp
from backend.app.services import lace_app_actions, leads_sheet
from backend.app.services.lace_apps import DbLaceApps
from config import settings
from utils.log import logger


async def laces_due(db: AsyncSession, now: datetime, limit: int) -> list[uuid.UUID]:
    """Active Laces with a leads sheet not synced within the interval,
    the stalest first, bounded."""
    stale = now - timedelta(hours=settings.leads_sheet_sync_every_h)
    kept = (await db.scalars(select(LaceApp).where(
        LaceApp.platform == leads_sheet.APP, LaceApp.enabled.is_(True),
        exists().where(Lace.id == LaceApp.lace_id, Lace.status == "active")))).all()
    due = []
    for row in kept:
        values = row.settings or {}
        synced = values.get(leads_sheet.SYNCED_KEY)
        if values.get(leads_sheet.SHEET_KEY) and (not synced or datetime.fromisoformat(synced) < stale):
            due.append((synced or "", row.lace_id))
    return [lace_id for _, lace_id in sorted(due)[:limit]]


async def _synced(db: AsyncSession, lace_id: uuid.UUID, now: datetime) -> None:
    row = await leads_sheet.settings_row(db, lace_id)
    if row is not None:
        row.settings = {**(row.settings or {}), leads_sheet.SYNCED_KEY: now.isoformat()}
    await db.commit()


async def sync_lace(lace_id: uuid.UUID, now: datetime | None = None) -> int | None:
    """Add the saved leads missing from the Lace's leads sheet. Returns how
    many rows were added, or None when the sheet couldn't be read or written
    (tried again at the next sweep)."""
    now = now or datetime.now(UTC)
    async with AsyncSessionLocal() as db:
        spreadsheet = await leads_sheet.sheet_of(db, lace_id)
    if spreadsheet is None:
        return None
    try:
        sheet = await DbLaceApps(AsyncSessionLocal, lace_id).sheet(spreadsheet, None)
    except AppError as exc:
        logger.warning("Leads sheet sync for Lace %s skipped, tried again next sweep: %s", lace_id, exc)
        return None
    if sheet is None:
        return None
    in_sheet = leads_sheet.ids_in(sheet["rows"])
    async with AsyncSessionLocal() as db:
        if in_sheet is None:
            # Without the column, every lead would look new: add nothing, and
            # don't read it again until the next day.
            logger.warning("Leads sheet of Lace %s has no %r column; nothing added", lace_id, leads_sheet.ID_COLUMN)
            await _synced(db, lace_id, now)
            return None
        lace = await db.get(Lace, lace_id)
        missing = await leads_sheet.rows(db, lace_id, leaving_out=in_sheet) if lace else []
        added = 0
        if missing:
            action = await lace_app_actions.run_standing(
                db, lace, leads_sheet.APP, "write", f"Add {len(missing)} leads to your leads sheet",
                "\n".join(r[0] for r in missing),
                {"spreadsheet_id": spreadsheet, "rows": missing, "tab": sheet["tab"], "range": None})
            if action is None or action.status != "done":
                return None
            added = len(missing)
        await _synced(db, lace_id, now)
    return added
