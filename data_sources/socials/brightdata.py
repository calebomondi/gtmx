"""Shared Bright Data Scraper API client for the socials modules."""

import threading
from functools import lru_cache

from brightdata import SyncBrightDataClient

from config import Settings, get_settings
from utils import usage
from utils.log import logger


class SocialsError(Exception):
    """A scrape that failed (no key, the scraper errored or timed out), as
    opposed to one that ran and found nothing."""


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


def fetch_record(
    platform: str,
    method: str,
    url: str,
    config: Settings | None = None,
    timeout_s: float | None = None,
) -> dict | None:
    """Run one Bright Data scraper method and return the first record, or None
    when it found nothing (a missing, private or dead page). Raises
    SocialsError when the scrape itself failed. Without `timeout_s` the SDK's
    own wait applies (180 s)."""
    cfg = config or get_settings()
    if not cfg.brightdata_api_key:
        raise SocialsError("Bright Data is not configured (no API key).")
    try:
        service = getattr(_client(cfg.brightdata_api_key, threading.get_ident()).scrape, platform)
        scraper = getattr(service, method)
    except AttributeError:
        raise SocialsError(f"Unknown Bright Data endpoint {platform}.{method}.") from None
    kwargs = {"timeout": int(timeout_s)} if timeout_s else {}
    try:
        with usage.track("brightdata", f"{platform}.{method}"):
            results = scraper(url=url, **kwargs)
    except Exception as exc:  # noqa: BLE001 -- the SDK raises many types; all mean the scrape failed
        raise SocialsError(f"the {platform} scraper failed ({type(exc).__name__}: {exc})") from exc
    if getattr(results, "success", True) is False:
        status = getattr(results, "status", None) or "error"
        raise SocialsError(f"the {platform} scraper stopped ({status}: {results.error or 'no detail'})")
    if isinstance(results, (list, dict)):
        record = results
    else:
        record = getattr(results, "data", None) or getattr(results, "result", None)
    if isinstance(record, list):
        record = record[0] if record else None
    if not isinstance(record, dict):
        logger.info("Bright Data %s.%s returned no record for %s", platform, method, url)
        return None
    # A missing or dead page comes back as a record carrying only the error.
    if record.get("error"):
        logger.info("Bright Data %s.%s: %s for %s", platform, method, record.get("error_code") or record["error"], url)
        return None
    return record


def scrape_resource(
    platform: str,
    method: str,
    url: str,
    config: Settings | None = None,
) -> dict | None:
    """`fetch_record` for the background pipelines: a failed scrape is logged
    and read as no data, so a single scraper outage does not sink an agent run."""
    try:
        return fetch_record(platform, method, url, config)
    except SocialsError as exc:
        logger.warning("Bright Data %s.%s skipped for %s: %s", platform, method, url, exc)
        return None
