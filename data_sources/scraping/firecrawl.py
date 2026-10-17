"""Firecrawl: read a site page by page, as markdown.

Exa is the search engine; Firecrawl is how a Lace reads its founder's own site.
`map_site` lists the site's URLs so the caller can choose the pages that
matter (home, product, pricing, about, customers), and `scrape_pages` reads
them in one batch. A whole-site crawl would pay for blog archives and legal
pages nobody needs.

Failures raise `FirecrawlError` rather than returning empty values, so a caller
can tell "the site has nothing" from "the call failed".
"""

from dataclasses import dataclass
from functools import lru_cache

from firecrawl import Firecrawl
from firecrawl.v2.types import Document

from config import Settings
from data_sources.scraping.quality import is_usable_body, rejection_reason
from utils import usage
from utils.log import logger

# The SDK retries on its own; one retry is enough to ride out a blip without
# multiplying the caller's wait.
_SDK_RETRIES = 1


class FirecrawlError(RuntimeError):
    pass


@dataclass(frozen=True)
class SiteLink:
    url: str
    title: str = ""
    description: str = ""


@dataclass(frozen=True)
class Page:
    url: str
    title: str
    markdown: str


@dataclass(frozen=True)
class PageFailure:
    url: str
    reason: str


@lru_cache(maxsize=4)
def _client(api_key: str, timeout_s: float) -> Firecrawl:
    if not api_key:
        raise FirecrawlError("FIRECRAWL_API_KEY is not set")
    return Firecrawl(api_key=api_key, timeout=timeout_s, max_retries=_SDK_RETRIES)


def _norm(url: str) -> str:
    return url.lower().split("://", 1)[-1].removeprefix("www.").rstrip("/")


def _page_from(doc: Document, requested_url: str) -> Page | PageFailure:
    meta = doc.metadata
    url = (meta.source_url or meta.url if meta else None) or requested_url
    status = meta.status_code if meta else None
    if status is not None and not (200 <= status < 300 or status == 304):
        return PageFailure(url, (meta.error if meta else None) or f"HTTP {status}")
    if not is_usable_body(doc.markdown):
        return PageFailure(url, rejection_reason(doc.markdown))
    return Page(url=url, title=(meta.title if meta else None) or "", markdown=doc.markdown or "")


def map_site(url: str, config: Settings, limit: int = 100, search: str | None = None) -> list[SiteLink]:
    """The site's URLs, most relevant first when `search` is given."""
    client = _client(config.firecrawl_api_key, config.firecrawl_timeout_s)
    try:
        with usage.track("firecrawl", "map"):
            result = client.map(url, limit=limit, search=search, sitemap="include")
    except Exception as exc:
        raise FirecrawlError(f"map failed for {url}: {exc}") from exc
    links = [SiteLink(l.url, l.title or "", l.description or "") for l in result.links or [] if l.url]
    logger.info("Firecrawl map of %s returned %d links", url, len(links))
    return links


def scrape_page(url: str, config: Settings) -> Page:
    """One page as markdown. Raises when the page is unreachable or empty."""
    client = _client(config.firecrawl_api_key, config.firecrawl_timeout_s)
    try:
        with usage.track("firecrawl", "scrape"):
            doc = client.scrape(url, formats=["markdown"], only_main_content=True)
    except Exception as exc:
        raise FirecrawlError(f"scrape failed for {url}: {exc}") from exc
    page = _page_from(doc, url)
    if isinstance(page, PageFailure):
        raise FirecrawlError(f"{page.url}: {page.reason}")
    return page


def scrape_pages(urls: list[str], config: Settings) -> tuple[list[Page], list[PageFailure]]:
    """Several pages in one batch, waiting at most `firecrawl_batch_timeout_s`.

    Pages that fail come back as failures alongside the ones that worked; only
    a failure of the whole batch raises.
    """
    if not urls:
        return [], []
    client = _client(config.firecrawl_api_key, config.firecrawl_timeout_s)
    try:
        # One record per batch, billed per page: left unpriced rather than
        # reported at one page's price.
        with usage.track("firecrawl", "batch_scrape"):
            job = client.batch_scrape(
                urls,
                formats=["markdown"],
                only_main_content=True,
                wait_timeout=int(config.firecrawl_batch_timeout_s),
            )
    except Exception as exc:
        raise FirecrawlError(f"batch scrape failed: {exc}") from exc

    pages: list[Page] = []
    failures: list[PageFailure] = []
    for doc in job.data or []:
        result = _page_from(doc, "")
        (failures if isinstance(result, PageFailure) else pages).append(result)
    if len(job.data or []) < len(urls):
        # Returned URLs can differ from requested ones by a redirect, so the
        # missing pages are only guessed at when the batch came back short.
        returned = {_norm(p.url) for p in pages} | {_norm(f.url) for f in failures}
        failures += [PageFailure(u, "not returned by the batch") for u in urls if _norm(u) not in returned]
    logger.info("Firecrawl batch of %d: %d pages, %d failed (status %s)",
                len(urls), len(pages), len(failures), job.status)
    return pages, failures
