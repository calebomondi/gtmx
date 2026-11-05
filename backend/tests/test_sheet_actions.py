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



async def test_writing_rows_appends_or_updates_a_range(composio):  # noqa: F811
    added = await sheet_actions.write(_ctx("googlesheets"), {
        "spreadsheet_id": "s3", "rows": [["Acme", "lead"]], "tab": "Pipeline", "range": None})
    assert composio["calls"][0] == ("GOOGLESHEETS_SPREADSHEETS_VALUES_APPEND", {
        "spreadsheetId": "s3", "range": "Pipeline", "valueInputOption": "USER_ENTERED",
        "insertDataOption": "INSERT_ROWS", "values": [["Acme", "lead"]]})
    assert added.result == "Added 1 rows to Pipeline."
    updated = await sheet_actions.write(_ctx("googlesheets"), {
        "spreadsheet_id": "s3", "rows": [["won"]], "tab": None, "range": "Sheet1!C2"})
    assert composio["calls"][1] == ("GOOGLESHEETS_VALUES_UPDATE", {
        "spreadsheet_id": "s3", "range": "Sheet1!C2", "value_input_option": "USER_ENTERED", "values": [["won"]]})
    assert updated.result == "Updated Sheet1!C2 (1 rows)." and updated.url.endswith("/s3")


async def test_a_missing_permission_says_to_reconnect(monkeypatch):
    stub_accounts(monkeypatch, {"googlesheets"})
    answers = {"GOOGLESHEETS_SEARCH_SPREADSHEETS": {"data": {"spreadsheets": [
        {"id": "s1", "name": "Antler application", "modifiedTime": "2026-11-01"}]}, "error": None, "log_id": "l"}}
    monkeypatch.setattr(lace_apps.connection_service, "execute_tool", lambda e, tool, args, c: answers[tool])
    apps = lace_apps.DbLaceApps(AsyncSessionLocal, _lace())
    assert await apps.sheet_search("Antler") == [{"id": "s1", "name": "Antler application",
                                                  "url": "https://docs.google.com/spreadsheets/d/s1",
                                                  "modified": "2026-11-01"}]
    answers["GOOGLESHEETS_SEARCH_SPREADSHEETS"] = {"data": None, "log_id": None,
                                                   "error": "403 ACCESS_TOKEN_SCOPE_INSUFFICIENT"}
    with pytest.raises(lace_apps.AppError, match="without every permission it needs.*ask for the sheet's link"):
        await apps.sheet_search("Antler")


async def test_sheets_and_notion_read_unwrapped_responses(monkeypatch):
    """Composio stopped wrapping some apps' responses (response_data,
    spreadsheet_data): what they return is read either way."""
    stub_accounts(monkeypatch, {"googlesheets", "notion"})
    answers = {
        "GOOGLESHEETS_GET_SHEET_NAMES": {"sheet_names": ["Sheet1"]},
        "GOOGLESHEETS_BATCH_GET": {"spreadsheetId": "s1", "valueRanges": [{"values": [["Question", "Answer"]]}]},
        "NOTION_SEARCH_NOTION_PAGE": {"results": [{"id": "p1", "object": "page", "url": "https://notion.so/p1",
                                                   "properties": {"title": {"title": [{"plain_text": "Antler"}]}}}]},
    }
    monkeypatch.setattr(lace_apps.connection_service, "execute_tool",
                        lambda e, tool, args, c: {"data": answers[tool], "error": None, "log_id": "l"})
    apps = lace_apps.DbLaceApps(AsyncSessionLocal, _lace())
    assert (await apps.sheet("s1", None))["rows"] == [["Question", "Answer"]]
    assert [p["id"] for p in await apps.notion_search("Antler")] == ["p1"]
