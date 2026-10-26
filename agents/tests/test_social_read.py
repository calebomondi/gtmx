"""Reading one social link: which scraper reads it, failures told apart from
nothing found, and every kind normalized to the shape the Lace reads."""

from types import SimpleNamespace

import pytest

from config import get_settings
from data_sources.socials import brightdata, read
from data_sources.socials.brightdata import SocialsError
from data_sources.socials.read import SocialLink, classify, normalize


@pytest.mark.parametrize("url, platform, kind, method", [
    ("https://www.instagram.com/acme.clinics", "instagram", "profile", "profiles"),
    ("instagram.com/acme.clinics/", "instagram", "profile", "profiles"),
    ("https://www.instagram.com/p/AbC123", "instagram", "post", "posts"),
    ("https://www.instagram.com/reel/AbC123/", "instagram", "post", "reels"),
    ("https://www.linkedin.com/in/jane-doe", "linkedin", "person", "profiles"),
    ("https://ke.linkedin.com/in/jane-doe?trk=x", "linkedin", "person", "profiles"),
    ("https://www.linkedin.com/company/acme", "linkedin", "company", "companies"),
    ("https://www.linkedin.com/posts/acme_launch-activity-1234-abcd", "linkedin", "post", "posts"),
    ("https://www.linkedin.com/feed/update/urn:li:activity:1234", "linkedin", "post", "posts"),
    ("https://x.com/acme", "x", "profile", "profiles"),
    ("https://twitter.com/acme/status/1234", "x", "post", "posts"),
    ("https://www.tiktok.com/@acme", "tiktok", "profile", "profiles"),
    ("https://www.tiktok.com/@acme/video/1234", "tiktok", "post", "posts"),
    ("https://www.facebook.com/acme/posts/pfbid0abc", "facebook", "post", "posts_by_url"),
    ("https://www.facebook.com/share/p/1AbC/", "facebook", "post", "posts_by_url"),
    ("https://www.facebook.com/reel/1234", "facebook", "post", "reels"),
])
def test_classify_picks_the_scraper(url, platform, kind, method):
    link = classify(url)
    assert link is not None
    assert (link.platform, link.kind, link.method) == (platform, kind, method)


@pytest.mark.parametrize("url", [
    "https://www.facebook.com/acme",  # a page: no scraper reads it
    "https://www.instagram.com/explore/tags/clinics",
    "https://www.linkedin.com/jobs/view/1234",
    "https://x.com/search?q=clinics",
    "https://acme.test/about",
    "https://www.tiktok.com/discover",
    "",
])
def test_classify_refuses_links_no_scraper_reads(url):
    assert classify(url) is None


def test_post_reads_text_engagement_and_top_comments_and_drops_media():
    raw = {"url": "https://www.instagram.com/p/AbC", "user_posted": "acme.clinics", "description": "Open in Nakuru",
           "date_posted": "2026-10-05T14:17:45Z", "likes": 17, "num_comments": "2",
           "photos": ["https://cdn.test/1.jpg"], "thumbnail": "https://cdn.test/t.jpg", "pk": "999",
           "latest_comments": [{"user_commenting": "kim", "comments": "Congrats!", "date_of_comment": "2026-10-06",
                                "likes": 1, "profile_picture": "https://cdn.test/kim.jpg"}],
           "content_type": "Carousel", "input": {"url": "x"}}
    out = normalize(SocialLink("instagram", "post", "posts", raw["url"]), raw)
    assert out["kind"] == "post" and out["author"] == "acme.clinics" and out["text"] == "Open in Nakuru"
    assert (out["likes"], out["comments_count"]) == (17, 2)
    assert out["top_comments"] == [{"author": "kim", "text": "Congrats!", "date": "2026-10-06", "likes": 1}]
    assert out["details"] == {"content_type": "Carousel"}  # media, bookkeeping and main fields left out


def test_linkedin_person_reads_headline_company_and_activity():
    raw = {"name": "Jane Doe", "position": "Head of Ops", "city": "Nairobi", "about": "Runs clinics.",
           "current_company": {"name": "Acme Clinics", "link": "https://linkedin.com/company/acme"},
           "followers": "1,041", "connections": "500", "experience": None,
           "education": [{"title": "University of Nairobi", "start_year": "2015"}],
           "people_also_viewed": [{"name": "Someone Else"}],
           "activity": [{"title": "We opened in Nakuru", "link": "https://linkedin.com/posts/1", "interaction": "Posted",
                         "img": "https://cdn.test/a.jpg"}]}
    out = normalize(SocialLink("linkedin", "person", "profiles", "https://linkedin.com/in/jane"), raw)
    assert (out["name"], out["headline"], out["current_company"]) == ("Jane Doe", "Head of Ops", "Acme Clinics")
    assert (out["followers"], out["connections"]) == (1041, 500)
    assert out["recent_activity"] == [{"text": "We opened in Nakuru", "url": "https://linkedin.com/posts/1",
                                       "interaction": "Posted"}]
    assert out["details"] == {"education": [{"title": "University of Nairobi", "start_year": "2015"}]}


