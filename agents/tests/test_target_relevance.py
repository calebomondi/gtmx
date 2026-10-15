"""Discovery keeps only plausible targets: competitors the model judges are
not competitors are dropped, and accounts whose real headcount is above every
ICP size band are dropped (a size copied from the ICP is not evidence)."""

from types import SimpleNamespace

import pytest

from agents.pipelines.accounts.account_discovery import _headcount_range, _size_verdict
from agents.pipelines.competitors import get_competitors as gc
from agents.schemas.competition import CompetitorProfile, CompetitorRelevance

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
        def fake(messages, schema=None, **k):
            if schema is CompetitorRelevance:
                return CompetitorRelevance(offer_job="x", their_job="x", same_buyer=True, substitute=True)
            return profile
        monkeypatch.setattr(gc, "invoke_structured_with_fallback", fake)
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


def test_adjacent_companies_are_stopped_before_profiling(monkeypatch):
    """AIGN Global (AI governance) was filed as a HeatherDB competitor."""
    monkeypatch.setattr(gc, "_gather_profile_evidence", lambda s: ("AIGN governs AI programmes.", "site"))
    calls = []

    def fake(messages, schema=None, **k):
        calls.append(schema)
        return CompetitorRelevance(offer_job="Store data that serves AI without GPUs",
                                   their_job="Advise organisations on AI governance", same_buyer=True, substitute=False)
    monkeypatch.setattr(gc, "invoke_structured_with_fallback", fake)
    offer = {"offer_name": "HeatherDB", "offer_description": "An intelligent database", "offer_type": "product"}
    assert gc._profile_one({"name": "AIGN Global", "website": "https://aign.global"}, offer) == (None, "not_a_competitor")
    assert calls == [CompetitorRelevance]  # no expensive profile call


def test_the_hunt_runs_the_planners_queries_before_label_fallbacks(monkeypatch):
    """Label queries ran first and the hunt stopped at their first hit, so the
    planner's good queries never ran (Sasol, GridCars as 'competitors')."""
    from agents.schemas.competition import CompetitorHuntPlan, CompetitorHuntTask

    plan = CompetitorHuntPlan(tasks=[CompetitorHuntTask(
        archetype_label="Local Full-Stack ODM", geography_scope="local", objective="Find local ODMs",
        queries=["hardware product development firm Nairobi", "electronics ODM Kenya"],
    )])
    monkeypatch.setattr(gc, "invoke_structured_with_fallback", lambda *a, **k: plan)
    state = {"ideal_competitor_profile": {"archetypes": [{"label": "Local Full-Stack ODM"}]},
             "target_market": ["Kenya"], "offer_name": "Engineering and Innovation Consultancy"}
    [task] = gc.plan_hunt(state)["competitor_hunt_tasks"]
    assert task.queries[:2] == ["hardware product development firm Nairobi", "electronics ODM Kenya"]
    assert task.queries[-1] == "Local Full-Stack ODM companies in Kenya"

    searched = []

    def search(query, cfg, num_results, start_published_date):
        searched.append(query)
        return [{"url": f"https://{len(searched)}-{i}.example", "text": "x"} for i in range(3)]
    monkeypatch.setattr(gc, "_search_and_scrape", search)
    monkeypatch.setattr(gc, "distill_documents", lambda docs, **k: "notes")
    monkeypatch.setattr(gc, "invoke_structured_with_fallback", lambda *a, **k: gc.CompetitorHuntBundle(
        archetype_label="x", geography_scope="local", queries=[], search_failed=False, sources=[]))
    try:
        gc._hunt_one(task)
    except Exception:  # noqa: BLE001 -- only the searches issued matter here
        pass
    assert searched == task.queries[:3]  # 3 results each: keeps going past the first hit
