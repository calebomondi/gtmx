"""Discovery keeps only plausible targets: competitors the model judges are
not competitors are dropped, and accounts whose real headcount is above every
ICP size band are dropped (a size copied from the ICP is not evidence)."""

from types import SimpleNamespace

import pytest

from agents.pipelines.accounts.account_discovery import _headcount_range, _size_verdict
from agents.pipelines.competitors import get_competitors as gc
from agents.schemas.competition import CompetitorProfile

ICP_SIZES = ["11-50 employees (seed to Series A)", "51-200 employees"]


@pytest.mark.parametrize("text, expected", [
    ("51-200 employees", (51, 200)),
    ("10,001+ employees", (10001, float("inf"))),
    ("Enterprise teams (501–2,000+ employees)", (501, float("inf"))),
    ("120 employees", (120, 120)),
    ("Series B", None),
    (None, None),
])
def test_headcount_parsing(text, expected):
    assert _headcount_range(text) == expected


def test_accounts_above_every_band_are_too_large():
    assert _size_verdict(SimpleNamespace(size="10,001+ employees"), ICP_SIZES) == "too_large"
    assert _size_verdict(SimpleNamespace(size="120 employees"), ICP_SIZES) is None
    assert _size_verdict(SimpleNamespace(size=None), ICP_SIZES) is None


def test_size_copied_from_the_icp_is_cleared_not_trusted():
    account = SimpleNamespace(size="51-200 employees")
    assert _size_verdict(account, ICP_SIZES) is None and account.size is None


@pytest.fixture
def profiled(monkeypatch):
    monkeypatch.setattr(gc, "_gather_profile_evidence", lambda s: ("Southwest is an airline.", "site"))
    monkeypatch.setattr(gc.social_profiles, "find_on_site", lambda website, name: {})

    def run(relevance):
        profile = CompetitorProfile(
            name="Southwest Airlines", website="https://southwest.com", relevance=relevance,
            relevance_reason="An airline that uses the product", opportunities=["x"],
        )
        monkeypatch.setattr(gc, "invoke_structured_with_fallback", lambda *a, **k: profile)
        return gc._profile_one({"name": "Southwest Airlines", "website": "https://southwest.com"}, {})
    return run


def test_non_competitors_are_dropped(profiled):
    assert profiled("not_a_competitor") == (None, "not_a_competitor")
    assert profiled("direct")[0] is not None
    assert profiled(None)[0] is not None  # no verdict is not a reason to drop


def test_a_failed_profile_call_drops_only_that_firm(monkeypatch):
    monkeypatch.setattr(gc, "_gather_profile_evidence", lambda s: ("Some text.", "site"))

    def exhausted(*_a, **_k):
        raise gc.LlmProvidersExhaustedError("profile", None)
    monkeypatch.setattr(gc, "invoke_structured_with_fallback", exhausted)
    assert gc._profile_one({"name": "Acme", "website": "https://acme.example"}, {}) == (None, "unprofiled")


def test_unreadable_sites_get_searched_instead(monkeypatch):
    searched = []
    monkeypatch.setattr(gc, "call_with_timeout", lambda fn, *a, **k: "")  # site serves no text
    monkeypatch.setattr(gc, "_search_and_scrape", lambda q, cfg, num_results: searched.append(q) or [
        {"url": f"https://review.example/{len(searched)}", "text": "Acme costs $9 a seat."},
    ])
    evidence, site = gc._gather_profile_evidence({"name": "Acme", "website": "https://www.acme.example", "sources": []})
    assert site == "" and len(searched) == len(gc._FALLBACK_QUERIES)
    assert '"Acme" acme.example' in searched and "Acme costs $9 a seat." in evidence


def test_site_socials_join_the_tracking_sources(monkeypatch):
    monkeypatch.setattr(gc.social_profiles, "find_on_site", lambda website, name: {
        "linkedin": "https://www.linkedin.com/company/acme", "x": "https://x.com/acme",
    })
    profile = CompetitorProfile(name="Acme", website="https://acme.example",
                                tracking_sources=[{"kind": "x", "value": "@acmehq", "confidence": "medium"}])
    gc._add_site_socials(profile, profile.website)
    assert [(s.kind, s.confidence) for s in profile.tracking_sources] == [("x", "medium"), ("linkedin", "high")]
