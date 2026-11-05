"""The Google Sheets actions a Lace can propose, run on the founder's approval
(lace_app_actions): exporting its saved accounts or contacts to a new
spreadsheet, or appending them to one the founder linked. Composio tools
verified against the live catalog (2026-10-24)."""

from backend.app.services import connections as connection_service
from backend.app.services.lace_app_actions import ActionFailed, Outcome, RunContext, call, runs

_SHEET_URL = "https://docs.google.com/spreadsheets/d/{}"


@runs("googlesheets", "export")
async def export(ctx: RunContext, arguments: dict) -> Outcome:
    header, rows = arguments["header"], arguments["rows"]
    if arguments.get("spreadsheet_id"):
        done = await call(ctx, "GOOGLESHEETS_SPREADSHEETS_VALUES_APPEND", {
            "spreadsheetId": arguments["spreadsheet_id"], "range": "A1", "valueInputOption": "RAW",
            "insertDataOption": "INSERT_ROWS", "values": rows})
        return Outcome(f"Added {len(rows)} rows to your sheet.", _SHEET_URL.format(arguments["spreadsheet_id"]),
                       done["log_id"])
    done = await call(ctx, "GOOGLESHEETS_SHEET_FROM_JSON", {
        "title": arguments["title"], "sheet_name": "Sheet1",
        "sheet_json": [dict(zip(header, row)) for row in rows]})
    created = connection_service.payload(done["data"])
    spreadsheet = created.get("spreadsheetId")
    if not spreadsheet:
        raise ActionFailed("Google Sheets didn't say which spreadsheet it made; look for it in your Drive.")
    return Outcome(f"Made “{arguments['title']}” with {len(rows)} rows.",
                   created.get("spreadsheetUrl") or _SHEET_URL.format(spreadsheet), done["log_id"])


@runs("googlesheets", "write")
async def write(ctx: RunContext, arguments: dict) -> Outcome:
    """Rows the founder approved: appended after a tab's last row, or written
    over a range they named."""
    rows, spreadsheet = arguments["rows"], arguments["spreadsheet_id"]
    if arguments.get("range"):
        done = await call(ctx, "GOOGLESHEETS_VALUES_UPDATE", {
            "spreadsheet_id": spreadsheet, "range": arguments["range"], "value_input_option": "USER_ENTERED",
            "values": rows})
        result = f"Updated {arguments['range']} ({len(rows)} rows)."
    else:
        done = await call(ctx, "GOOGLESHEETS_SPREADSHEETS_VALUES_APPEND", {
            "spreadsheetId": spreadsheet, "range": arguments.get("tab") or "A1", "valueInputOption": "USER_ENTERED",
            "insertDataOption": "INSERT_ROWS", "values": rows})
        result = f"Added {len(rows)} rows" + (f" to {arguments['tab']}." if arguments.get("tab") else ".")
    return Outcome(result, _SHEET_URL.format(spreadsheet), done["log_id"])
