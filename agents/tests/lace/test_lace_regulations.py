"""Regulations: searched only where a founder confirmed the startup is
registered and operates, on official sources, and kept only when cited."""

import json
from datetime import date

from agents.lace.regulations import OFFICIAL_SITES, QUERIES_PER_PLACE, find_regulations, is_official
from agents.lace.tools import build_tools
from agents.schemas.lace import LaceProfile
from agents.schemas.regulations import Regulation, RegulationList, RegulationPlan, RegulationQuery, RegulationSummary
from config import get_settings
from data_sources.legislation.kenya_law import Bill
from lace_fakes import MemoryStore, RecordingJobs, make_fact

PROFILE = LaceProfile(name="Lace", website="https://thalace.com", startup_name="Thalace")
TODAY = date(2026, 10, 31)
ODPC = "https://www.odpc.go.ke/registration-of-data-controllers"
VAT_BILL = "https://kenyalaw.org/akn/ke/bill/na/2026-04-10/the-value-added-tax-amendment-bill-2026/eng@2026-04-10"
BLOG = "https://lawblog.test/kenya-data-protection"


def _r(url, kind="law", place="KE", title="X", stage=None):
    return Regulation(kind=kind, title=title, jurisdiction=place, url=url, stage=stage,
                      why_it_applies="It holds customer data.", what_to_do="Register.")


def _run(extracted, registered_in="KE", operates_in=("KE",), queries=None, hits=None):
    seen = {"searches": []}

    def plan(messages):
        seen["plan_prompt"] = messages[0].content
        return RegulationPlan(queries=queries or [RegulationQuery(jurisdiction="KE", query="Kenya data protection ODPC")])

    def search(query, cfg, sites):
        seen["searches"].append((query, sites))
        return hits if hits is not None else [{"url": u, "title": "page", "highlights": ["..."]} for u in (ODPC, BLOG)]

    def bills():
        seen["bills_read"] = True
        return [Bill(title="The Value Added Tax (Amendment) Bill, 2026", url=VAT_BILL, chamber="National Assembly",
                     published=date(2026, 4, 10))]

    def extract(messages):
        seen["extract_prompt"] = messages[0].content
        return RegulationList(regulations=extracted)

    found = find_regulations(PROFILE, [make_fact("1", "Thalace sells an AI assistant to founding teams.")],
                             registered_in, list(operates_in), get_settings(), TODAY,
                             plan=plan, extract=extract, search=search, bills=bills)
    return found, seen


def test_only_cited_official_sources_in_the_places_are_kept():
    found, seen = _run([
        _r(ODPC, title="The Data Protection Act, 2019"),
        _r(VAT_BILL, kind="bill", title="The VAT (Amendment) Bill, 2026"),
        _r(BLOG),                                     # found, but not an official source
        _r("https://made-up.go.ke/act"),              # not a page that was read
        _r(ODPC, place="UG", title="Out of place"),   # not one of the places
        _r(ODPC, title="duplicate"),
    ])
    assert [(r.url, r.title) for r in found] == [(ODPC, "The Data Protection Act, 2019"),
                                                 (VAT_BILL, "The VAT (Amendment) Bill, 2026")]
    assert BLOG not in seen["extract_prompt"]
    assert "a bill before the National Assembly, published 2026-04-10" in seen["extract_prompt"]
    assert "AI assistant to founding teams" in seen["plan_prompt"] and "KE: registered here" in seen["plan_prompt"]


def test_only_a_bill_keeps_a_stage_and_only_from_a_page_that_states_it():
    tracker = "https://www.parliament.go.ke/bills/data-protection-amendment-2026"
    found, _ = _run([_r(ODPC, stage="committee"), _r(VAT_BILL, kind="bill", stage="first_reading"),
                     _r(tracker, kind="bill", stage="committee")],
                    hits=[{"url": u, "title": "page", "highlights": ["..."]} for u in (ODPC, tracker)])
    assert [(r.url, r.stage) for r in found] == [(ODPC, None), (VAT_BILL, None), (tracker, "committee")]


