"""TikTok capabilities via Bright Data."""

from typing import Optional

from config import Config
from data_sources.socials.brightdata import scrape_resource


def get_profile(url: str, config: Optional[Config] = None) -> dict | None:
    return scrape_resource("tiktok", "profiles", url, config)
