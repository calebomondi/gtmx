"""Onboarding: the right pages are read, facts must cite them, and a dead site
is reported rather than papered over."""

import re

from agents.lace import onboarding
from agents.lace.onboarding import candidates, onboard, pick_pages
from agents.schemas.lace import ExtractedFact, PagePick, SiteUnderstanding
from data_sources.scraping.firecrawl import FirecrawlError, Page, PageFailure, SiteLink
from lace_fakes import MemoryStore

SITE = [SiteLink(u, t) for u, t in [
    ("https://acme.test/", "Acme"), ("https://www.acme.test/pricing", "Pricing"),
    ("https://acme.test/blog/launch-day", "Launch"), ("https://acme.test/about", "About"),
    ("https://acme.test/privacy", "Privacy"), ("https://acme.test/products/payroll", "Payroll"),
    ("https://acme.test/customers", "Customers"), ("https://other.test/pricing", "Other"),
    ("https://acme.test/logo.png", ""), ("https://acme.test/docs/api/v2/auth", "Auth"),
    ("https://acme.test/clinic-os", "Clinic OS: the operating system for clinics"),
    ("https://acme.test/a/b/c", "Too deep"),
]]
CANDIDATES = {"https://www.acme.test/pricing", "https://acme.test/about", "https://acme.test/products/payroll",
              "https://acme.test/customers", "https://acme.test/clinic-os"}


def _never(messages):
    raise AssertionError("the picker should not be called")


def test_candidates_are_same_site_shallow_and_not_skipped():
    assert {l.url for l in candidates("acme.test", SITE)} == CANDIDATES


def test_few_candidates_are_all_read_without_a_model_call():
    assert pick_pages("acme.test", SITE, pick=_never) == ["https://acme.test", *sorted(
        CANDIDATES, key=[l.url for l in candidates("acme.test", SITE)].index)]


def test_the_model_picks_when_there_are_too_many_and_cannot_add_pages():
    seen = {}

    def pick(messages):
        seen["listing"] = messages[1].content
        return PagePick(urls=["https://acme.test/clinic-os", "https://evil.test/x", "https://acme.test/clinic-os"])

    picked = pick_pages("acme.test", SITE, pick=pick, limit=3)
    assert picked == ["https://acme.test", "https://acme.test/clinic-os"]
    assert "https://acme.test/clinic-os | Clinic OS" in seen["listing"]


def test_keyword_ranking_when_the_pick_fails():
    def broken(messages):
        raise RuntimeError("provider down")

    # A nested product page ranks below top-level pricing and about.
    assert pick_pages("acme.test", SITE, pick=broken, limit=3) == [
        "https://acme.test", "https://www.acme.test/pricing", "https://acme.test/about"]


def _fake_site(monkeypatch, pages, failures=(), map_fails=False):
    def map_site(url, cfg, limit, search=None):
        if map_fails:
            raise FirecrawlError("map down")
        return list(SITE)

    read = {}

    def scrape_pages(urls, cfg, on_progress=None):
        read["urls"] = urls
        if on_progress:
            on_progress(len(urls), len(urls))
        return list(pages), list(failures)

    monkeypatch.setattr(onboarding.firecrawl, "map_site", map_site)
    monkeypatch.setattr(onboarding.firecrawl, "scrape_pages", scrape_pages)
    return read


async def test_onboard_records_cited_facts_and_the_startup_name(monkeypatch, settings):
    home = Page(url="https://acme.test/", title="Acme", markdown="Acme: payroll for clinics. " * 50)
    pricing = Page(url="https://acme.test/pricing", title="Pricing", markdown="From $20 a month. " * 50)
    _fake_site(monkeypatch, [home, pricing], [PageFailure("https://acme.test/about", "HTTP 500")])
    seen = {}

    def extract(messages):
        seen["prompt"] = messages[1].content
        return SiteUnderstanding(startup_name="Acme Health", open_questions=["a", "b", "c", "d"], facts=[
            ExtractedFact(topic="offer", claim="Acme sells payroll software to clinics.",
                          source_url="https://acme.test/", confidence="high"),
            ExtractedFact(topic="pricing", claim="Plans start at $20 a month.",
                          source_url="https://acme.test/pricing", confidence="high"),
            ExtractedFact(topic="customers", claim="Used by 500 clinics.",
                          source_url="https://acme.test/testimonials", confidence="high"),  # never read
        ])

    store = MemoryStore()
    result = await onboard(store, settings, extract=extract, pick=_never)

    assert result.facts_recorded == 2 and result.startup_name == "Acme Health"
    assert result.pages_failed == ["https://acme.test/about"]
    assert result.open_questions == ["a", "b", "c"]
    facts = await store.facts()
    assert {f.claim for f in facts} == {"Acme sells payroll software to clinics.", "Plans start at $20 a month."}
    assert all(f.origin == "crawl" for f in facts)
    assert store.startup_name == "Acme Health"
    assert set(store.sources) == {"https://acme.test/", "https://acme.test/pricing"}
    assert '<page url="https://acme.test/pricing"' in seen["prompt"]


async def test_onboard_reports_its_progress_in_order(monkeypatch, settings):
    _fake_site(monkeypatch, [Page(url="https://acme.test/", title="Acme", markdown="x " * 500)])
    seen: list[tuple[float, str]] = []
    await onboard(MemoryStore(), settings, extract=lambda m: SiteUnderstanding(startup_name="Acme"), pick=_never,
                  progress=lambda fraction, text: seen.append((fraction, text)))
    fractions = [f for f, _ in seen]
    assert fractions == sorted(fractions) and fractions[-1] == onboarding.UNDERSTOOD
    texts = [t for _, t in seen]
    assert texts[:2] == ["Mapping your site", "Choosing the pages to read"] and texts[3] == "Learning what you sell"
    assert re.fullmatch(r"Read (\d+) of \1 pages", texts[2])


async def test_onboard_reads_the_homepage_when_the_map_fails(monkeypatch, settings):
    read = _fake_site(monkeypatch, [Page(url="https://acme.test", title="", markdown="x " * 500)], map_fails=True)
    await onboard(MemoryStore(), settings, extract=lambda m: SiteUnderstanding(startup_name="Acme"), pick=_never)
    assert read["urls"] == ["https://acme.test"]


async def test_unreadable_site_records_nothing_and_says_so(monkeypatch, settings):
    _fake_site(monkeypatch, [], [PageFailure("https://acme.test", "HTTP 503")])

    def extract(messages):
        raise AssertionError("nothing to extract from")

    store = MemoryStore()
    result = await onboard(store, settings, extract=extract, pick=_never)
    assert result.site_unreadable and result.facts_recorded == 0
    assert await store.facts() == []


def test_opening_message_asks_the_open_questions_or_for_a_description():
    from agents.lace.onboarding import opening_message
    from agents.schemas.lace import OnboardingResult
    seen = []
    write = lambda messages: (seen.append(messages[1].content), " Hi! ")[1]
    read = OnboardingResult(startup_name="Acme", pages_read=["https://acme.test"], pages_failed=[],
                            facts_recorded=3, open_questions=["Who buys?"])
    assert opening_message("sys", read, write) == "Hi!"
    assert "- Who buys?" in seen[0]
    dead = OnboardingResult(startup_name=None, pages_read=[], pages_failed=["https://acme.test"],
                            facts_recorded=0, open_questions=[])
    opening_message("sys", dead, write)
    assert "could not" in seen[1] and "https://acme.test" in seen[1]
