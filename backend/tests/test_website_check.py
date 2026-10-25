"""A new Lace's website is opened before the Lace is made; one that can't be
read is refused with a plain reason, and nothing is created."""

import time

import psycopg

from backend.app.services import website_check
from backend.app.services.website_check import readable
from backend.tests.test_laces_api import API, _create, lace_runtime  # noqa: F401 -- fixture
from config import settings
from data_sources.scraping import firecrawl
from data_sources.scraping.firecrawl import FirecrawlError


def test_an_unreadable_site_is_refused_and_nothing_is_made(client, lace_runtime, monkeypatch):  # noqa: F811
    async def unreadable(website):
        return False
    monkeypatch.setattr(website_check, "readable", unreadable)
    refused = _create(client, website="https://www.nowhere.test/about")
    assert refused.status_code == 422
    assert refused.json()["detail"] == ("We couldn't open nowhere.test. Check that the website address is right, "
                                        "then try again.")
    with psycopg.connect(settings.database_url) as conn:
        assert conn.execute("SELECT count(*) FROM laces").fetchone()[0] == 0


async def test_a_site_that_fails_or_hangs_is_not_readable(monkeypatch):
    def fails(url, config):
        raise FirecrawlError("scrape failed: DNS")
    monkeypatch.setattr(firecrawl, "scrape_page", fails)
    assert await readable("https://nowhere.test") is False

    def hangs(url, config):
        time.sleep(0.5)
    monkeypatch.setattr(firecrawl, "scrape_page", hangs)
    monkeypatch.setattr(settings, "website_check_timeout_s", 0.05)
    assert await readable("https://slow.test") is False

    monkeypatch.setattr(firecrawl, "scrape_page", lambda url, config: object())
    assert await readable("https://acme.test") is True
