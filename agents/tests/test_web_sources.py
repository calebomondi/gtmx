"""The Firecrawl and Exa-highlights adapters the Lace reads the web through.
Lives with the agents tests because agents are their only callers."""

from types import SimpleNamespace

import pytest
from firecrawl.v2.types import BatchScrapeJob, Document, DocumentMetadata, LinkResult, MapData

from config import get_settings
from data_sources.scraping import exa, firecrawl
from data_sources.scraping.firecrawl import FirecrawlError

BODY = "Acme builds payroll software for small clinics in Nairobi. " * 20


def _doc(url: str, markdown: str = BODY, status: int = 200) -> Document:
    return Document(markdown=markdown, metadata=DocumentMetadata(source_url=url, status_code=status, title="T"))


class FakeFirecrawl:
    def __init__(self, docs=(), links=(), fail=False):
        self.docs, self.links, self.fail = list(docs), list(links), fail

    def scrape(self, url, **kw):
        if self.fail:
            raise ConnectionError("boom")
        return self.docs[0]

    def start_batch_scrape(self, urls, **kw):
        self.urls, self.polls = urls, 0
        return SimpleNamespace(id="batch-1")

    def get_batch_scrape_status(self, job_id):
        # Running on the first check, done on the second.
        self.polls += 1
        if self.polls == 1:
            return BatchScrapeJob(status="scraping", completed=0, total=len(self.urls), data=[])
        return BatchScrapeJob(status="completed", completed=len(self.docs), total=len(self.urls), data=self.docs)

    def map(self, url, **kw):
        return MapData(links=self.links)


@pytest.fixture
def cfg():
    return get_settings().model_copy(update={"firecrawl_api_key": "fc-test"})


def _use(monkeypatch, fake):
    monkeypatch.setattr(firecrawl, "_client", lambda key, timeout: fake)
    monkeypatch.setattr(firecrawl, "_BATCH_POLL_S", 0)


def test_missing_key_is_an_error_not_an_empty_result():
    cfg = get_settings().model_copy(update={"firecrawl_api_key": ""})
    firecrawl._client.cache_clear()
    with pytest.raises(FirecrawlError, match="FIRECRAWL_API_KEY"):
        firecrawl.scrape_page("https://acme.test", cfg)


def test_scrape_page_returns_markdown(monkeypatch, cfg):
    _use(monkeypatch, FakeFirecrawl([_doc("https://acme.test/")]))
    page = firecrawl.scrape_page("https://acme.test", cfg)
    assert page.url == "https://acme.test/" and "payroll" in page.markdown


@pytest.mark.parametrize("doc, reason", [
    (_doc("https://acme.test", status=404), "404"),
    (_doc("https://acme.test", markdown="Coming soon"), "too short"),
])
def test_scrape_page_rejects_dead_or_placeholder_pages(monkeypatch, cfg, doc, reason):
    _use(monkeypatch, FakeFirecrawl([doc]))
    with pytest.raises(FirecrawlError, match=reason):
        firecrawl.scrape_page("https://acme.test", cfg)


def test_scrape_page_wraps_sdk_failures(monkeypatch, cfg):
    _use(monkeypatch, FakeFirecrawl(fail=True))
    with pytest.raises(FirecrawlError, match="boom"):
        firecrawl.scrape_page("https://acme.test", cfg)


def test_batch_separates_pages_from_failures(monkeypatch, cfg):
    _use(monkeypatch, FakeFirecrawl([_doc("https://acme.test/"), _doc("https://acme.test/x", status=500)]))
    pages, failures = firecrawl.scrape_pages(["https://acme.test", "https://acme.test/x"], cfg)
    assert [p.url for p in pages] == ["https://acme.test/"]
    assert [f.url for f in failures] == ["https://acme.test/x"]


def test_batch_reports_progress_as_it_runs(monkeypatch, cfg):
    _use(monkeypatch, FakeFirecrawl([_doc("https://acme.test/"), _doc("https://acme.test/x")]))
    seen = []
    firecrawl.scrape_pages(["https://acme.test", "https://acme.test/x"], cfg, on_progress=lambda d, t: seen.append((d, t)))
    assert seen == [(0, 2), (2, 2)]


def test_short_batch_reports_the_missing_page_but_not_a_redirected_one(monkeypatch, cfg):
    # /pricing came back as https://www.acme.test/pricing/; /about never came back.
    _use(monkeypatch, FakeFirecrawl([_doc("https://www.acme.test/pricing/")]))
    pages, failures = firecrawl.scrape_pages(["https://acme.test/pricing", "https://acme.test/about"], cfg)
    assert len(pages) == 1
    assert [f.url for f in failures] == ["https://acme.test/about"]


def test_map_site_drops_links_without_urls(monkeypatch, cfg):
    _use(monkeypatch, FakeFirecrawl(links=[LinkResult(url="https://acme.test/pricing", title="Pricing"),
                                           LinkResult(url="")]))
    links = firecrawl.map_site("https://acme.test", cfg)
    assert [(l.url, l.title) for l in links] == [("https://acme.test/pricing", "Pricing")]


def test_search_highlights_shapes_results(monkeypatch):
    seen = {}

    class FakeExa:
        def search(self, query, **kw):
            seen.update(kw)
            return SimpleNamespace(results=[
                SimpleNamespace(url="https://a.test", title="A", highlights=["payroll"], published_date="2026-09-01"),
                SimpleNamespace(url="", title="no url", highlights=[], published_date=None),
            ])

    monkeypatch.setattr(exa, "_client", lambda key: FakeExa())
    out = exa.search_highlights("clinic payroll kenya", get_settings(), search_type="fast")
    assert out == [{"url": "https://a.test", "title": "A", "highlights": ["payroll"], "published_date": "2026-09-01"}]
    assert seen["type"] == "fast" and seen["contents"] == {"highlights": True}
