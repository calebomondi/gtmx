"""A Lace's leads sheet: its rows laid out for following up, offered once
as an approval that makes the sheet and remembers it, and kept up to date
each day with the leads saved since, never touching rows already in it."""

import json
import uuid
from datetime import UTC, datetime, timedelta

import psycopg

from backend.app.database.connect import AsyncSessionLocal
from backend.app.database.lace_models import LaceAppAction
from backend.app.services import lace_app_actions, leads_sheet, leads_sheet_sync
from backend.tests.helpers import stub_accounts
from backend.tests.test_lace_apps import _lace
from backend.tests.test_social_actions import composio  # noqa: F401 -- fixture
from config import settings

NOW = datetime.now(UTC)
# Google's spreadsheet ids are long; a short one isn't read as one.
SHEET = "1LeadsSheet0123456789abcdefgh"


def _sql(query: str, *args):
    with psycopg.connect(settings.database_url, autocommit=True) as conn:
        return conn.execute(query, args).fetchone()


def _lead(lace_id, name, status="target", score=0.5, **columns) -> uuid.UUID:
    values = {"temperature": "cold", "do_not_contact": False, **columns}
    record = json.dumps({"trigger_event": {"event": f"{name} raised a round"}})
    return _sql(f"INSERT INTO lace_accounts (id, lace_id, key, name, account_type, website, record, status, score,"
                f" {', '.join(values)}) VALUES (%s, %s, %s, %s, 'company', %s, %s, %s, %s,"
                f" {', '.join(['%s'] * len(values))}) RETURNING id",
                uuid.uuid4(), lace_id, name.lower(), name, f"https://{name.lower()}.test", record, status, score,
                *values.values())[0]


def _person(lace_id, account_id, name, email=None) -> None:
    _sql("INSERT INTO lace_contacts (id, lace_id, account_id, key, name, title, email, source)"
         " VALUES (%s, %s, %s, %s, %s, 'CEO', %s, 'discovery') RETURNING id",
         uuid.uuid4(), lace_id, account_id, (email or name).lower(), name, email)


def _sent(lace_id, account_id, sent_at, due=None) -> None:
    _sql("INSERT INTO lace_outreach (id, lace_id, user_id, account_id, channel, direction, status, sent_at,"
         " follow_up_due_at, recipient_company, body) VALUES (%s, %s, %s, %s, 'email', 'outbound', 'sent', %s, %s,"
         " '', '...') RETURNING id", uuid.uuid4(), lace_id, uuid.uuid4(), account_id, sent_at, due)


async def _rows(lace_id):
    async with AsyncSessionLocal() as db:
        return await leads_sheet.rows(db, lace_id)


async def test_rows_say_who_to_reach_and_where_each_lead_stands():
    lace = _lace()
    acme = _lead(lace, "Acme", score=0.9, temperature="warm")
    _person(lace, acme, "Bo")
    _person(lace, acme, "Ada", "ada@acme.test")
    _sent(lace, acme, NOW - timedelta(days=2), NOW + timedelta(days=1))
    _lead(lace, "Gone", score=0.8, do_not_contact=True)
    _lead(lace, "Maybe", status="suggested")  # not saved by the founder: not in the sheet
    found = await _rows(lace)
    assert [r[0] for r in found] == ["Acme", "Gone"]
    assert found[0] == ["Acme", "https://acme.test", "Ada", "CEO", "ada@acme.test", "Warm", "Acme raised a round",
                        "Emailed", f"{NOW - timedelta(days=2):%Y-%m-%d}", f"{NOW + timedelta(days=1):%Y-%m-%d}", "",
                        str(acme)]
    assert found[1][7] == "Not interested" and found[1][8:10] == ["", ""]


async def _offer(lace_id):
    async with AsyncSessionLocal() as db:
        return await leads_sheet.offer(db, lace_id)


async def _propose(lace_id) -> LaceAppAction:
    async with AsyncSessionLocal() as db:
        row = LaceAppAction(lace_id=lace_id, app="googlesheets", action="leads_sheet", title="Keep your leads",
                            arguments={"spreadsheet_id": None, "title": "Acme: leads", "with_header": False,
                                       "header": leads_sheet.COLUMNS, "rows": [["Acme"] + [""] * 11]})
        db.add(row)
        await db.commit()
        return row


async def test_approving_the_offer_makes_and_keeps_the_sheet(composio, monkeypatch):  # noqa: F811
    stub_accounts(monkeypatch, {"googlesheets"})
    composio["answers"] = {"GOOGLESHEETS_SHEET_FROM_JSON": {
        "spreadsheetId": SHEET, "spreadsheetUrl": f"https://docs.google.com/spreadsheets/d/{SHEET}/edit"}}
    lace = _lace()
    assert await _offer(lace) is None
    row = await _propose(lace)
    assert await _offer(lace) == "offered"
    async with AsyncSessionLocal() as db:
        done = await lace_app_actions.approve(db, await db.get(LaceAppAction, row.id), uuid.uuid4())
        assert done.status == "done"
        assert await leads_sheet.sheet_of(db, lace) == SHEET
    assert await _offer(lace) == "kept"


