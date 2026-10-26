"""The Lace's CRM tools: the pipeline summed up in code, lookups, and a lead
as a proposal the founder approves."""

import json
from datetime import date

import pytest

from agents.lace.crm import summarise_deals
from agents.lace.tools import build_tools

TODAY = date(2026, 10, 24)
DEALS = [
    {"name": "Alpha", "stage": "Proposal", "amount": 1000.0, "close_date": "2026-10-30", "updated": "2026-10-20",
     "closed": False, "won": False},
    {"name": "Beta", "stage": "Proposal", "amount": 500.5, "close_date": "2026-10-01", "updated": "2026-08-01T09:00:00Z",
     "closed": False, "won": False},
    {"name": "Gamma", "stage": "Closed Won", "amount": 2000.0, "closed": True, "won": True},
    {"name": "Delta", "stage": "Closed Lost", "amount": None, "closed": True, "won": False},
]


class Apps:
    def __init__(self, crm="zoho", deals=None, found=None):
        self.which, self.deals, self.found = crm, deals, found

    async def crm(self):
        return self.which

    async def crm_deals(self):
        return self.deals

    async def crm_find(self, query):
        return self.found


def _tools(store, settings, apps):
    return {t.name: t for t in build_tools(store, settings, apps=apps)}


async def _run(tool, **args) -> dict:
    return json.loads(await tool.ainvoke(args))


def test_the_pipeline_is_summed_in_code():
    s = summarise_deals(DEALS, TODAY)
    assert (s["deals"], s["open"], s["won"], s["lost"]) == (4, {"count": 2, "value": 1500.5},
                                                            {"count": 1, "value": 2000.0}, 1)
    assert s["by_stage"]["Proposal"] == {"count": 2, "value": 1500.5}
    assert s["stale"] == {"count": 1, "days": 30, "names": ["Beta"]}
    assert s["closing_soon"] == [{"name": "Beta", "close_date": "2026-10-01", "overdue": True},
                                 {"name": "Alpha", "close_date": "2026-10-30", "overdue": False}]


async def test_the_pipeline_tool_says_the_totals(store, settings):
    out = await _run(_tools(store, settings, Apps(deals=DEALS))["crm_pipeline"])
    assert out["ok"] and out["summary"].startswith("4 deals: 2 open worth 1,500.50, 1 won, 1 lost")


async def test_without_a_crm_it_says_so(store, settings):
    tools = _tools(store, settings, Apps(crm=None))
    for name, args in [("crm_pipeline", {}), ("crm_lookup", {"query": "Acme"}),
                       ("add_lead_to_crm", {"name": "Joe Kamau", "company": "Acme"})]:
        out = await _run(tools[name], **args)
        assert not out["ok"] and "No CRM is connected" in out["error"], name


async def test_a_lead_is_a_proposal_for_the_lace_s_crm(store, settings):
    out = await _run(_tools(store, settings, Apps(crm="zoho"))["add_lead_to_crm"], name="Joe Kamau",
                     company="Acme Farms", email="joe@acme.test", title="COO", note="Asked for a demo.")
    [card] = out["data"]["ui"]
    assert (card["title"], card["preview"]) == ("Add Joe Kamau to Zoho CRM",
                                                "Joe Kamau, COO at Acme Farms\njoe@acme.test\nAsked for a demo.")
    assert (store.proposed[0].app, store.proposed[0].action) == ("zoho", "add_lead")


@pytest.mark.parametrize("found, said", [([], "Nobody in the CRM"), ([{"kind": "lead", "name": "Joe"}], "1 matches")])
async def test_lookup(store, settings, found, said):
    out = await _run(_tools(store, settings, Apps(found=found))["crm_lookup"], query="Joe")
    assert out["ok"] and said in out["summary"]