def test_searches_are_capped_per_place_and_kept_to_official_sites():
    many = [RegulationQuery(jurisdiction="KE", query=f"q{i}") for i in range(QUERIES_PER_PLACE + 2)]
    _, seen = _run([], queries=many + [RegulationQuery(jurisdiction="FR", query="not a place of ours")])
    assert seen["searches"] == [(f"q{i}", OFFICIAL_SITES["KE"]) for i in range(QUERIES_PER_PLACE)]


def test_kenyan_bills_are_read_only_when_kenya_is_a_place():
    _, seen = _run([], registered_in="US-DE", operates_in=("NG",),
                   queries=[RegulationQuery(jurisdiction="NG", query="Nigeria data protection NDPC")], hits=[])
    assert "bills_read" not in seen and seen["searches"] == [("Nigeria data protection NDPC", None)]


def test_no_places_means_no_search():
    def fail(*_):
        raise AssertionError("nothing should run")

    assert find_regulations(PROFILE, [], None, [], get_settings(), TODAY, plan=fail, extract=fail, search=fail,
                            bills=fail) == []


def test_official_sources():
    assert is_official(ODPC, "KE") and is_official(VAT_BILL, "KE") and is_official("https://cma.or.ke/x", "KE")
    assert is_official("https://www.gov.uk/vat-registration", "GB") and is_official("https://nitda.gov.ng/x", "NG")
    assert is_official("https://eur-lex.europa.eu/eli/reg/2016/679", "FR")
    assert not is_official(BLOG, "KE") and not is_official("https://kenyalaw.org.evil.test/x", "KE")
    assert not is_official("https://cma.or.ke/x", "NG")


def _tools(store, jobs=None):
    return {t.name: t for t in build_tools(store, get_settings(), jobs)}


async def _call(tool, args):
    return json.loads(await tool.ainvoke(args))


async def test_the_search_waits_for_a_confirmed_jurisdiction():
    store, jobs = MemoryStore(), RecordingJobs()
    tools = _tools(store, jobs)
    refused = await _call(tools["find_regulations"], {})
    assert not refused["ok"] and "set_jurisdiction" in refused["error"] and jobs.started == []

    recorded = await _call(tools["set_jurisdiction"], {"registered_in": "ke", "operates_in": ["KE", " ug "]})
    assert recorded["ok"] and store.place.places == ["KE", "UG"] and store.place.confirmed
    assert (await _call(tools["find_regulations"], {}))["ok"]
    assert jobs.started == [("find_regulations", {})]


async def test_a_jurisdiction_must_be_iso_codes():
    store = MemoryStore()
    bad = await _call(_tools(store)["set_jurisdiction"], {"registered_in": "Kenya", "operates_in": []})
    assert not bad["ok"] and "KENYA" in bad["error"] and not store.place.confirmed


async def test_the_search_needs_something_to_run_jobs():
    assert "find_regulations" not in _tools(MemoryStore())


async def test_regulations_are_listed_and_tracked_on_the_founders_word():
    store = MemoryStore()
    store.place = store.place.model_copy(update={"registered_in": "KE", "confirmed": True})
    store.rules = [RegulationSummary(**_r(ODPC, title="The Data Protection Act, 2019").model_dump(), id="r1",
                                     status="suggested")]
    tools = _tools(store)
    listed = await _call(tools["list_regulations"], {"status": "suggested"})
    assert [r["id"] for r in listed["data"]["regulations"]] == ["r1"] and "Jurisdiction: KE" in listed["summary"]

    tracked = await _call(tools["update_regulations"], {"ids": ["r1", "nope"], "verdict": "track"})
    assert tracked["ok"] and "No match for: nope" in tracked["summary"]
    assert [r.status for r in store.rules] == ["tracked"]
