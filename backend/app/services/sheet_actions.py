"""The Google Sheets actions a Lace can propose, run on the founder's approval
(lace_app_actions): exporting its saved accounts or contacts to a new
spreadsheet, or appending them to one the founder linked. Composio tools
verified against the live catalog (2026-10-24)."""

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
    created = (done["data"] or {}).get("response_data") or {}
    spreadsheet = created.get("spreadsheetId")
    if not spreadsheet:
        raise ActionFailed("Google Sheets didn't say which spreadsheet it made; look for it in your Drive.")
    return Outcome(f"Made “{arguments['title']}” with {len(rows)} rows.",
                   created.get("spreadsheetUrl") or _SHEET_URL.format(spreadsheet), done["log_id"])
