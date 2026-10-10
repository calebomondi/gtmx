"""Shared Bright Data Scraper API client for the socials modules."""

import threading
from functools import lru_cache
from typing import Optional

from brightdata import SyncBrightDataClient

from config import Config
from utils.log import logger


@lru_cache(maxsize=32)
def _client(token: str, thread_id: int) -> SyncBrightDataClient:
    client = SyncBrightDataClient(token=token, auto_create_zones=False, validate_token=False)
    client.__enter__()
    return client


def get_client(config: Config | None = None) -> SyncBrightDataClient | None:
    cfg = config or Config()
    if not cfg.brightdata_api_key:
        return None
    return _client(cfg.brightdata_api_key, threading.get_ident())


def scrape_resource(
    platform: str,
    method: str,
    url: str,
    config: Config | None = None,
) -> dict | None:
    """Run one Bright Data scraper method and return the first result, or None.

    Every social module funnels through this. Failures are surfaced in the logs
    and swallowed so a single scraper outage does not sink an agent run.
    """
    cfg = config or Config()
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
        results = scraper(url=url)
    except Exception as exc:
        logger.warning("Bright Data %s.%s failed for %s: %s", platform, method, url, exc)
        return None
    if isinstance(results, list):
        return results[0] if results else None
    if isinstance(results, dict):
        return results
    data = getattr(results, "data", None) or getattr(results, "result", None)
    if isinstance(data, list):
        return data[0] if data else None
    if isinstance(data, dict):
        return data
    logger.warning("Bright Data %s.%s returned no structured record for %s", platform, method, url)
    return None
