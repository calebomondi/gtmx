"""X (Twitter) capabilities via Bright Data."""

from typing import Optional

from config import Settings
from data_sources.socials.brightdata import fetch_records, parse_count, scrape_resource


def get_profile(url: str, config: Optional[Settings] = None) -> dict | None:
    return scrape_resource("x", "profiles", url, config)


def recent_posts(handle: str, config: Settings, timeout_s: float) -> list[dict]:
    """An account's recent public posts, newest first: [{url, text, date,
    views, likes, replies, reposts}]. Raises SocialsError when the scrape fails."""
    rows = fetch_records("x", "posts_by_profile", f"https://x.com/{handle}", config, timeout_s)
    posts = [{"url": r.get("url"), "text": (r.get("description") or "")[:280], "date": r.get("date_posted"),
              "views": parse_count(r.get("views")), "likes": parse_count(r.get("likes")),
              "replies": parse_count(r.get("replies")), "reposts": parse_count(r.get("reposts"))}
             for r in rows if not r.get("is_repost")]
    return sorted(posts, key=lambda p: p["date"] or "", reverse=True)