async def test_a_declined_offer_stays_declined():
    lace = _lace()
    row = await _propose(lace)
    async with AsyncSessionLocal() as db:
        await lace_app_actions.decline(db, await db.get(LaceAppAction, row.id))
    assert await _offer(lace) == "declined"


async def _keep(lace_id, spreadsheet=SHEET) -> None:
    _sql("UPDATE laces SET status = 'active' WHERE id = %s RETURNING id", lace_id)
    async with AsyncSessionLocal() as db:
        await leads_sheet.keep(db, lace_id, f"https://docs.google.com/spreadsheets/d/{spreadsheet}")
        await db.commit()


async def _due(lace_id, now=NOW) -> bool:
    async with AsyncSessionLocal() as db:
        return lace_id in await leads_sheet_sync.laces_due(db, now, 1000)


async def test_each_day_the_sheet_gets_the_leads_missing_from_it(composio, monkeypatch):  # noqa: F811
    stub_accounts(monkeypatch, {"googlesheets"})
    lace = _lace()
    there, new = _lead(lace, "Acme", score=0.9), _lead(lace, "Beta", score=0.4)
    await _keep(lace)
    assert await _due(lace)
    # The founder moved the Lead id column and added a row of their own.
    composio["answers"] = {
        "GOOGLESHEETS_GET_SHEET_NAMES": {"sheet_names": ["Leads"]},
        "GOOGLESHEETS_BATCH_GET": {"valueRanges": [{"values": [
            ["Lead id", "Company", "Notes"], [str(there), "Acme", "Met at iHub"], ["", "Their own lead", ""]]}]}}
    assert await leads_sheet_sync.sync_lace(lace, NOW) == 1
    [append] = [args for tool, args in composio["calls"] if tool == "GOOGLESHEETS_SPREADSHEETS_VALUES_APPEND"]
    assert append["spreadsheetId"] == SHEET and append["range"] == "Leads"
    assert [(r[0], r[-1]) for r in append["values"]] == [("Beta", str(new))]
    assert not await _due(lace) and await _due(lace, NOW + timedelta(hours=settings.leads_sheet_sync_every_h + 1))


async def test_a_sheet_without_the_lead_id_column_is_left_alone(composio, monkeypatch):  # noqa: F811
    stub_accounts(monkeypatch, {"googlesheets"})
    lace = _lace()
    _lead(lace, "Acme")
    await _keep(lace)
    composio["answers"] = {
        "GOOGLESHEETS_GET_SHEET_NAMES": {"sheet_names": ["Leads"]},
        "GOOGLESHEETS_BATCH_GET": {"valueRanges": [{"values": [["Company"], ["Acme"]]}]}}
    assert await leads_sheet_sync.sync_lace(lace, NOW) is None
    assert all(tool != "GOOGLESHEETS_SPREADSHEETS_VALUES_APPEND" for tool, _ in composio["calls"])
    # Not read again until the next day.
    assert not await _due(lace)


def _account(account_id) -> tuple:
    return _sql("SELECT founder_notes, temperature, do_not_contact, sheet_status FROM lace_accounts WHERE id = %s",
                account_id)


async def _read_back(lace_id, rows) -> int:
    async with AsyncSessionLocal() as db:
        changed = await leads_sheet.read_back(db, lace_id, rows, NOW)
        await db.commit()
        return changed


async def test_the_founders_notes_and_status_come_back_from_the_sheet():
    lace = _lace()
    acme, beta, gamma = _lead(lace, "Acme"), _lead(lace, "Beta"), _lead(lace, "Gamma")
    header = ["Company", "Status", "Notes", "Lead id"]
    assert await _read_back(lace, [header, ["Acme", "Customer", " Signed in Nov ", str(acme)],
                                   ["Beta", "Not interested", "", str(beta)], ["Gamma", "Call Friday", "", str(gamma)],
                                   ["Nobody", "Customer", "", "not-an-id"]]) == 2
    assert _account(acme) == ("Signed in Nov", "customer", False, "Customer")
    assert _account(beta) == (None, "cold", True, "Not interested")
    # A status of the founder's own changes nothing but is remembered.
    assert _account(gamma) == (None, "cold", False, "Call Friday")


async def test_an_old_status_in_the_sheet_never_undoes_the_app():
    lace = _lace()
    acme = _lead(lace, "Acme")
    rows = [["Status", "Lead id"], ["Customer", str(acme)]]
    await _read_back(lace, rows)
    # The founder takes "customer" back in the app; the sheet still says it.
    _sql("UPDATE lace_accounts SET temperature = 'cold' WHERE id = %s RETURNING id", acme)
    assert await _read_back(lace, rows) == 0 and _account(acme)[1] == "cold"
