"""
End-to-end test of the competition-understanding subgraph with REAL LLM and Exa calls.

Nothing is stubbed. Each run pays for:
  - 1 planner call (thinking off, reading the offer + sibling domain/market context)
  - 3-5 tasks x 1-2 RECENCY-GATED Exa searches each, plus cheap-tier distillation
  - 1 cheap-tier structured extraction call (thinking off) returning the draft
    Ideal Competitor Profile plus the offer's SWOD
  - 1 cheap-tier refine call (thinking off, self-review over the draft profile)
  - 1 findings writer call (thinking off, anchored on the refined profile)

Note there are no longer per-competitor website verification scrapes: the stage
emits archetypes, which have no URL to verify.

Run all branches:
    python agents/tests/sub_agents/test_understand_competition.py
Run one branch:
    python agents/tests/sub_agents/test_understand_competition.py product
Under pytest:
    pytest -m live agents/tests/sub_agents/test_understand_competition.py

Assertions are invariants, not exact text: LLM output is nondeterministic, so we
assert the things the design actually promises (brand-free queries, the 3-5 task
clamp, a real research result, the two findings fields, a bounded positioning
understanding, no fabricated source URLs, a real IdealCompetitorProfile that
names no company and spans local plus international archetypes, and a SWOD
record the writer stayed anchored on), plus competition's own promises: EVERY
search is recency-gated and the sibling stages' Sources blocks (which belong to
those stages' retrieved sets) never reach this run's findings.
The gate is observed with a recording wrapper around search_and_scrape that
still delegates to the real Exa call -- observation, not stubbing. Failures
print the offending values so they are actionable.

Timings are printed, not asserted. Each branch's findings are also saved under
agents/tests/sub_agents/_out/ for a human read that asserts cannot replace.
"""

import json
import re
import sys
import time
from pathlib import Path

# Walk up from cwd to find the repo root (has pyproject.toml).
root = Path.cwd()
while root != root.parent:
    if (root / "pyproject.toml").exists():
        break
    root = root.parent
sys.path.insert(0, str(root))

from agents.llm.main import llm_timing_report  # noqa: E402
from agents.states import (  # noqa: E402
    CompetitionExtraction,
    IdealCompetitorProfile,
    MarketExtraction,
)
from agents.sub_agents.schema_states import Specialist  # noqa: E402
import agents.sub_agents.discover.understand_competition as uc  # noqa: E402
from agents.sub_agents.discover.understand_competition import build_competition_graph  # noqa: E402
import pytest

# Real LLM + web calls: opt-in with `uv run pytest -m live`.
pytestmark = pytest.mark.live

_OUT_DIR = Path(__file__).resolve().parent / "_out"

# Observe the recency gate without stubbing: patch the module-global
# search_and_scrape with a wrapper that records start_published_date, then
# delegates to the real Exa call.
_SEEN_RECENCY: list[str | None] = []
_ORIGINAL_SEARCH = uc.search_and_scrape


def _recording_search(query, config, num_results=3, start_published_date=None):
    _SEEN_RECENCY.append(start_published_date)
    return _ORIGINAL_SEARCH(
        query, config, num_results=num_results, start_published_date=start_published_date
    )


uc.search_and_scrape = _recording_search


# ---------------------------------------------------------------------------
# Fixtures. One product and one service, each cosplayed by a COMPETITION
# specialist, so a run exercises specialist selection by `domain ==
# "competition"` and the offer_noun branching both ways. Each fixture also
# carries the CANNED SIBLING STAGE OUTPUTS (offer_findings / market_findings /
# market_data) the competition stage is required to consume -- the stage does
# its own real research on top of them. The canned Sources blocks use URLs that
# are NOT this run's retrieved set: if stripping ever fails, those URLs leak
# into the findings and the fabrication scan fails.
# ---------------------------------------------------------------------------

SIBLING_DOMAIN_SOURCE = "https://domain-heatherdb.example"
SIBLING_MARKET_SOURCE = "https://market-heatherdb.example"

