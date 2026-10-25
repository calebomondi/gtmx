"""A company's social profiles: handles read off its own homepage, stats
fetched through Bright Data, every platform normalized to one shape so the
backend and UI never read raw scraper records.

Handles come only from the company's own site (or ones the competitor agent
recorded), never from a name search: a search finds a same-named business
just as easily, and tracking the wrong company is worse than tracking none.
"""

import re
from collections import Counter
from datetime import UTC, datetime

import httpx

from config import Settings
from data_sources.socials import instagram, linkedin, tiktok, x
from data_sources.socials.brightdata import parse_count
from utils.log import logger

PLATFORMS = ("linkedin", "x", "instagram", "tiktok")

# Anchored on "//" so "netflix.com/..." can never read as an x.com link.
_LINK_RE = {
    "linkedin": re.compile(r"//(?:[a-z]{2,3}\.)?linkedin\.com/company/([A-Za-z0-9_%-]+)", re.I),
    "x": re.compile(r"//(?:www\.|mobile\.)?(?:twitter|x)\.com/([A-Za-z0-9_]{1,15})(?![A-Za-z0-9_])", re.I),
    "instagram": re.compile(r"//(?:www\.)?instagram\.com/([A-Za-z0-9_.]{1,30})", re.I),
    "tiktok": re.compile(r"//(?:www\.)?tiktok\.com/@([A-Za-z0-9_.]{1,24})", re.I),
}
_NOT_HANDLES = {"share", "sharer", "intent", "home", "i", "p", "reel", "reels", "explore",
                "accounts", "search", "hashtag", "login", "signup", "about", "legal"}
_PROFILE_URL = {
    "linkedin": "https://www.linkedin.com/company/{}",
    "x": "https://x.com/{}",
    "instagram": "https://www.instagram.com/{}",
    "tiktok": "https://www.tiktok.com/@{}",
}
_FETCH = {
    "linkedin": linkedin.get_company,
    "x": x.get_profile,
    "instagram": instagram.get_profile,
    "tiktok": tiktok.get_profile,
}
_HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                          "(KHTML, like Gecko) Chrome/129.0 Safari/537.36"}
_POSTS = 3
_POST_CHARS = 280


def _handle(platform: str, text: str) -> str | None:
    match = _LINK_RE[platform].search(text)
    return match.group(1) if match else None


def profile_handle(platform: str, value: str) -> str | None:
    """The handle in a profile URL or a bare handle ("@acme" or "acme"); None
    for anything else."""
    url = profile_url(platform, value)
    return _handle(platform, url) if url else None


def profile_url(platform: str, value: str) -> str | None:
    """A profile URL from a URL or a bare handle; None for share links etc."""
    value = (value or "").strip()
    handle = _handle(platform, value) if "/" in value else value.lstrip("@")
    if not handle or handle.lower() in _NOT_HANDLES or not re.fullmatch(r"[A-Za-z0-9_.%-]+", handle):
        return None
    return _PROFILE_URL[platform].format(handle)


def find_on_page(html: str, name: str) -> dict[str, str]:
    """{platform: profile URL} linked from a page. With several candidates the
    one resembling the company name wins, then the most linked."""
    key = re.sub(r"[^a-z0-9]", "", name.lower())
    found = {}
    for platform, pattern in _LINK_RE.items():
        handles = Counter(h for h in pattern.findall(html) if h.lower() not in _NOT_HANDLES)
        if not handles:
            continue
        best = max(handles, key=lambda h: (bool(key) and key[:5] in h.lower(), handles[h]))
        found[platform] = _PROFILE_URL[platform].format(best)
    return found


def find_on_site(website: str, name: str, timeout_s: float = 15) -> dict[str, str]:
    try:
        response = httpx.get(website, headers=_HEADERS, follow_redirects=True, timeout=timeout_s)
        response.raise_for_status()
    except httpx.HTTPError as exc:
        logger.info("Could not read socials off %s: %s", website, exc)
        return {}
    return find_on_page(response.text, name)


def _post(text, url, date, likes=None) -> dict:
    return {"text": (text or "")[:_POST_CHARS], "url": url, "date": date, "likes": parse_count(likes)}


def normalize(platform: str, raw: dict, url: str) -> dict:
    """One shape for every platform: name, followers, posts_count, verified,
    bio, recent_posts (newest first) plus platform extras."""
    if platform == "linkedin":
        profile = {"name": raw.get("name"), "followers": parse_count(raw.get("followers")),
                   "bio": raw.get("slogan") or (raw.get("about") or "")[:300],
                   "employees": raw.get("company_size"),
                   "posts": [_post(p.get("text"), p.get("post_url"), p.get("date"), p.get("likes_count"))
                             for p in raw.get("updates") or []]}
    elif platform == "x":
        profile = {"name": raw.get("profile_name"), "followers": parse_count(raw.get("followers")),
                   "posts_count": parse_count(raw.get("posts_count")), "bio": raw.get("biography"),
                   "posts": [_post(p.get("description"), p.get("post_url"), p.get("date_posted"), p.get("likes"))
                             for p in raw.get("posts") or []]}
    elif platform == "instagram":
        profile = {"name": raw.get("full_name") or raw.get("profile_name"), "followers": parse_count(raw.get("followers")),
                   "posts_count": parse_count(raw.get("posts_count")), "bio": raw.get("biography"),
                   "posts": [_post(p.get("caption"), p.get("url"), p.get("datetime"))
                             for p in raw.get("posts") or []]}
    else:  # tiktok
        profile = {"name": raw.get("nickname"), "followers": parse_count(raw.get("followers")),
                   "posts_count": parse_count(raw.get("videos_count")), "bio": raw.get("biography") or raw.get("signature"),
                   "likes": parse_count(raw.get("likes")),
                   "posts": [_post(p.get("description"), p.get("post_url"), p.get("create_time"), p.get("likes"))
                             for p in raw.get("top_posts_data") or []]}
    posts = sorted((p for p in profile.pop("posts") if p["text"] or p["url"]),
                   key=lambda p: p["date"] or "", reverse=True)
    return {
        "platform": platform, "url": url, **profile,
        "verified": str(raw.get("is_verified")).lower() == "true",
        "recent_posts": posts[:_POSTS],
        "fetched_at": datetime.now(UTC).isoformat(),
    }


def fetch(platform: str, url: str, config: Settings | None = None) -> dict | None:
    """The normalized profile, or None when the scrape failed or found nothing."""
    raw = _FETCH[platform](url, config)
    return normalize(platform, raw, url) if raw else None
