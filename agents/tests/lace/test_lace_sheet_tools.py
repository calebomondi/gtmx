"""The Lace's Google Sheets tools: a shared sheet is read with its totals and
counts worked out in code; an export is a proposal the founder approves."""

import json

import pytest

from agents.lace.apps import AppError
from agents.lace.sheets import number, sheet_id, summarise
from agents.lace.tools import build_tools
from agents.schemas.lace import AccountSummary

URL = "https://docs.google.com/spreadsheets/d/1AbCdEfGhIjKlMnOpQrStUvWxYz0123456789/edit#gid=0"
PIPELINE = [["Company", "Stage", "Value"],
            ["Alpha", "Won", "KES 1,200"], ["Beta", "Lead", "300"], ["Gamma", "Won", "1500.5"], ["Delta", "Lead", ""]]


class Apps:
    def __init__(self, sheet=None, error=None):
        self.result, self.error, self.asked = sheet, error, []

    async def sheet(self, spreadsheet_id, tab):
        self.asked.append((spreadsheet_id, tab))
        if self.error:
            raise AppError(self.error)
        return self.result


def _tools(store, settings, apps):
    return {t.name: t for t in build_tools(store, settings, apps=apps)}


async def _run(tool, **args) -> dict:
    return json.loads(await tool.ainvoke(args))


@pytest.mark.parametrize("cell, value", [
    ("KES 1,200", 1200.0), ("$3.5", 3.5), ("40%", 40.0), ("-7", -7.0), ("2026-10-24", None), ("+254 712 000", None),
    ("Won", None), ("", None),
])
def test_numbers_read_from_cells(cell, value):
    assert number(cell) == value


def test_a_pipeline_is_summed_and_counted_in_code():
    summary = summarise(PIPELINE)
    company, stage, value = summary["columns"]
    assert summary["rows"] == 4
    assert (company["filled"], "counts" in company, "sum" in company) == (4, False, False)  # all different
    assert stage["counts"] == {"Won": 2, "Lead": 2}
    assert (value["filled"], value["sum"], value["min"], value["max"], value["average"]) == (3, 3000.5, 300.0, 1500.5, 1000.17)


def test_a_sheet_link_gives_its_id():
    assert sheet_id(URL) == "1AbCdEfGhIjKlMnOpQrStUvWxYz0123456789"
    assert sheet_id("https://example.com/sheet") is None


async def test_reading_a_shared_sheet(store, settings):
    apps = Apps({"tabs": ["Pipeline", "Notes"], "tab": "Pipeline", "rows": PIPELINE})
    out = await _run(_tools(store, settings, apps)["read_sheet"], url=URL)
    assert out["ok"] and "'Pipeline' (2 tabs: Pipeline, Notes): 4 rows." in out["summary"]
    assert out["data"]["summary"]["columns"][2]["sum"] == 3000.5 and out["data"]["rows"] == PIPELINE
    assert apps.asked == [("1AbCdEfGhIjKlMnOpQrStUvWxYz0123456789", None)]


@pytest.mark.parametrize("apps, url, said", [
    (Apps(None), URL, "isn't connected"),
    (Apps(error="Google Sheets refused it (403)"), URL, "refused it"),
    (Apps(None), "https://example.com/x", "isn't a Google Sheets link"),
])
async def test_a_sheet_that_cant_be_read_says_why(store, settings, apps, url, said):
    out = await _run(_tools(store, settings, apps)["read_sheet"], url=url)
    assert not out["ok"] and said in out["error"]


async def test_an_export_is_a_proposal_with_a_preview(store, settings):
    store.targets = [AccountSummary(id=f"a{i}", name=f"Farm {i}", account_type="customer", geo="Nakuru")
                     for i in range(7)]
    out = await _run(_tools(store, settings, Apps())["export_to_sheet"], what="accounts")
    [card] = out["data"]["ui"]
    assert card["title"] == "Export 7 accounts to Google Sheets"
    assert card["preview"].startswith("7 accounts to a new spreadsheet, “Acme: accounts”:\nName | Type")
    assert card["preview"].endswith("…and 2 more")
    [proposal] = store.proposed
    assert (proposal.app, proposal.action, proposal.arguments["spreadsheet_id"], len(proposal.arguments["rows"])) == (
        "googlesheets", "export", None, 7)
    assert proposal.arguments["rows"][0][:4] == ["Farm 0", "customer", "", "Nakuru"]


async def test_nothing_to_export_proposes_nothing(store, settings):
    out = await _run(_tools(store, settings, Apps())["export_to_sheet"], what="contacts")
    assert not out["ok"] and "no saved contacts" in out["error"] and store.proposed == []
