"""Google Sheets through a stubbed Composio, as its documented response
shapes: reading a tab for the Lace, and the exports a founder approves."""

import pytest

from backend.app.database.connect import AsyncSessionLocal
from backend.app.services import lace_apps, sheet_actions
from backend.app.services.lace_app_actions import ActionFailed
from backend.tests.helpers import stub_accounts
from backend.tests.test_lace_apps import _lace
from backend.tests.test_social_actions import _ctx, composio  # noqa: F401 -- fixture

ROWS = [["Name", "Type"], ["Farm A", "customer"]]


async def test_exporting_to_a_new_spreadsheet(composio):  # noqa: F811
    composio["answers"] = {"GOOGLESHEETS_SHEET_FROM_JSON": {"response_data": {
        "spreadsheetId": "s1", "spreadsheetUrl": "https://docs.google.com/spreadsheets/d/s1/edit"}}}
    outcome = await sheet_actions.export(_ctx("googlesheets"), {
        "spreadsheet_id": None, "title": "Acme: accounts", "header": ROWS[0], "rows": ROWS[1:]})
    assert composio["calls"] == [("GOOGLESHEETS_SHEET_FROM_JSON", {
        "title": "Acme: accounts", "sheet_name": "Sheet1", "sheet_json": [{"Name": "Farm A", "Type": "customer"}]})]
    assert (outcome.result, outcome.url) == ("Made “Acme: accounts” with 1 rows.",
                                             "https://docs.google.com/spreadsheets/d/s1/edit")


async def test_exporting_into_the_founders_sheet_appends(composio):  # noqa: F811
    outcome = await sheet_actions.export(_ctx("googlesheets"), {
        "spreadsheet_id": "s2", "title": "x", "header": ROWS[0], "rows": ROWS[1:]})
    assert composio["calls"] == [("GOOGLESHEETS_SPREADSHEETS_VALUES_APPEND", {
        "spreadsheetId": "s2", "range": "A1", "valueInputOption": "RAW", "insertDataOption": "INSERT_ROWS",
        "values": [["Farm A", "customer"]]})]
    assert outcome.url == "https://docs.google.com/spreadsheets/d/s2"


async def test_an_export_with_no_spreadsheet_back_fails_with_why(composio):  # noqa: F811
    with pytest.raises(ActionFailed, match="look for it in your Drive"):
        await sheet_actions.export(_ctx("googlesheets"), {"spreadsheet_id": None, "title": "x", "header": ["A"],
                                                          "rows": [["1"]]})


async def test_the_lace_reads_a_tab_by_name(composio, monkeypatch):  # noqa: F811
    stub_accounts(monkeypatch, {"googlesheets"})
    composio["answers"] = {
        "GOOGLESHEETS_GET_SHEET_NAMES": {"sheet_names": ["Leads", "Bob's notes"]},
        "GOOGLESHEETS_BATCH_GET": {"spreadsheet_data": {"valueRanges": [{"values": [["Name"], ["Farm A", 12]]}]}},
    }
    apps = lace_apps.DbLaceApps(AsyncSessionLocal, _lace())
    assert await apps.sheet("s1", "bob's NOTES") == {"tabs": ["Leads", "Bob's notes"], "tab": "Bob's notes",
                                                    "rows": [["Name"], ["Farm A", "12"]]}
    assert composio["calls"][1] == ("GOOGLESHEETS_BATCH_GET", {"spreadsheet_id": "s1",
                                                               "ranges": ["'Bob''s notes'!A1:ZZ1000"]})
    with pytest.raises(lace_apps.AppError, match="no tab named 'Pipeline'"):
        await apps.sheet("s1", "Pipeline")


async def test_without_google_sheets_nothing_is_read(composio, monkeypatch):  # noqa: F811
    stub_accounts(monkeypatch, set())
    assert await lace_apps.DbLaceApps(AsyncSessionLocal, _lace()).sheet("s1", None) is None
    assert composio["calls"] == []
