"""A stalled Exa call fails fast instead of hanging the run (its SDK has no
timeout). Lives with the agents tests because agents are its only callers."""

import threading
import time

import pytest

from config import get_settings
from data_sources.scraping import exa


def test_stalled_search_times_out(monkeypatch):
    release = threading.Event()

    class StalledClient:
        def search(self, *a, **k):
            release.wait(5)  # stands in for requests.post() that never returns
            return None

    monkeypatch.setattr(exa, "_client", lambda key: StalledClient())
    cfg = get_settings().model_copy(update={"exa_timeout_s": 0.2})
    started = time.monotonic()
    try:
        with pytest.raises(TimeoutError, match="timed out"):
            exa.search_and_scrape("anything", cfg)
    finally:
        release.set()
    assert time.monotonic() - started < 2
