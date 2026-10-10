"""Competitor socials: handles come only from the company's own links, every
platform normalizes to one shape, and a failed scrape keeps the last good
profile."""

from agents.pipelines.monitor import socials
from data_sources.socials import profiles

_PAGE = """
<a href="https://twitter.com/intent/tweet?text=hi">share</a>
<a href="https://netflix.com/watch">customer</a>
<a href="https://x.com/someinvestor">quote</a>
<a href="https://x.com/AcmeHQ">X</a><a href="https://x.com/AcmeHQ">X</a>
<a href="https://www.linkedin.com/company/acme-inc/">in</a>
<a href="https://www.instagram.com/p/Cabc123/">post</a>
<a href="https://www.tiktok.com/@acme.app">tt</a>
"""


def test_find_on_page_ignores_share_links_and_lookalike_domains():
    assert profiles.find_on_page(_PAGE, "Acme") == {
        "x": "https://x.com/AcmeHQ",
        "linkedin": "https://www.linkedin.com/company/acme-inc",
        "tiktok": "https://www.tiktok.com/@acme.app",
    }


def test_profile_url_from_handle_or_url():
    assert profiles.profile_url("x", "@acme") == "https://x.com/acme"
    assert profiles.profile_url("instagram", "https://instagram.com/acme.co/") == "https://www.instagram.com/acme.co"
    assert profiles.profile_url("x", "https://x.com/intent/tweet") is None


def test_normalize_hidden_counts_are_null_and_posts_newest_first():
    raw = {"profile_name": "Acme", "followers": "0", "posts_count": "1,204", "is_verified": "True",
           "posts": [{"description": "old", "post_url": "u1", "date_posted": "2026-01-01", "likes": 3},
                     {"description": "new", "post_url": "u2", "date_posted": "2026-10-01", "likes": 9}]}
    profile = profiles.normalize("x", raw, "https://x.com/acme")
    assert profile["followers"] is None and profile["posts_count"] == 1204 and profile["verified"]
    assert [p["text"] for p in profile["recent_posts"]] == ["new", "old"]


def test_refresh_skips_low_confidence_and_keeps_last_good_profile(monkeypatch):
    monkeypatch.setattr(profiles, "find_on_site", lambda website, name: {"linkedin": "https://www.linkedin.com/company/acme"})
    scraped = []

    def fake_fetch(platform, url, config=None):
        scraped.append(platform)
        return None if platform == "x" else {"platform": platform, "url": url, "followers": 10}
    monkeypatch.setattr(profiles, "fetch", fake_fetch)
    tracking = [{"kind": "x", "value": "@acme", "confidence": "high"},
                {"kind": "instagram", "value": "@maybe_acme", "confidence": "low"}]
    previous = {"x": {"platform": "x", "url": "https://x.com/acme", "followers": 7}}

    result, found = socials.refresh("Acme", "https://acme.example", tracking, previous)
    assert sorted(scraped) == ["linkedin", "x"]  # the low-confidence handle is never scraped
    assert result["x"]["followers"] == 7 and result["linkedin"]["followers"] == 10
    assert found == {"linkedin": "https://www.linkedin.com/company/acme"}
