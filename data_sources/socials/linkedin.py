"""LinkedIn capabilities via Bright Data."""

from typing import Optional

from config import Settings
from data_sources.socials.brightdata import scrape_resource


def get_company(url: str, config: Optional[Settings] = None) -> dict | None:
    return scrape_resource("linkedin", "companies", url, config)


def get_profile(url: str, config: Optional[Settings] = None) -> dict | None:
    return scrape_resource("linkedin", "profiles", url, config)