def test_profile_reuses_the_company_profile_shape():
    raw = {"full_name": "Acme Clinics", "followers": "308", "posts_count": "9", "biography": "Clinics in Kenya",
           "is_verified": "False", "posts": [{"caption": "Hello", "url": "https://instagram.com/p/1",
                                              "datetime": "2026-10-01"}]}
    out = normalize(SocialLink("instagram", "profile", "profiles", "https://instagram.com/acme"), raw)
    assert (out["name"], out["followers"], out["bio"]) == ("Acme Clinics", 308, "Clinics in Kenya")
    assert out["recent_posts"][0]["text"] == "Hello" and out["url"] == "https://instagram.com/acme"
    assert out["details"] == {}  # every field was read into the main ones


def test_details_stay_bounded():
    raw = {"description": "x", "about": "y" * 5000, "items": [{"n": i} for i in range(50)],
           **{f"k{i}": i + 1 for i in range(100)}}
    details = normalize(SocialLink("x", "post", "posts", "https://x.com/a/status/1"), raw)["details"]
    assert len(details) <= 40
    assert len(details["about"]) <= 401 and len(details["items"]) == 5


# fetch_record: a failed scrape raises, nothing found is None.

def _scraper(monkeypatch, result):
    calls = []

    def scrape(**kwargs):
        calls.append(kwargs)
        if isinstance(result, Exception):
            raise result
        return result
    client = SimpleNamespace(scrape=SimpleNamespace(instagram=SimpleNamespace(profiles=scrape)))
    monkeypatch.setattr(brightdata, "_client", lambda token, thread: client)
    return calls


@pytest.fixture
def cfg():
    return get_settings().model_copy(update={"brightdata_api_key": "bd-test"})


def test_fetch_record_passes_the_timeout_and_returns_the_record(monkeypatch, cfg):
    calls = _scraper(monkeypatch, SimpleNamespace(success=True, data=[{"account": "acme"}]))
    assert brightdata.fetch_record("instagram", "profiles", "https://instagram.com/acme", cfg, 90) == {"account": "acme"}
    assert calls == [{"url": "https://instagram.com/acme", "timeout": 90}]


def test_fetch_record_raises_on_a_timed_out_scrape(monkeypatch, cfg):
    _scraper(monkeypatch, SimpleNamespace(success=False, status="timeout", error="no snapshot after 90s", data=None))
    with pytest.raises(SocialsError, match="timeout"):
        brightdata.fetch_record("instagram", "profiles", "https://instagram.com/acme", cfg)


def test_fetch_record_raises_when_the_sdk_raises(monkeypatch, cfg):
    _scraper(monkeypatch, ConnectionError("reset"))
    with pytest.raises(SocialsError, match="ConnectionError"):
        brightdata.fetch_record("instagram", "profiles", "https://instagram.com/acme", cfg)


def test_fetch_record_raises_without_a_key():
    with pytest.raises(SocialsError, match="not configured"):
        brightdata.fetch_record("instagram", "profiles", "https://instagram.com/acme",
                                get_settings().model_copy(update={"brightdata_api_key": ""}))


def test_a_dead_page_is_nothing_found_not_a_failure(monkeypatch, cfg):
    _scraper(monkeypatch, SimpleNamespace(success=True, data=[{"error": "Page not found", "error_code": "dead_page"}]))
    assert brightdata.fetch_record("instagram", "profiles", "https://instagram.com/gone", cfg) is None


def test_scrape_resource_still_swallows_failures_for_the_pipelines(monkeypatch, cfg, caplog):
    _scraper(monkeypatch, ConnectionError("reset"))
    assert brightdata.scrape_resource("instagram", "profiles", "https://instagram.com/acme", cfg) is None
    assert "skipped" in caplog.text


def test_read_returns_none_when_nothing_was_found(monkeypatch, cfg):
    monkeypatch.setattr(read, "fetch_record", lambda *a: None)
    assert read.read(classify("https://instagram.com/gone"), cfg, 90) is None
