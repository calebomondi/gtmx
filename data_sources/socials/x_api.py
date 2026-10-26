"""X API v2 records, as Composio returns them, in the reading shape of
`data_sources.socials.read`, so a read from X's own API and one from Bright Data
look the same to the Lace."""

from datetime import UTC, datetime
from urllib.parse import urlparse

# The fields asked for with each lookup.
USER_FIELDS = ["description", "public_metrics", "verified", "location", "url", "created_at"]
POST_FIELDS = ["created_at", "public_metrics", "author_id", "entities", "lang"]
POST_EXPANSIONS = ["author_id"]


def key(url: str, kind: str) -> str:
    """What X's API looks the link up by: the handle of a profile
    (x.com/<handle>), the id of a post (x.com/<handle>/status/<id>)."""
    parts = [p for p in urlparse(url).path.split("/") if p]
    return parts[2] if kind == "post" else parts[0]


def _data(record: dict) -> dict:
    """The record itself: Composio may or may not wrap the API's `data`."""
    inner = record.get("data") if isinstance(record.get("data"), dict) else record
    return inner if isinstance(inner, dict) else {}


def profile(record: dict, url: str) -> dict:
    user = _data(record)
    metrics = user.get("public_metrics") or {}
    return {
        "platform": "x", "kind": "profile", "url": url,
        "name": user.get("name"), "handle": user.get("username"), "bio": user.get("description"),
        "followers": metrics.get("followers_count"), "following": metrics.get("following_count"),
        "posts_count": metrics.get("tweet_count"), "verified": bool(user.get("verified")),
        "location": user.get("location"), "website": user.get("url"), "joined": user.get("created_at"),
        "details": {}, "fetched_at": datetime.now(UTC).isoformat(),
    }


def post(record: dict, url: str) -> dict:
    tweet = _data(record)
    metrics = tweet.get("public_metrics") or {}
    users = ((record.get("includes") or (record.get("data") or {}).get("includes") or {}).get("users")) or []
    author = next((u for u in users if u.get("id") == tweet.get("author_id")), {})
    hashtags = [h.get("tag") for h in (tweet.get("entities") or {}).get("hashtags") or [] if h.get("tag")]
    return {
        "platform": "x", "kind": "post", "url": url,
        "author": author.get("name") or author.get("username"),
        "author_url": f"https://x.com/{author['username']}" if author.get("username") else None,
        "text": tweet.get("text") or "", "date": tweet.get("created_at"),
        "likes": metrics.get("like_count"), "comments_count": metrics.get("reply_count"),
        "shares": metrics.get("retweet_count"), "views": metrics.get("impression_count"),
        "hashtags": hashtags or None, "top_comments": [],
        "details": {"quotes": metrics.get("quote_count"), "language": tweet.get("lang")},
        "fetched_at": datetime.now(UTC).isoformat(),
    }
