"""Shared Bright Data Scraper API client for the socials modules."""

import threading
from functools import lru_cache

from brightdata import SyncBrightDataClient

from config import Settings, get_settings
from utils import usage
from utils.log import logger


@lru_cache(maxsize=32)
def _client(token: str, thread_id: int) -> SyncBrightDataClient:
    client = SyncBrightDataClient(token=token, auto_create_zones=False, validate_token=False)
    client.__enter__()
    return client


def get_client(config: Settings | None = None) -> SyncBrightDataClient | None:
    cfg = config or get_settings()
    if not cfg.brightdata_api_key:
        return None
    return _client(cfg.brightdata_api_key, threading.get_ident())


def scrape_resource(
    platform: str,
    method: str,
    url: str,
    config: Settings | None = None,
) -> dict | None:
    """Run one Bright Data scraper method and return the first result, or None.

    Every social module funnels through this. Failures are surfaced in the logs
    and swallowed so a single scraper outage does not sink an agent run.
    """
    cfg = config or get_settings()
    if not cfg.brightdata_api_key:
        logger.warning("Bright Data API key missing; skipping %s.%s for %s", platform, method, url)
        return None
    try:
        service = getattr(_client(cfg.brightdata_api_key, threading.get_ident()).scrape, platform)
        scraper = getattr(service, method)
    except AttributeError:
        logger.error("Unknown Bright Data endpoint %s.%s", platform, method)
        return None
    try:
        with usage.track("brightdata", f"{platform}.{method}"):
            results = scraper(url=url)
    except Exception as exc:
        logger.warning("Bright Data %s.%s failed for %s: %s", platform, method, url, exc)
        return None
    if isinstance(results, (list, dict)):
        record = results
    else:
        record = getattr(results, "data", None) or getattr(results, "result", None)
    if isinstance(record, list):
        record = record[0] if record else None
    if not isinstance(record, dict):
        logger.warning("Bright Data %s.%s returned no structured record for %s", platform, method, url)
        return None
    # A missing or dead page comes back as a record carrying only the error.
    if record.get("error"):
        logger.info("Bright Data %s.%s: %s for %s", platform, method, record.get("error_code") or record["error"], url)
        return None
    return record
