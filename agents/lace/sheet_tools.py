"""The Lace's Google Sheets tools: finding a sheet by name, reading one (a
lead list to import, a pipeline to sum up) with its numbers worked out in
code, and, as proposals the founder approves, exporting its accounts or
contacts or writing rows to one of their sheets."""

from typing import Literal

from langchain_core.tools import BaseTool, tool

from agents.lace.app_actions import propose
from agents.lace.apps import AppError, LaceApps
from agents.lace.sheets import sheet_id, summarise
from agents.lace.store import LaceStore
from agents.lace.tool_guard import guarded
from agents.schemas.lace import ProposedAction, ToolResult

# Rows of a sheet shown to the model (its summary covers every row read).
ROWS_SHOWN = 50
# The most rows one export writes, and shown in its preview.
EXPORT_MAX = 500
PREVIEW_ROWS = 5
# The most rows one write puts in a founder's sheet, and the longest name searched.
WRITE_MAX = 200
QUERY_CHARS = 100
NOT_CONNECTED = ("Google Sheets isn't connected for this Lace, or is switched off. "
                 "The founder can connect it under Apps & accounts in your settings.")

_ACCOUNT_COLUMNS = ["Name", "Type", "Website", "Location", "Why now", "Need", "Fit", "Contacts"]
_CONTACT_COLUMNS = ["Name", "Title", "Company", "Email", "LinkedIn", "X", "Instagram"]


async def _rows(store: LaceStore, what: Literal["accounts", "contacts"]) -> list[list[str]]:
    if what == "accounts":
        return [[a.name, a.account_type, a.website or "", a.geo or "", a.trigger or "", a.need or "",
                 a.fit_strength or "", ", ".join(c.get("name") or "" for c in a.contacts if c.get("name"))]
                for a in await store.accounts(limit=EXPORT_MAX)]
    return [[c.name or "", c.title or "", c.company, c.email or "", c.linkedin or "", c.x or "", c.instagram or ""]
            for c in await store.contacts(limit=EXPORT_MAX)]