PRODUCT_OFFER = {
    "offer_type": "product",
    "offer_name": "HeatherDB",
    "offer_description": (
        "HeatherDB is a self-organizing, natively intelligent database that functions as a memory substrate "
        "where data itself becomes the model, eliminating the need for model weights, retraining, or GPUs."
    ),
    "target_market": ["Africa", "Middle East"],
    "problem": "General-purpose LLMs need enormous compute for reasoning that a storage-shaped design could do far more cheaply.",
    "solution": "A storage-shaped reasoning paradigm: an episodic knowledge index paired with a compact reasoning core.",
    "target_users": ["AI research teams", "on-device AI product builders"],
    "features": [
        "Self-organizing memory substrate",
        "Model ingestion",
        "Commodity hardware compatibility",
    ],
    "service_uniqueness": [],
    "how_it_works": (
        "Queries resolve against a persistent episodic index; a compact reasoning core synthesises "
        "responses with context, so intuition and lateral thinking come from retrieval-shaped "
        "memory rather than raw parameter scale."
    ),
    "specialists": [
        Specialist(
            domain="competition",
            name="Kwame Asante",
            role="Principal Competitive Analyst",
            affiliation="West Africa AI Market Desk",
            description=(
                "Charts the on-device and small-model AI reasoning landscape in West and East "
                "Africa: who actually ships, how they position, what they charge, and where "
                "their customers hurt."
            ),
        ),
    ],
    # -- Backend sibling outputs (Sources stripped at use) --
    "offer_findings": (
        "### On-device AI reasoning systems\neffective runtimes split context from "
        "parameters: a small reasoning core paired with a large retrieval-shaped index. "
        "HeatherDB sits in this category: retrieval-shaped memory rather than parameter scale.\n"
        f"\n### Sources\n[1] {SIBLING_DOMAIN_SOURCE}"
    ),
    "offer_domain_fit_understanding": "sits in the retrieval-shaped on-device reasoning category",
    "market_findings": (
        "### On-device AI buyers\nB2B teams in West and East Africa buy per-deployment; "
        "willingness to pay clusters below $20k/yr; the adoption barriers are compute cost "
        "and integration trust rather than awareness.\n"
        f"\n### Sources\n[1] {SIBLING_MARKET_SOURCE}"
    ),
    "product_market_fit_understanding": "fits B2B on-device reasoning in West and East Africa",
    "market_data": MarketExtraction(
        buyer_type="b2b",
        category="other",
        target_audience="AI research teams and on-device product builders",
        target_geo=["Africa", "Middle East"],
        category_conventions="small-model runtimes on commodity hardware; per-deployment licensing",
        market_demand="growing interest in on-device reasoning to cut inference cost",
        growth_outlook="growing",
    ),
}

SIBLING_DOMAIN_SOURCE_S = "https://domain-stitchup.example"
SIBLING_MARKET_SOURCE_S = "https://market-stitchup.example"

SERVICE_OFFER = {
    "offer_type": "service",
    "offer_name": "Engineering and Innovation Consultancy",
    "offer_description": (
        "Engineering and Innovation Consultancy provides end-to-end R&D services that guide hardware and software "
        "projects from initial concept and feasibility studies through prototyping, pilot deployment, mass "
        "manufacturing, and ongoing aftermarket support."
    ),
    "target_market": ["Kenya", "Africa", "Emerging markets"],
    "problem": "The complexity and fragmentation of bringing hardware products to market, specifically the need for integrated R&D, prototyping, manufacturing, and support that accounts for the operating realities of emerging markets.",
    "solution": "A structured hardware/software engineering lifecycle from consultancy to manufacturing.",
    "target_users": ["Startups", "Hardware innovators", "Emerging-market SMEs"],
    "features": [],
    "service_uniqueness": [
        "Integrated R&D and manufacturing",
        "Expertise in emerging-market operating realities",
        "Aftermarket support",
    ],
    "how_it_works": (
        "Clients receive end-to-end consultancy from feasibility and prototyping through pilots, "
        "mass manufacturing, and post-deployment support."
    ),
    "specialists": [
        Specialist(
            domain="competition",
            name="Njeri Wanjiru",
            role="Principal Competitive Analyst",
            affiliation="East Africa Hardware Innovation Desk",
            description=(
                "Maps the regional engineering-consultancy and contract-manufacturing landscape: "
                "how local and international players position, what startups actually pay, and "
                "where trust breaks down."
            ),
        ),
    ],
    "offer_findings": (
        "### On-demand tailoring services\nquality rests on the tailor, the fitting process "
        "and the delivery guarantee; the Gulf has strong local artisans but no standardised "
        "quality bar or 48-hour commitment.\n"
        f"\n### Sources\n[1] {SIBLING_DOMAIN_SOURCE_S}"
    ),
    "offer_domain_fit_understanding": "sits in on-demand tailored-apparel services",
    "market_findings": (
        "### On-demand services in Gulf cities\nbusy professionals and e-commerce sellers "
        "pay a premium for home pickup and delivery; trust is the adoption barrier rather "
        "than price.\n"
        f"\n### Sources\n[1] {SIBLING_MARKET_SOURCE_S}"
    ),
    "product_market_fit_understanding": "fits the premium on-demand services market in Gulf cities",
    "market_data": MarketExtraction(
        buyer_type="b2b",
        category="service",
        target_audience="Startups, hardware innovators, and emerging-market SMEs",
        target_geo=["Kenya", "Africa", "Emerging markets"],
        category_conventions="fixed-fee plus milestone engagements; quality gates expected",
        market_demand="High demand for integrated R&D and local prototyping",
        growth_outlook="growing",
    ),
}

