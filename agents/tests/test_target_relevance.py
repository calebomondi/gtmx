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

    def run(relevance):
        profile = CompetitorProfile(
            name="Southwest Airlines", website="https://southwest.com", relevance=relevance,
            relevance_reason="An airline that uses the product", opportunities=["x"],
        )
        monkeypatch.setattr(gc, "invoke_structured_with_fallback", lambda *a, **k: profile)
        return gc._profile_one({"name": "Southwest Airlines", "website": "https://southwest.com"}, {})
    return run


def test_non_competitors_are_dropped(profiled):
    assert profiled("not_a_competitor") is None
    assert profiled("direct") is not None
    assert profiled(None) is not None  # no verdict is not a reason to drop