def build_sheet_tools(store: LaceStore, apps: LaceApps) -> list[BaseTool]:

    @tool(parse_docstring=True)
    @guarded
    async def read_sheet(url: str, tab: str | None = None) -> ToolResult:
        """Read a Google Sheet the founder shares a link to: a lead list to import (once the founder says so, add the people with add_contact), or a pipeline or tracker to sum up. Returns the rows and, worked out exactly, each column's totals or counts: quote those, never add up rows yourself.

        Args:
            url: The sheet's link, docs.google.com/spreadsheets/d/...
            tab: Which tab to read, by name; the first tab when not given.
        """
        spreadsheet = sheet_id(url)
        if spreadsheet is None:
            return ToolResult.failure("That isn't a Google Sheets link (docs.google.com/spreadsheets/d/...).")
        try:
            sheet = await apps.sheet(spreadsheet, tab)
        except AppError as exc:
            return ToolResult.failure(str(exc))
        if sheet is None:
            return ToolResult.failure(NOT_CONNECTED)
        rows = sheet["rows"]
        summary = summarise(rows)
        shown = rows[:ROWS_SHOWN + 1]
        more = f" Showing the first {ROWS_SHOWN} rows; the totals cover all {summary['rows']}." \
            if summary["rows"] > ROWS_SHOWN else ""
        return ToolResult.success(
            f"Tab {sheet['tab']!r} ({len(sheet['tabs'])} tabs: {', '.join(sheet['tabs'])}): "
            f"{summary['rows']} rows.{more}",
            {"summary": summary, "rows": shown})

    @tool(parse_docstring=True)
    @guarded
    async def export_to_sheet(what: Literal["accounts", "contacts"], sheet_url: str | None = None,
                              title: str | None = None) -> ToolResult:
        """Propose exporting your saved leads or contacts to Google Sheets: a new spreadsheet, or appended to one the founder links. It runs only if they approve it.

        Args:
            what: accounts or contacts.
            sheet_url: A sheet to add the rows to; a new spreadsheet when not given.
            title: The new spreadsheet's name.
        """
        spreadsheet = sheet_id(sheet_url) if sheet_url else None
        if sheet_url and spreadsheet is None:
            return ToolResult.failure("That isn't a Google Sheets link (docs.google.com/spreadsheets/d/...).")
        rows = await _rows(store, what)
        if not rows:
            return ToolResult.failure(f"There are no saved {what} to export yet.")
        header = _ACCOUNT_COLUMNS if what == "accounts" else _CONTACT_COLUMNS
        profile = await store.profile()
        name = (title or "").strip() or f"{profile.startup_name or profile.name}: {what}"
        where = "your sheet" if spreadsheet else f"a new spreadsheet, “{name}”"
        preview = "\n".join([f"{len(rows)} {what} to {where}:", " | ".join(header),
                             *(" | ".join(r) for r in rows[:PREVIEW_ROWS]),
                             *([f"…and {len(rows) - PREVIEW_ROWS} more"] if len(rows) > PREVIEW_ROWS else [])])
        return await propose(store, ProposedAction(
            app="googlesheets", action="export", title=f"Export {len(rows)} {what} to Google Sheets", preview=preview,
            arguments={"spreadsheet_id": spreadsheet, "title": name[:100], "header": header, "rows": rows}))

    @tool(parse_docstring=True)
    @guarded
    async def search_sheets(name: str) -> ToolResult:
        """Find spreadsheets in the founder's Google Drive by name, when they mention a sheet without a link ("the Antler application sheet"). Then read one with read_sheet and its url.

        Args:
            name: Words from the sheet's name, e.g. "Antler application".
        """
        words = " ".join(name.split())[:QUERY_CHARS]
        if not words:
            return ToolResult.failure("Give words from the sheet's name.")
        try:
            found = await apps.sheet_search(words)
        except AppError as exc:
            return ToolResult.failure(str(exc))
        if found is None:
            return ToolResult.failure(NOT_CONNECTED)
        if not found:
            return ToolResult.success(f"No spreadsheet named like “{words}”. Ask the founder for its link.", [])
        return ToolResult.success(f"{len(found)} spreadsheets match, newest first.", found)

    @tool(parse_docstring=True)
    @guarded
    async def update_sheet(sheet_url: str, rows: list[list[str]], tab: str | None = None,
                           cell_range: str | None = None) -> ToolResult:
        """Propose writing to one of the founder's Google Sheets: rows added after the last row of a tab, or written over a range. It runs only if they approve it. Read the sheet first (read_sheet) so the columns line up.

        Args:
            sheet_url: The sheet's link (from the founder or search_sheets).
            rows: The rows to write, each a list of cell values in the sheet's column order.
            tab: The tab to add rows to; the first tab when not given.
            cell_range: Write over this range instead of adding rows, in A1 notation, e.g. "Sheet1!B2:D4".
        """
        spreadsheet = sheet_id(sheet_url)
        if spreadsheet is None:
            return ToolResult.failure("That isn't a Google Sheets link (docs.google.com/spreadsheets/d/...).")
        clean = [[str(cell) for cell in row] for row in rows if any(str(cell).strip() for cell in row)]
        if not clean:
            return ToolResult.failure("There are no rows to write.")
        if len(clean) > WRITE_MAX:
            return ToolResult.failure(f"Write at most {WRITE_MAX} rows at a time.")
        where = f"over {cell_range}" if cell_range else f"after the last row of {tab or 'the first tab'}"
        preview = "\n".join([f"{len(clean)} rows {where}:", *(" | ".join(r) for r in clean[:PREVIEW_ROWS]),
                             *([f"…and {len(clean) - PREVIEW_ROWS} more"] if len(clean) > PREVIEW_ROWS else [])])
        return await propose(store, ProposedAction(
            app="googlesheets", action="write", title=f"Write {len(clean)} rows to a Google Sheet", preview=preview,
            arguments={"spreadsheet_id": spreadsheet, "rows": clean, "tab": tab, "range": cell_range}))

    return [read_sheet, export_to_sheet, search_sheets, update_sheet]