BRANCHES = {"product": PRODUCT_OFFER, "service": SERVICE_OFFER}


# ---------------------------------------------------------------------------
# Runner: stream through the compiled graph, timing each node.
# ---------------------------------------------------------------------------


def _run_competition(offer: dict) -> tuple[dict, dict]:
    """Run the real graph once for one offer.

    Streams in updates mode so each node's arrival time is its wall clock --
    including the planner's, Exa's, the distillers', the extractor's, the
    refiner's and the writer's without a second run. State is accumulated the
    way the graph's channels reduce it: everything is a last-value channel
    except competition_task_research (operator.add), which is appended.

    Both structured nodes soft-fail, so a timing entry can be absent: a node that
    returns `{}` still appears in the stream, but one that raised before
    returning would not. `timings.get(node, 0.0)` in the report handles that.
    """
    initial = {k: v for k, v in offer.items() if k != "specialists"} | {
        "specialists": offer["specialists"],
        "scraped_content": None,
    }
    graph = build_competition_graph(checkpointer=False)

    state = dict(initial)
    timings: dict[str, float] = {}
    started = time.perf_counter()
    last = started

    for chunk in graph.stream(state, stream_mode="updates"):
        for node, update in chunk.items():
            now = time.perf_counter()
            timings[node] = now - last
            last = now
            if not update:
                continue
            for key, value in update.items():
                if key == "competition_task_research":
                    state[key] = list(state.get(key) or []) + list(value or [])
                else:
                    state[key] = value

    timings["_total"] = time.perf_counter() - started
    return state, timings


def _source_urls(findings: str) -> list[str]:
    """The http(s) URLs listed below '### Sources', trailing punctuation stripped."""
    body = findings.split("### Sources", 1)[-1]
    return [re.sub(r"[)\]},.;']+$", "", url) for url in re.findall(r"https?://\S+", body)]


def _body_urls(findings: str) -> list[str]:
    """The http(s) URLs the MODEL wrote in its notes (i.e. before the Sources block).

    This is the fabrication surface. The Sources block itself is appended by the
    harness from the retrieved set, so it cannot fabricate; the model, however,
    was told to cite only numbered [n] entries from its prompt and must not drop
    bare URLs into the prose.
    """
    body = findings.split("### Sources", 1)[0]
    return [re.sub(r"[)\]},.;']+$", "", url) for url in re.findall(r"https?://\S+", body)]


