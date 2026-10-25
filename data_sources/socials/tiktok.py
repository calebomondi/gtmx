"""TikTok capabilities via Bright Data."""

from typing import Optional

from config import Settings
from data_sources.socials.brightdata import fetch_record, fetch_records, parse_count, scrape_resource


def get_profile(url: str, config: Optional[Settings] = None) -> dict | None:
    return scrape_resource("tiktok", "profiles", url, config)


def recent_videos(handle: str, config: Settings, timeout_s: float) -> list[dict]:
    """An account's recent public videos as its profile lists them, newest
    first: [{url, text, date, views, likes, comments, shares}]. Raises
    SocialsError when the scrape fails. (Bright Data's videos-by-profile
    scraper rejects its own input, so the profile's list is read instead.)"""
    profile = fetch_record("tiktok", "profiles", f"https://www.tiktok.com/@{handle}", config, timeout_s) or {}
    captions = {str(p.get("post_id") or p.get("id") or ""): p.get("description")
                for p in profile.get("top_posts_data") or [] if isinstance(p, dict)}
    videos = [{"url": v.get("video_url"), "text": (captions.get(str(v.get("video_id"))) or "")[:280],
               "date": v.get("create_date"), "views": parse_count(v.get("playcount")),
               "likes": parse_count(v.get("diggcount")), "comments": parse_count(v.get("commentcount")),
               "shares": parse_count(v.get("share_count"))}
              for v in profile.get("top_videos") or [] if isinstance(v, dict) and v.get("video_url")]
    return sorted(videos, key=lambda v: str(v["date"] or ""), reverse=True)


def video_comments(url: str, config: Settings, timeout_s: float) -> list[dict]:
    """A public video's comments: [{author, text, date, likes}]. Raises
    SocialsError when the scrape fails or runs past `timeout_s`."""
    return [{"author": c.get("commenter_user_name") or c.get("commenter_id"),
             "text": (c.get("comment_text") or c.get("text") or "")[:300],
             "date": c.get("date_created") or c.get("create_time"), "likes": parse_count(c.get("num_likes"))}
            for c in fetch_records("tiktok", "comments", url, config, timeout_s)
            if (c.get("comment_text") or c.get("text"))]
