"""Read one social link (a person, a company or a post) through Bright Data.

`classify` says what a link is and which scraper reads it; `read` runs that
scraper and returns one shape per kind: the fields an agent reasons with
first, then `details`, the rest of the record with media links and scraper
bookkeeping removed and long values shortened, so nothing useful is lost but
the size stays bounded. Company and handle profiles reuse `profiles.normalize`.
"""

import re
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Literal
from urllib.parse import urlparse

from config import Settings
from data_sources.socials import profiles
from data_sources.socials.brightdata import fetch_record

Platform = Literal["instagram", "linkedin", "x", "tiktok", "facebook"]
Kind = Literal["person", "company", "profile", "post"]

SUPPORTED = ("Instagram profiles, posts and reels; LinkedIn people, companies and posts; X profiles and posts; "
             "TikTok profiles and videos; Facebook posts.")

_HOSTS: dict[str, Platform] = {
    "instagram.com": "instagram", "linkedin.com": "linkedin", "x.com": "x", "twitter.com": "x",
    "tiktok.com": "tiktok", "facebook.com": "facebook", "fb.com": "facebook",
}
# First path segments that are site pages, not someone's handle.
_RESERVED = {"explore", "accounts", "about", "legal", "privacy", "help", "home", "search", "hashtag", "i",
             "intent", "share", "settings", "login", "signup", "messages", "notifications", "stories", "direct"}
_FB_POST = re.compile(r"/(posts|permalink\.php|photo|photo\.php|videos|watch|story\.php|share/[prv])(/|$|\?)", re.I)

# Limits on `details`.
_DETAIL_KEYS = 40
_DETAIL_CHARS = 400
_DETAIL_ITEMS = 5
_DETAIL_DEPTH = 3
_TEXT_CHARS = 3_000
_COMMENTS = 5
_ACTIVITY = 5
# Record keys that are media, markup or scraper bookkeeping: never useful to read.
_NOISE = re.compile(r"(image|photo|video|thumbnail|avatar|(^|_)pic(_|$)|picture|banner|logo|audio|_html|^input$|^timestamp$"
                    r"|^pk$|^fbid$|^partner_id$|_num_id$|^content_id$|^shortcode$|^post_content$|^original_post_text$)",
                    re.I)


@dataclass(frozen=True)
class SocialLink:
    platform: Platform
    kind: Kind
    method: str  # the Bright Data scraper method that reads it
    url: str


def classify(url: str) -> SocialLink | None:
    """What a social link is, or None for one that no scraper reads (a
    Facebook page, a search page, another site)."""
    url = (url or "").strip()
    if not re.match(r"^https?://", url, re.I):
        url = "https://" + url
    parsed = urlparse(url)
    host = (parsed.hostname or "").lower()
    platform = next((p for h, p in _HOSTS.items() if host == h or host.endswith("." + h)), None)
    parts = [p for p in parsed.path.split("/") if p]
    if platform is None or (not parts and platform != "facebook"):
        return None
    head = parts[0].lower()
    if platform == "instagram":
        if head in ("p", "tv") and len(parts) > 1:
            return SocialLink(platform, "post", "posts", url)
        if head in ("reel", "reels") and len(parts) > 1:
            return SocialLink(platform, "post", "reels", url)
        return SocialLink(platform, "profile", "profiles", url) if len(parts) == 1 and head not in _RESERVED else None
    if platform == "linkedin":
        if head == "in" and len(parts) > 1:
            return SocialLink(platform, "person", "profiles", url)
        if head in ("company", "school", "showcase") and len(parts) > 1:
            return SocialLink(platform, "company", "companies", url)
        if head in ("posts", "pulse") or parts[:2] == ["feed", "update"]:
            return SocialLink(platform, "post", "posts", url)
        return None
    if platform == "x":
        if len(parts) >= 3 and parts[1].lower() == "status":
            return SocialLink(platform, "post", "posts", url)
        return SocialLink(platform, "profile", "profiles", url) if len(parts) == 1 and head not in _RESERVED else None
    if platform == "tiktok":
        if head.startswith("@") and len(parts) >= 3 and parts[1].lower() == "video":
            return SocialLink(platform, "post", "posts", url)
        return SocialLink(platform, "profile", "profiles", url) if len(parts) == 1 and head.startswith("@") else None
    # Facebook: only posts and reels; Bright Data has no page or profile scraper.
    if head in ("reel", "reels") and len(parts) > 1:
        return SocialLink(platform, "post", "reels", url)
    return SocialLink(platform, "post", "posts_by_url", url) if _FB_POST.search(parsed.path + "?" + parsed.query) else None


def _first(raw: dict, *keys: str):
    for key in keys:
        value = raw.get(key)
        if value not in (None, "", [], {}, "None", "null"):
            return value
    return None


def _count(raw: dict, *keys: str) -> int | None:
    return profiles.parse_count(_first(raw, *keys))


def _short(value, depth: int = 0):
    """`value` with long text cut, lists shortened and noisy keys dropped;
    None when nothing worth reading is left."""
    if isinstance(value, dict):
        if depth >= _DETAIL_DEPTH:
            return None
        out = {}
        for key, item in value.items():
            if _NOISE.search(key):
                continue
            item = _short(item, depth + 1)
            if item is not None:
                out[key] = item
            if len(out) >= _DETAIL_KEYS:
                break
        return out or None
    if isinstance(value, list):
        items = [s for s in (_short(v, depth + 1) for v in value[:_DETAIL_ITEMS]) if s is not None]
        return items or None
    if value in (None, "", "None", "null"):
        return None
    if isinstance(value, str) and len(value) > _DETAIL_CHARS:
        return value[:_DETAIL_CHARS] + "…"
    return value


