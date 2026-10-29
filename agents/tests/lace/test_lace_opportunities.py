"""Opportunities: searched per kind, kept only when sourced and still open."""

import json
from datetime import date

from agents.lace.opportunities import QUERIES_PER_KIND, RECENCY_DAYS, find_opportunities
from agents.lace.tools import build_tools
from agents.schemas.lace import LaceProfile
from agents.schemas.opportunities import Opportunity, OpportunityList, OpportunityPlan, OpportunityQuery
from config import get_settings
from lace_fakes import MemoryStore, RecordingJobs, make_fact

PROFILE = LaceProfile(name="Ada", website="https://shangalabs.com", startup_name="Shanga Labs")
TODAY = date(2026, 10, 19)
PAGES = {"https://expo.test/2026": "Agritech Expo Nairobi 2026", "https://tenders.test/iot": "IoT sensors tender"}


def _o(url, kind="showcase", deadline=None, when=None, title="X"):
    return Opportunity(kind=kind, title=title, url=url, deadline=deadline, date=when, why_it_fits="Fits.",
                       how_to_act="Apply.")


def _run(extracted, kinds=("showcase", "sell", "partner"), queries=None):
    seen = {"queries": []}

    def plan(messages):
        seen["plan_prompt"] = messages[0].content
        return OpportunityPlan(queries=queries or [OpportunityQuery(kind="showcase", query="agritech expo 2026"),
                                                   OpportunityQuery(kind="sell", query="IoT tender Kenya 2026")])

    def search(query, cfg, since):
        seen["queries"].append(query)
        seen["since"] = since
        return [{"url": url, "title": title, "highlights": ["..."]} for url, title in PAGES.items()]

    def extract(messages):
        seen["extract_prompt"] = messages[0].content
        return OpportunityList(opportunities=extracted)

    found = find_opportunities(PROFILE, [make_fact("1", "Shanga Labs builds rugged IoT hardware.")], None,
                               get_settings(), kinds, TODAY, plan=plan, extract=extract, search=search)
    return found, seen


def test_only_sourced_open_opportunities_are_kept():
    found, seen = _run([
        _o("https://expo.test/2026", when="2026-11-20"),
        _o("https://tenders.test/iot", kind="sell", deadline="2026-10-01"),  # closed
        _o("https://made-up.test/award"),                                     # not a page that was found
        _o("https://expo.test/2026", when="2026-11-20", title="duplicate"),
    ])
    assert [(o.url, o.title) for o in found] == [("https://expo.test/2026", "X")]
    assert "https://tenders.test/iot" in seen["extract_prompt"] and "rugged IoT" in seen["plan_prompt"]


def test_searches_are_recent_and_capped_per_kind():
    many = [OpportunityQuery(kind="showcase", query=f"q{i}") for i in range(QUERIES_PER_KIND + 3)]
    _, seen = _run([], kinds=("showcase",), queries=many + [OpportunityQuery(kind="sell", query="not asked for")])
    assert seen["queries"] == [f"q{i}" for i in range(QUERIES_PER_KIND)]
    assert date.fromisoformat(seen["since"]) == TODAY.fromordinal(TODAY.toordinal() - RECENCY_DAYS)


def test_nothing_found_means_nothing_reported():
    def search(query, cfg, since):
        return []

    def extract(messages):
        raise AssertionError("nothing to extract from")

    found = find_opportunities(PROFILE, [], None, get_settings(), ("showcase",), TODAY,
                               plan=lambda m: OpportunityPlan(queries=[OpportunityQuery(kind="showcase", query="q")]),
                               extract=extract, search=search)
    assert found == []


async def test_find_opportunities_tool_starts_a_job(settings):
    jobs = RecordingJobs()
    tool = {t.name: t for t in build_tools(MemoryStore(), settings, jobs)}["find_opportunities"]
    assert json.loads(await tool.ainvoke({"kinds": ["sell"]}))["ok"]
    assert json.loads(await tool.ainvoke({}))["ok"]
    assert jobs.started == [("find_opportunities", {"kinds": ["sell"]}),
                            ("find_opportunities", {"kinds": ["showcase", "sell", "partner", "funding"]})]


def test_funding_is_searched_for_what_the_startup_qualifies_for():
    grant = "https://grants.test/iot-2026"
    PAGES[grant] = "IoT hardware grant: call for applications"
    try:
        found, seen = _run([_o(grant, kind="funding", deadline="2026-12-01", title="IoT hardware grant")],
                           kinds=("funding",), queries=[OpportunityQuery(kind="funding", query="IoT grant Kenya 2026")])
    finally:
        del PAGES[grant]
    assert [(o.kind, o.title) for o in found] == [("funding", "IoT hardware grant")]
    # Searches name the sector, stage and country; the extraction keeps only
    # a current call the startup meets, and says what it meets.
    assert "grants, incubators, accelerators" in seen["plan_prompt"] and "sector, its stage and its country" in seen["plan_prompt"]
    assert "states who can apply and the startup meets it" in seen["extract_prompt"]
    assert "evergreen" in seen["extract_prompt"]