def _assert_competition_run(offer: dict, result: dict) -> None:
    """The invariants this pipeline promises. Each failure names the offender."""
    brand = offer["offer_name"].lower()
    noun = offer["offer_type"]

    # Recency gate: every search this run issued carries a start_published_date.
    assert _SEEN_RECENCY, f"[{noun}] no searches were issued"
    ungated = [i for i, r in enumerate(_SEEN_RECENCY) if r is None]
    assert not ungated, (
        f"[{noun}] competition research must recency-gate every search, but these "
        f"calls carried no start_published_date: {ungated}"
    )
    assert all(
        re.fullmatch(r"\d{4}-\d{2}-\d{2}", r or "") for r in _SEEN_RECENCY
    ), f"[{noun}] malformed recency cutoffs: {_SEEN_RECENCY}"

    task_list = result.get("competition_tasks")
    assert task_list is not None and task_list.tasks, "planner produced no tasks"
    plan = task_list.tasks
    assert 3 <= len(plan) <= 5, f"planner returned {len(plan)} tasks, expected 3-5"

    for t in plan:
        assert t.queries, f"task {t.area!r} has no queries"
        assert t.area and t.objective, f"task missing area/objective: {t.model_dump()}"
        for q in t.queries:
            assert brand not in q.lower(), (
                f"[{noun}] brand leaked into a query: {q!r} "
                "(queries must research the rivals/category, never the offer)"
            )

    bundles = result.get("competition_task_research") or []
    assert bundles, "no research bundles produced"
    ok = [b for b in bundles if not b.search_failed and b.notes.strip()]
    assert ok, (
        f"[{noun}] every task came back empty -- Exa down, bad key, or all queries dead. "
        f"Per-task: {[(b.area, b.search_failed, len(b.sources)) for b in bundles]}"
    )

    findings = result.get("competition_findings") or ""
    assert findings.strip(), f"[{noun}] competition_findings empty"
    assert "### Sources" in findings, f"[{noun}] findings missing the ### Sources block"

    # The sibling stages' Sources blocks belong to THEIR retrieved sets. If they
    # leak into this run's findings, the fabrication scan below would already
    # flag them (they are not in the retrieved set) -- this assert names the
    # cause rather than the symptom.
    for leaked in (SIBLING_DOMAIN_SOURCE, SIBLING_MARKET_SOURCE,
                   SIBLING_DOMAIN_SOURCE_S, SIBLING_MARKET_SOURCE_S):
        assert leaked not in findings, f"[{noun}] sibling-stage Source URL leaked into findings: {leaked}"

    positioning = result.get("competitive_positioning_understanding") or ""
    words = positioning.split()
    assert 1 <= len(words) <= 50, (
        f"[{noun}] competitive_positioning_understanding is {len(words)} words, must be 1-50: {positioning!r}"
    )

    retrieved = {u for b in bundles for u in b.sources if u}
    fabricated_block = [u for u in _source_urls(findings) if u not in retrieved]
    assert not fabricated_block, (
        f"[{noun}] citations in Sources not returned by research: {fabricated_block}"
    )
    fabricated_inline = [u for u in _body_urls(findings) if u not in retrieved]
    assert not fabricated_inline, (
        f"[{noun}] the model dropped bare URLs into its notes that were never "
        f"retrieved (it must cite [n] against the auditable list): {fabricated_inline}"
    )

    assert result.get("competition_complete") is True, f"[{noun}] completion flag not set"

    # The ideal competitor profile is the load-bearing output. Between 1 and 8
    # (the extractor clamps to MAX_ARCHETYPES and the <3 warning is non-fatal):
    # the test demands one real archetype, not padding.
    profile = result.get("ideal_competitor_profile")
    assert isinstance(profile, IdealCompetitorProfile), (
        f"[{noun}] ideal_competitor_profile is not an IdealCompetitorProfile: "
        f"{type(profile).__name__} {profile!r}"
    )
    archetypes = list(profile.archetypes or [])
    assert 1 <= len(archetypes) <= 8, (
        f"[{noun}] profile has {len(archetypes)} archetype(s), must be 1-8"
    )
    for a in archetypes:
        assert a.label.strip(), "an archetype entry has an empty label"
        assert a.archetype_description.strip(), (
            f"archetype {a.label!r} has an empty description"
        )
        assert a.geography_scope in ("local", "regional", "global", "any"), (
            f"archetype {a.label!r} has an invalid geography_scope {a.geography_scope!r}"
        )

    # The profile must name NOBODY. This is the invariant the whole design turns
    # on: an archetype that leaks a real company name makes the downstream
    # competitor agent believe its search has already happened. Checked against
    # the companies the research actually retrieved, since those are the names
    # the model could plausibly have lifted.
    labels_blob = " ".join(
        f"{a.label} {a.archetype_description} {a.typical_offering or ''}" for a in archetypes
    ).lower()
    leaked = sorted({
        domain.split("//", 1)[-1].split("/", 1)[0].removeprefix("www.")
        for domain in retrieved
        if domain.split("//", 1)[-1].split("/", 1)[0].removeprefix("www.") in labels_blob
    })
    assert not leaked, (
        f"[{noun}] archetypes name real retrieved domains {leaked} -- an archetype "
        f"describes a KIND of company, never a specific firm"
    )

    # GEO-UNBOUNDED: the profile must not collapse to only the offer's own
    # geographies. A run whose every archetype is scoped to one place has
    # re-introduced the target_geo filter this stage was changed to drop.
    scopes = {a.geography_scope for a in archetypes}
    assert scopes & {"global", "any", "regional"}, (
        f"[{noun}] every archetype is local ({sorted(scopes)}) -- the profile must "
        f"span local incumbents and international operators, not just the offer's market"
    )

    # The SWOD record is shipped alongside and stays usable.
    data = result.get("competition_data")
    assert isinstance(data, CompetitionExtraction), (
        f"[{noun}] competition_data is not a CompetitionExtraction: {type(data).__name__} {data!r}"
    )
    assert data.strengths or data.weaknesses or data.opportunities or data.differentiators, (
        f"[{noun}] SWOD record is entirely empty"
    )
    for f in data.strengths + data.weaknesses + data.opportunities + data.differentiators:
        assert isinstance(f, str) and f.strip(), "SWOD entry must be a non-empty string"

    # The writer was anchored on the refined profile: the notes must engage the
    # landscape it describes, or the anchor did not work.
    findings_lower = findings.lower()
    anchored = [
        a.label for a in archetypes
        if a.label and a.label.lower() in findings_lower
    ]
    assert anchored or len(archetypes) <= 2, (
        f"[{noun}] writer engaged none of the profile archetypes "
        f"{[a.label for a in archetypes]} -- the profile anchor failed"
    )


