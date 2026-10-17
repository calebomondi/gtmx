"""The Lace's tools: typed results, failures reported not raised, store scoping."""

import json

import pytest

from agents.lace import tools as lace_tools
from agents.lace.tools import BATCH_PAGE_TOKEN_CAP, PAGE_TOKEN_CAP, build_tools
from agents.context_budget import count_tokens
from data_sources.scraping.firecrawl import FirecrawlError, Page, PageFailure
from lace_fakes import MemoryStore, make_fact


def _tools(store, settings):
    return {t.name: t for t in build_tools(store, settings)}


async def _run(tool, **args) -> dict:
    return json.loads(await tool.ainvoke(args))


async def test_read_page_saves_the_whole_page_but_returns_a_capped_one(monkeypatch, store, settings):
    long = "Acme payroll for clinics. " * 4000
    monkeypatch.setattr(lace_tools.firecrawl, "scrape_page",
                        lambda url, cfg: Page(url=url, title="Home", markdown=long))
    out = await _run(_tools(store, settings)["read_page"], url="https://acme.test")
    assert out["ok"] and "truncated" in out["summary"]
    assert count_tokens(out["data"]["markdown"]) <= PAGE_TOKEN_CAP + 5
    assert store.sources["https://acme.test"].markdown == long


async def test_unreadable_page_is_a_failure_result(monkeypatch, store, settings):
    def down(url, cfg):
        raise FirecrawlError("https://acme.test: HTTP 503")
    monkeypatch.setattr(lace_tools.firecrawl, "scrape_page", down)
    out = await _run(_tools(store, settings)["read_page"], url="https://acme.test")
    assert out == {"ok": False, "summary": "https://acme.test: HTTP 503", "error": "https://acme.test: HTTP 503"}


async def test_unexpected_error_is_reported_and_logged(monkeypatch, store, settings, caplog):
    def bug(*a, **k):
        raise ZeroDivisionError
    monkeypatch.setattr(lace_tools.exa, "search_highlights", bug)
    out = await _run(_tools(store, settings)["search_web"], query="clinic payroll")
    assert not out["ok"] and "ZeroDivisionError" in out["error"]
    assert "Lace tool search_web failed" in caplog.text


async def test_read_pages_reports_each_failure_and_caps_each_page(monkeypatch, store, settings):
    monkeypatch.setattr(lace_tools.firecrawl, "scrape_pages", lambda urls, cfg: (
        [Page(url=urls[0], title="Pricing", markdown="Plans from $20. " * 2000)],
        [PageFailure(urls[1], "HTTP 404")],
    ))
    out = await _run(_tools(store, settings)["read_pages"], urls=["https://acme.test/pricing", "https://acme.test/x"])
    assert out["ok"] and out["summary"] == "Read 1 of 2 pages."
    page, failure = out["data"]
    assert page["truncated"] and count_tokens(page["markdown"]) <= BATCH_PAGE_TOKEN_CAP + 5
    assert failure == {"url": "https://acme.test/x", "error": "HTTP 404"}


async def test_read_pages_refuses_an_oversized_batch(store, settings):
    out = await _run(_tools(store, settings)["read_pages"], urls=[f"https://acme.test/{i}" for i in range(9)])
    assert not out["ok"] and "At most 8" in out["error"]


async def test_search_trims_highlights(monkeypatch, store, settings):
    monkeypatch.setattr(lace_tools.exa, "search_highlights", lambda q, cfg, **kw: [
        {"url": "https://a.test", "title": "A", "highlights": ["1", "2", "3", "4"], "published_date": None}])
    out = await _run(_tools(store, settings)["search_web"], query="clinic payroll", depth="fast")
    assert out["data"][0]["highlights"] == ["1", "2", "3"]


async def test_record_fact_needs_a_source_unless_the_founder_said_it(store, settings):
    record = _tools(store, settings)["record_fact"]
    refused = await _run(record, topic="pricing", claim="Plans start at $20 a month.")
    assert not refused["ok"] and "source_url" in refused["error"]

    saved = await _run(record, topic="pricing", claim="Plans start at $20 a month.", from_founder=True)
    assert saved["ok"]
    [fact] = await store.facts()
    assert fact.origin == "user" and fact.source_url is None


async def test_record_fact_supersedes_without_deleting(settings):
    store = MemoryStore([make_fact("f1", "Plans start at $15.", topic="pricing")])
    out = await _run(_tools(store, settings)["record_fact"], topic="pricing", claim="Plans start at $20.",
                     source_url="https://acme.test/pricing", replaces_id="f1")
    assert out["ok"]
    assert [f.claim for f in await store.facts()] == ["Plans start at $20."]
    assert "f1" in store.superseded


async def test_record_fact_cannot_replace_an_unknown_fact(store, settings):
    out = await _run(_tools(store, settings)["record_fact"], topic="offer", claim="x",
                     source_url="https://acme.test", replaces_id="someone-elses")
    assert not out["ok"] and "someone-elses" in out["error"]


@pytest.mark.parametrize("topic, expected", [(None, 2), ("pricing", 1)])
async def test_get_facts_filters_by_topic(settings, topic, expected):
    store = MemoryStore([make_fact("f1", "a", topic="pricing"), make_fact("f2", "b", topic="offer")])
    out = await _run(_tools(store, settings)["get_facts"], **({"topic": topic} if topic else {}))
    assert len(out["data"]) == expected


def test_tool_schemas_describe_their_arguments(store, settings):
    for t in build_tools(store, settings):
        assert t.description
        for name, prop in t.args.items():
            assert prop.get("description"), f"{t.name}.{name} has no description"
