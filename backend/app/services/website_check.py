"""Whether a startup's website can be read, checked before its Lace is made:
the same scraper its onboarding reads the site with, on the home page. A
site it can't open is refused with a plain reason, so no Lace starts out
knowing nothing."""

import asyncio

from data_sources.scraping import firecrawl
from data_sources.scraping.firecrawl import FirecrawlError
from config import settings
from utils.log import logger


async def readable(website: str) -> bool:
    """True when the site's home page reads as a page with something on it."""
    try:
        await asyncio.wait_for(asyncio.to_thread(firecrawl.scrape_page, website, settings),
                               settings.website_check_timeout_s)
    except (FirecrawlError, TimeoutError) as exc:
        logger.info("Website check: couldn't read %s: %s", website, exc)
        return False
    return True
