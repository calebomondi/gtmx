"""Opportunities: searched per kind, kept only when sourced and still open,
as their own page states: an event, tender or grant needs a date after today."""

import json
from datetime import date

from agents.lace.opportunities import QUERIES_PER_KIND, RECENCY_DAYS, find_opportunities
from agents.lace.tools import build_tools
from agents.schemas.lace import LaceProfile
from agents.schemas.opportunities import Opportunity, OpportunityDates, OpportunityList, OpportunityPlan, OpportunityQuery
from config import get_settings
from lace_fakes import MemoryStore, RecordingJobs, make_fact

PROFILE = LaceProfile(name="Ada", website="https://shangalabs.com", startup_name="Shanga Labs")
TODAY = date(2026, 10, 19)
PAGES = {"https://expo.test/2026": "Agritech Expo Nairobi 2026", "https://tenders.test/iot": "IoT sensors tender"}


def _o(url, kind="showcase", deadline=None, when=None, title="X"):
    return Opportunity(kind=kind, title=title, url=url, deadline=deadline, date=when, why_it_fits="Fits.",
                       how_to_act="Apply.")


def _run(extracted, kinds=("showcase", "sell", "partner"), queries=None, pages=None, dates=None):
    """`pages` are the opportunity pages that read (url -> text); `dates` what
    the check finds on each (url -> OpportunityDates, or an exception)."""
    seen = {"queries": [], "read": [], "checked": []}

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

    def read(urls, cfg):
        seen["read"] = list(urls)
        return dict(pages or {})

    def check(messages):
        url = next(u for u, text in (pages or {}).items() if text in messages[-1].content)
        seen["checked"].append(url)
        answer = (dates or {})[url]
        if isinstance(answer, Exception):
            raise answer
        return answer

    found = find_opportunities(PROFILE, [make_fact("1", "Shanga Labs builds rugged IoT hardware.")], None,
                               get_settings(), kinds, TODAY, plan=plan, extract=extract, search=search,
                               read=read, check=check)
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


def test_a_page_that_says_applications_closed_is_dropped():
    # Latitude59 Kenya: the final is in December, but applications closed in October.
    url = "https://expo.test/2026"
    found, seen = _run([_o(url, when="2026-12-04")], pages={url: "Applications closed 2 October."},
                       dates={url: OpportunityDates(deadline="2026-10-02", date="2026-12-04", open=False,
                                                    note="applications closed")})
    assert found == [] and seen["read"] == [url] and seen["checked"] == [url]


def test_the_page_dates_replace_the_snippets():
    url = "https://expo.test/2026"
    found, _ = _run([_o(url)], pages={url: "Exhibitor applications close 15 November."},
                    dates={url: OpportunityDates(deadline="2026-11-15", date="2026-11-20", open=True)})
    assert [(o.deadline, o.date) for o in found] == [("2026-11-15", "2026-11-20")]


def test_a_past_date_on_the_page_drops_it_even_if_the_model_says_open():
    # Africa Blockchain Festival: held 15-17 October, before today.
    url = "https://expo.test/2026"
    found, _ = _run([_o(url)], pages={url: "15-17 October 2026, Nairobi."},
                    dates={url: OpportunityDates(date="2026-10-15", open=True)})
    assert found == []


def test_an_event_with_no_date_anywhere_is_dropped_but_a_partner_is_kept():
    found, _ = _run([_o("https://expo.test/2026"), _o("https://tenders.test/iot", kind="partner")])
    assert [o.url for o in found] == ["https://tenders.test/iot"]


def test_a_tender_or_grant_needs_a_deadline_not_just_an_event_date():
    # Latitude59 Kenya's general page gives the December final but no closing date.
    found, _ = _run([_o("https://expo.test/2026", kind="sell", when="2026-12-03"),
                     _o("https://tenders.test/iot", kind="sell", deadline="2026-11-30")])
    assert [o.url for o in found] == ["https://tenders.test/iot"]


def test_an_unreadable_page_or_failed_check_keeps_what_the_search_said():
    expo, tender = "https://expo.test/2026", "https://tenders.test/iot"
    found, seen = _run([_o(expo, when="2026-11-20"), _o(tender, kind="sell", deadline="2026-11-30")],
                       pages={tender: "Bids due 30 November."}, dates={tender: RuntimeError("model down")})
    assert [o.url for o in found] == [expo, tender]
    assert seen["checked"] == [tender]
