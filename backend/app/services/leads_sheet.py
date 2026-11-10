"""Each Lace's leads sheet: one Google Sheet of its saved leads, laid out
for following up (who to reach, how warm, when last contacted, when next),
that the founder keeps working in.

The Lace offers it once, as an approval card (lace_app_actions, action
"leads_sheet"); approving makes the sheet and remembers it in the Lace's
Google Sheets settings, declining stops the offer. Once a day each leads
sheet gets the leads saved since that aren't in it yet, found by the Lead id
column, and what the founder changed there is read back onto the leads: their
Notes, and a Status of Customer or Not interested (leads_sheet_sync). Rows
already in the sheet are the founder's: they are never rewritten.
"""

import uuid
from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from agents.lace.sheets import sheet_id
from agents.schemas.lace import LEAD_SHEET_COLUMNS
from backend.app.database.lace_models import LaceAccount, LaceApp, LaceAppAction, LaceContact, LaceOutreach
from backend.app.services import lead_temperature
from utils.log import logger

APP, ACTION = "googlesheets", "leads_sheet"
# The setting holding the sheet's id, and when it was last synced.
SHEET_KEY, SYNCED_KEY = "leads_sheet", "leads_sheet_synced_at"
COLUMNS = LEAD_SHEET_COLUMNS
ID_COLUMN = LEAD_SHEET_COLUMNS[-1]
# The most leads one sheet write carries.
ROWS_MAX = 200
SHEET_URL = "https://docs.google.com/spreadsheets/d/{}"


def _day(at: datetime | None) -> str:
    return f"{at:%Y-%m-%d}" if at else ""


def _status(account: LaceAccount, emailed: bool, replied: bool) -> str:
    if account.temperature == "customer":
        return "Customer"
    if account.do_not_contact:
        return "Not interested"
    return "Replied" if replied else "Emailed" if emailed else "New"


async def rows(db: AsyncSession, lace_id: uuid.UUID, limit: int = ROWS_MAX,
               leaving_out: set[str] | None = None) -> list[list[str]]:
    """The team's saved leads as sheet rows in COLUMNS order, strongest fit
    first, without those whose ids are in `leaving_out`."""
    accounts = (await db.scalars(select(LaceAccount).where(
        LaceAccount.lace_id == lace_id, LaceAccount.team(), LaceAccount.status == "target",
        LaceAccount.id.not_in([uuid.UUID(i) for i in leaving_out or set() if _is_uuid(i)]),
    ).order_by(LaceAccount.score.desc().nulls_last(), LaceAccount.first_seen_at).limit(limit))).all()
    if not accounts:
        return []
    ids = [a.id for a in accounts]
    people: dict[uuid.UUID, LaceContact] = {}
    for c in (await db.scalars(select(LaceContact).where(LaceContact.account_id.in_(ids)).order_by(
            LaceContact.email.is_(None), LaceContact.first_seen_at))).all():
        people.setdefault(c.account_id, c)
    sent = dict((await db.execute(select(LaceOutreach.account_id, func.max(LaceOutreach.sent_at)).where(
        LaceOutreach.account_id.in_(ids), LaceOutreach.direction == "outbound", LaceOutreach.sent_at.is_not(None),
    ).group_by(LaceOutreach.account_id))).all())
    due = dict((await db.execute(select(LaceOutreach.account_id, func.min(LaceOutreach.follow_up_due_at)).where(
        LaceOutreach.account_id.in_(ids), LaceOutreach.follow_up_due_at.is_not(None),
    ).group_by(LaceOutreach.account_id))).all())
    replied = set((await db.scalars(select(LaceOutreach.account_id).where(
        LaceOutreach.account_id.in_(ids), LaceOutreach.direction == "inbound"))).all())
    out = []
    for a in accounts:
        person = people.get(a.id)
        trigger = ((a.record or {}).get("trigger_event") or {}).get("event") or ""
        out.append([a.name, a.website or "", (person and person.name) or "", (person and person.title) or "",
                    (person and person.email) or "", a.temperature.capitalize(), trigger,
                    _status(a, a.id in sent, a.id in replied), _day(sent.get(a.id)), _day(due.get(a.id)), "",
                    str(a.id)])
    return out


def _is_uuid(value: str) -> bool:
    try:
        uuid.UUID(value)
    except ValueError:
        return False
    return True


async def settings_row(db: AsyncSession, lace_id: uuid.UUID) -> LaceApp | None:
    return await db.scalar(select(LaceApp).where(LaceApp.lace_id == lace_id, LaceApp.platform == APP))


