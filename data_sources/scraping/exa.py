from functools import lru_cache

from exa_py import Exa

from config import Settings
from data_sources.scraping.quality import (
    MIN_SEARCH_CHARS,
    is_usable_body,
    rejection_reason,
)
from utils.log import logger


@lru_cache(maxsize=4)
def _client(api_key: str) -> Exa:
    """One Exa client per key.

    The client is stateless over the wire and safe to share across threads; building
    a fresh one per call (as this module used to) meant re-initialising the HTTP
    stack on every single scrape.
    """
    return Exa(api_key=api_key)


def scrape_url(url: str, config: Settings) -> str:
    """Extract clean text content from a URL via Exa.

    `livecrawl="always"` is load-bearing. Exa serves `get_contents` from a cache, and
    a young or previously-placeholder site can have a stale snapshot pinned there: a
    live page then returns a dead-site body. Verified on https://shangalabs.com/ — the
    default call returned a 400-char "Coming Soon / under construction" parking page
    for a site with 5.7k chars of real content, while `livecrawl="always"` returned all
    4.6k of it. Cost is ~0.7s, which is nothing next to the LLM call this feeds.

    Returns all results concatenated. If a single URL returns multiple results
    (e.g. a page describing multiple products), all are included.
    """
    exa = _client(config.exa_api_key)
    result = exa.get_contents([url], text=True, livecrawl="always")
    if not result.results:
        raise ValueError(f"No content returned for URL: {url}")
    # Return all results concatenated, so multi-product pages are captured
    parts = []
    for i, r in enumerate(result.results):
        title = getattr(r, "title", "") or ""
        text = r.text or ""
        if len(result.results) > 1:
            parts.append(f"[Result {i+1}] Title: {title}\\n{text}")
        else:
            parts.append(text)
    return "\n\n".join(parts)


def search_and_scrape(
    query: str,
    config: Settings,
    num_results: int = 5,
    start_published_date: str | None = None,
) -> list[dict]:
    """Search the web and return results with full text content.

    `start_published_date` (ISO date string, e.g. "2025-09-09") narrows results
    to sources published after that date — used to keep market research current.
    """
    exa = _client(config.exa_api_key)
    results = exa.search(
        query,
        contents={"text": True},
        num_results=num_results,
        start_published_date=start_published_date,
    )

    # NOTE: deliberately NOT forcing `livecrawl` here, unlike scrape_url. Forcing
    # freshness changes result *composition*, not just freshness: with
    # livecrawl="always" the shangalabs.com homepage drops out of the ranking
    # entirely and is replaced by unrelated pages, because the ranking was built on
    # the stale cached copy. That is a recall regression in the research path, so
    # here we filter the poison out instead of re-ranking around it.
    #
    # This still matters: without it, search for a company's own name returns its
    # homepage as the top hit carrying "under construction", and the research stages
    # quote it as evidence about the company.
    kept: list[dict] = []
    for r in results.results:
        # MIN_SEARCH_CHARS, not the primary-page floor: search hits are snippets and
        # real ones are routinely short. We are screening out placeholders here, not
        # demanding essays.
        if not is_usable_body(r.text, min_chars=MIN_SEARCH_CHARS):
            logger.info(
                "Exa search for %r dropped %s (%s)",
                query, r.url, rejection_reason(r.text, min_chars=MIN_SEARCH_CHARS),
            )
            continue
        kept.append({"url": r.url, "title": r.title, "text": r.text})

    logger.info("Exa search for %r returned %d results, kept %d", query, len(results.results), len(kept))
    return kept
