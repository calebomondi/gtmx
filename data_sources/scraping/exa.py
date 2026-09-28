from exa_py import Exa

from config import Config
from utils.log import logger


def scrape_url(url: str, config: Config) -> str:
    """Extract clean text content from a URL via Exa.

    Returns all results concatenated. If a single URL returns multiple results
    (e.g. a page describing multiple products), all are included.
    """
    exa = Exa(api_key=config.exa_api_key)
    result = exa.get_contents([url], text=True)
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
    config: Config,
    num_results: int = 5,
    start_published_date: str | None = None,
) -> list[dict]:
    """Search the web and return results with full text content.

    `start_published_date` (ISO date string, e.g. "2025-09-09") narrows results
    to sources published after that date — used to keep market research current.
    """
    exa = Exa(api_key=config.exa_api_key)
    results = exa.search(
        query,
        contents={"text": True},
        num_results=num_results,
        start_published_date=start_published_date,
    )
    logger.info("Exa search for %r returned %d results", query, len(results.results))
    return [
        {"url": r.url, "title": r.title, "text": r.text}
        for r in results.results
    ]