async def sheet_of(db: AsyncSession, lace_id: uuid.UUID) -> str | None:
    """The id of the Lace's leads sheet, if it keeps one."""
    row = await settings_row(db, lace_id)
    return (row.settings or {}).get(SHEET_KEY) if row else None


async def offer(db: AsyncSession, lace_id: uuid.UUID) -> str | None:
    """Where the offer of a leads sheet stands: "kept" (there is one),
    "offered" (waiting for the founder), "declined", or None (never made)."""
    if await sheet_of(db, lace_id):
        return "kept"
    last = await db.scalar(select(LaceAppAction.status).where(
        LaceAppAction.lace_id == lace_id, LaceAppAction.app == APP, LaceAppAction.action == ACTION,
    ).order_by(LaceAppAction.created_at.desc()).limit(1))
    return {"proposed": "offered", "running": "offered", "declined": "declined"}.get(last or "")


async def keep(db: AsyncSession, lace_id: uuid.UUID, url: str | None) -> None:
    """Remember the sheet an approved offer made (or added to) as the
    Lace's leads sheet. The caller commits."""
    spreadsheet = sheet_id(url or "")
    if spreadsheet is None:
        logger.warning("Leads sheet for Lace %s made, but its link %r names no sheet", lace_id, url)
        return
    row = await settings_row(db, lace_id)
    if row is None:
        db.add(LaceApp(lace_id=lace_id, platform=APP, enabled=True, settings={SHEET_KEY: spreadsheet}))
    else:
        row.settings = {**(row.settings or {}), SHEET_KEY: spreadsheet}


# What the founder's Status says, read back: only these change the lead.
STATUS_CUSTOMER, STATUS_STOP = "customer", "not interested"
NOTES_CHARS = 1_000
STATUS_CHARS = 40


def _column(header: list[str], name: str) -> int | None:
    names = [cell.strip().lower() for cell in header]
    return names.index(name.lower()) if name.lower() in names else None


async def read_back(db: AsyncSession, lace_id: uuid.UUID, sheet_rows: list[list[str]],
                    now: datetime | None = None) -> int:
    """What the founder changed in their leads sheet, onto the leads: their
    Notes, and a Status of Customer (it's a customer) or Not interested (no
    more contact), when it changed since it was last read. Other statuses are
    the founder's own and change nothing, nor does clearing one. Returns how
    many leads changed; the caller commits."""
    if not sheet_rows:
        return 0
    header = sheet_rows[0]
    at_id, at_status, at_notes = (_column(header, name) for name in (ID_COLUMN, "Status", "Notes"))
    if at_id is None:
        return 0

    def cell(row: list[str], at: int | None) -> str:
        return row[at].strip() if at is not None and len(row) > at else ""
    by_id = {cell(r, at_id): r for r in sheet_rows[1:] if _is_uuid(cell(r, at_id))}
    if not by_id:
        return 0
    accounts = (await db.scalars(select(LaceAccount).where(
        LaceAccount.lace_id == lace_id, LaceAccount.team(), LaceAccount.status == "target",
        LaceAccount.id.in_([uuid.UUID(i) for i in by_id])))).all()
    changed = 0
    for account in accounts:
        row = by_id[str(account.id)]
        notes, status = cell(row, at_notes)[:NOTES_CHARS] or None, cell(row, at_status)[:STATUS_CHARS]
        before = (account.founder_notes, account.temperature, account.do_not_contact)
        if at_notes is not None:
            account.founder_notes = notes
        if at_status is not None and status != (account.sheet_status or ""):
            if status.lower() == STATUS_CUSTOMER and account.temperature != "customer":
                await lead_temperature.set_customer(db, account, True, now)
            if status.lower() == STATUS_STOP:
                account.do_not_contact = True
            account.sheet_status = status or None
        changed += before != (account.founder_notes, account.temperature, account.do_not_contact)
    return changed


def ids_in(sheet_rows: list[list[str]]) -> set[str] | None:
    """The Lead ids already in a sheet, read from its Lead id column (by the
    header, wherever the founder moved it); None when it has no such column."""
    header = [cell.strip().lower() for cell in sheet_rows[0]] if sheet_rows else []
    if ID_COLUMN.lower() not in header:
        return None
    at = header.index(ID_COLUMN.lower())
    return {row[at].strip() for row in sheet_rows[1:] if len(row) > at and row[at].strip()}