def _print_competition_report(offer: dict, result: dict, timings: dict) -> None:
    print(f"\n=== {offer['offer_name']} ({offer['offer_type']}) ===")
    print(f"  tasks: {[t.area for t in result['competition_tasks'].tasks]}")
    for b in result.get("competition_task_research") or []:
        status = "EMPTY" if b.search_failed else f"{len(b.sources)} source(s), {len(b.notes.split())} notes words"
        print(f"    - {b.area}: {status}")
    positioning = result.get("competitive_positioning_understanding") or ""
    print(f"  positioning understanding ({len(positioning.split())} words): {positioning}")
    profile = result.get("ideal_competitor_profile")
    if profile is not None:
        for a in profile.archetypes:
            print(f"    archetype [{a.geography_scope}]: {a.label} (confidence {a.confidence})")
        print(
            f"  ideal_competitor_profile: {len(profile.archetypes)} archetype(s), "
            f"confidence {profile.confidence}"
        )
    data = result.get("competition_data")
    if data is not None:
        print(
            f"  competition_data (SWOD): {len(data.strengths)} strengths, "
            f"{len(data.weaknesses)} weaknesses, "
            f"{len(data.opportunities)} opportunities, {len(data.differentiators)} differentiators"
        )
    for node in ("create_tasks_research", "conduct_research", "extract_competitor_profile", "refine_competitor_profile", "note_down_record"):
        print(f"  {node:22s} {timings.get(node, 0.0):6.1f}s")
    print(f"  {'total':22s} {timings['_total']:6.1f}s")


def _save_artifacts(offer: dict, result: dict, timings: dict, run_log_tag: str) -> None:
    _OUT_DIR.mkdir(parents=True, exist_ok=True)
    slug = offer["offer_name"].lower()
    (Path(_OUT_DIR) / f"{slug}_competition_notes.md").write_text(
        f"# {offer['offer_name']} - competition_findings\n\n"
        f"{result.get('competition_findings') or ''}\n",
        encoding="utf-8",
    )
    log_path = Path(_OUT_DIR) / "run_log.json"
    log = []
    if log_path.exists():
        try:
            log = json.loads(log_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            log = []
    data = result.get("competition_data")
    log.append(
        {
            "run_log_tag": run_log_tag,
            "offer": offer["offer_name"],
            "type": offer["offer_type"],
            "stages_seconds": timings,
            "positioning_words": len((result.get("competitive_positioning_understanding") or "").split()),
            "archetypes": [a.label for a in ((result.get("ideal_competitor_profile").archetypes) if result.get("ideal_competitor_profile") else [])],
            "recency_gated_searches": len(_SEEN_RECENCY),
        }
    )
    log_path.write_text(json.dumps(log, indent=2), encoding="utf-8")


def _run_and_assert(branch: str) -> None:
    offer = BRANCHES[branch]
    _SEEN_RECENCY.clear()
    result, timings = _run_competition(offer)
    # Save and print first: a failing run must still leave its findings and
    # timings behind, or the failure is undiagnosable from the assert message.
    _save_artifacts(offer, result, timings, run_log_tag="competition")
    _print_competition_report(offer, result, timings)
    _assert_competition_run(offer, result)


def test_understand_competition_product() -> None:
    _run_and_assert("product")


def test_understand_competition_service() -> None:
    _run_and_assert("service")


def main() -> None:
    """Run one or both branches, then the cumulative LLM timing report."""
    print("Real competition-understanding run (real LLM + Exa, nothing stubbed)")
    branches = ("product", "service") if len(sys.argv) < 2 else (sys.argv[1],)
    failed = False
    for branch in branches:
        if branch not in BRANCHES:
            sys.exit(f"unknown branch {branch!r}; choose from {sorted(BRANCHES)}")
        try:
            _run_and_assert(branch)
        except Exception:
            import traceback

            traceback.print_exc()
            failed = True
    # Traceback or not, a run that spent real money should still account for
    # where the time went.
    print("\nCumulative LLM wall clock (both branches; Exa time is NOT included):")
    print(llm_timing_report())
    if failed:
        sys.exit(1)


if __name__ == "__main__":
    main()