# Where each platform's scraper puts a field, in the order tried.
_C_AUTHOR = ("user_name", "user_commenting", "commenter_name", "user_id", "author")
_C_TEXT = ("comments", "comment", "text", "comment_text")
_C_DATE = ("date_of_comment", "date", "comment_date", "date_created")
_C_LIKES = ("likes", "num_reactions", "likes_number", "num_likes")
_P_AUTHOR = ("user_name", "user_posted", "profile_username", "page_name", "account", "user_id")
_P_AUTHOR_URL = ("profile_url", "use_url", "user_url", "page_url")
_P_TEXT = ("post_text", "description", "caption", "content", "text", "headline")
_P_DATE = ("date_posted", "create_time", "datetime", "date")
_P_LIKES = ("likes", "num_likes", "digg_count", "likes_count")
_P_COMMENTS = ("num_comments", "comment_count", "comments_count", "replies")
_P_SHARES = ("num_shares", "share_count", "reposts", "shares")
_P_VIEWS = ("views", "play_count", "video_view_count", "video_play_count")
_P_HASHTAGS = ("hashtags", "post_hashtags")
_P_TOP_COMMENTS = ("latest_comments", "top_visible_comments", "top_comments", "comments")
# The keys a reading's main fields come from, left out of its `details` so
# nothing is said twice; plus lists of other people, not about this one.
_USED = {
    "post": {"url", *_P_AUTHOR, *_P_AUTHOR_URL, *_P_TEXT, *_P_DATE, *_P_LIKES, *_P_COMMENTS, *_P_SHARES,
             *_P_VIEWS, *_P_HASHTAGS, *_P_TOP_COMMENTS},
    "person": {"url", "name", "first_name", "last_name", "position", "headline", "city", "location",
               "current_company", "current_company_name", "followers", "connections", "about", "activity",
               "people_also_viewed", "similar_profiles"},
}
# What profiles.normalize reads, across platforms.
_USED["profile"] = _USED["company"] = {
    "url", "name", "full_name", "profile_name", "nickname", "followers", "posts_count", "videos_count", "biography",
    "signature", "slogan", "about", "company_size", "likes", "is_verified", "posts", "updates", "top_posts_data"}


def _comment(raw: dict) -> dict:
    return {"author": _first(raw, *_C_AUTHOR), "text": str(_first(raw, *_C_TEXT) or "")[:_DETAIL_CHARS],
            "date": _first(raw, *_C_DATE), "likes": _count(raw, *_C_LIKES)}


def _post(raw: dict) -> dict:
    comments = _first(raw, *_P_TOP_COMMENTS) or []
    return {
        "author": _first(raw, *_P_AUTHOR),
        "author_url": _first(raw, *_P_AUTHOR_URL),
        "text": str(_first(raw, *_P_TEXT) or "")[:_TEXT_CHARS],
        "date": _first(raw, *_P_DATE),
        "likes": _count(raw, *_P_LIKES),
        "comments_count": _count(raw, *_P_COMMENTS),
        "shares": _count(raw, *_P_SHARES),
        "views": _count(raw, *_P_VIEWS),
        "hashtags": _first(raw, *_P_HASHTAGS),
        "top_comments": [_comment(c) for c in comments[:_COMMENTS] if isinstance(c, dict)],
    }


def _person(raw: dict) -> dict:
    company = raw.get("current_company") if isinstance(raw.get("current_company"), dict) else {}
    activity = raw.get("activity") or []
    return {
        "name": _first(raw, "name") or " ".join(filter(None, (raw.get("first_name"), raw.get("last_name")))) or None,
        "headline": _first(raw, "position", "headline"),
        "location": _first(raw, "city", "location"),
        "current_company": _first(company, "name") or _first(raw, "current_company_name"),
        "followers": _count(raw, "followers"),
        "connections": _count(raw, "connections"),
        "about": str(_first(raw, "about") or "")[:_TEXT_CHARS],
        "recent_activity": [{"text": (a.get("title") or "")[:_DETAIL_CHARS], "url": a.get("link"),
                             "interaction": a.get("interaction")}
                            for a in activity[:_ACTIVITY] if isinstance(a, dict)],
    }


def normalize(link: SocialLink, raw: dict) -> dict:
    """The reading of one record: its main fields, then `details`."""
    if link.kind == "post":
        main = _post(raw)
    elif link.kind == "person":
        main = _person(raw)
    else:
        main = profiles.normalize(link.platform, raw, link.url)
        for key in ("platform", "url", "fetched_at"):
            main.pop(key)
    used = _USED.get(link.kind, set())
    rest = {k: v for k, v in raw.items() if k not in used}
    return {"platform": link.platform, "kind": link.kind, "url": link.url, **main,
            "details": _short(rest) or {}, "fetched_at": datetime.now(UTC).isoformat()}


def read(link: SocialLink, config: Settings | None = None, timeout_s: float | None = None) -> dict | None:
    """The normalized record, or None when the scraper found nothing there.
    Raises SocialsError when the scrape failed."""
    raw = fetch_record(link.platform, link.method, link.url, config, timeout_s)
    return normalize(link, raw) if raw else None
