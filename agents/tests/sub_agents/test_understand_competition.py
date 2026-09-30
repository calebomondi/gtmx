"""
End-to-end test of the competition-understanding subgraph with REAL LLM and Exa calls.

Nothing is stubbed. Each run pays for:
  - 1 planner call (thinking off, reading the offer + sibling domain/market context)
  - 3-5 tasks x 1-2 RECENCY-GATED Exa searches each, plus cheap-tier distillation
  - 1 cheap-tier structured extraction call (thinking off) with per-competitor
    website verification (a light scrape per stated URL)
  - 1 findings writer call (thinking off, anchored on the structured competitor set)

Run all branches:
    python agents/tests/sub_agents/test_understand_competition.py
Run one branch:
    python agents/tests/sub_agents/test_understand_competition.py product
Under pytest:
    pytest agents/tests/sub_agents/test_understand_competition.py

Assertions are invariants, not exact text: LLM output is nondeterministic, so we
assert the things the design actually promises (brand-free queries, the 3-5 task
clamp, a real research result, the two findings fields, a bounded positioning
understanding, no fabricated source URLs, a real CompetitionExtraction with a
bounded competitor set the writer stayed anchored on), plus competition's own
promises: EVERY search is recency-gated and the sibling stages' Sources blocks
(which belong to those stages' retrieved sets) never reach this run's findings.
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
from agents.states import CompetitionExtraction, MarketExtraction  # noqa: E402
from agents.sub_agents.schema_states import Specialist  # noqa: E402
import agents.sub_agents.understand_competition as uc  # noqa: E402
from agents.sub_agents.understand_competition import build_competition_graph  # noqa: E402

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

SIBLING_DOMAIN_SOURCE = "https://domain-mirosvb.example"
SIBLING_MARKET_SOURCE = "https://market-mirosvb.example"

PRODUCT_OFFER = {
    "offer_type": "product",
    "offer_name": "MirosVB",
    "offer_description": (
        "MirosVB is a reasoning paradigm that enhances AI systems with intuition, creativity, "
        "and lateral thinking capabilities by leveraging storage-shaped intelligence rather "
        "than relying on massive computational power."
    ),
    "target_market": ["Nigeria", "Kenya", "Ghana"],
    "problem": "General-purpose LLMs need enormous compute for reasoning that a storage-shaped design could do far more cheaply.",
    "solution": "A storage-shaped reasoning paradigm: an episodic knowledge index paired with a compact reasoning core.",
    "target_users": ["AI research teams", "on-device AI product builders"],
    "features": [
        "Storage-shaped reasoning core",
        "Episodic knowledge index",
        "Efficient inference on commodity hardware",
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
            name="Kofi Mensah",
            role="Principal Competitive Analyst",
            affiliation="Accra Competitive Intelligence Desk",
            description=(
                "Charts the on-device and small-model AI reasoning landscape in West and East "
                "Africa: who actually ships, how they position, what they charge, and where "
                "their customers hurt."
            ),
        ),
    ],
    # -- Canned sibling stage outputs (Sources blocks must be stripped at use) --
    "offer_findings": (
        "### On-device AI reasoning systems\neffective runtimes split context from "
        "parameters: a small reasoning core paired with a large retrieval-shaped index. "
        "MirosVB sits in this category: retrieval-shaped memory rather than parameter scale.\n"
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
        target_geo=["Nigeria", "Kenya", "Ghana"],
        category_conventions="small-model runtimes on commodity hardware; per-deployment licensing",
        market_demand="growing interest in on-device reasoning to cut inference cost",
        growth_outlook="growing",
    ),
}

SIBLING_DOMAIN_SOURCE_S = "https://domain-stitchup.example"
SIBLING_MARKET_SOURCE_S = "https://market-stitchup.example"

SERVICE_OFFER = {
    "offer_type": "service",
    "offer_name": "StitchUp",
    "offer_description": (
        "StitchUp is an on-demand tailoring service connecting customers with vetted local "
        "tailors for fittings, alterations, and custom garments, with delivery and quality guarantees."
    ),
    "target_market": ["UAE", "Saudi Arabia"],
    "problem": "Reliable tailoring in Gulf cities means knowing a private tailor, waiting weeks, and hoping the result fits.",
    "solution": "A vetted local tailor network with in-home pickup and delivery, quality-scored fittings and a satisfaction guarantee.",
    "target_users": ["busy professionals", "e-commerce sellers needing garment alterations"],
    "features": [],
    "service_uniqueness": [
        "Vetted tailor network",
        "Quality guarantee on fit",
        "48-hour pickup and delivery",
    ],
    "how_it_works": (
        "Customers book a fitting online; a vetted tailor is dispatched with a measuring kit, "
        "garments are altered or made to order, and are delivered back within 48 hours under a fit guarantee."
    ),
    "specialists": [
        Specialist(
            domain="competition",
            name="Fatima Al-Rashid",
            role="Principal Competitive Analyst",
            affiliation="Dubai Consumer Services Intelligence",
            description=(
                "Maps the on-demand services and tailoring landscape in Gulf cities: the "
                "established ateliers, the delivery-managed alternatives, what they charge "
                "and where their customers defect."
            ),
        ),
    ],
    # -- Canned sibling stage outputs (Sources blocks must be stripped at use) --
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
        buyer_type="b2c",
        category="service",
        target_audience="busy professionals and e-commerce sellers",
        target_geo=["UAE", "Saudi Arabia"],
        category_conventions="home pickup/delivery at a premium; satisfaction guarantee expected",
        market_demand="growing comfort with on-demand home services",
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
    including the planner's, Exa's, the distillers', the extractor's (with its
    in-node URL verification) and the writer's without a second run. State is
    accumulated the way the graph's channels reduce it: everything is a
    last-value channel except competition_task_research (operator.add), which
    is appended.
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

    # The structured competitor set is the load-bearing output. Between 1 and 5
    # (the extractor clamps to 5 and the <3 warning is non-fatal): the test
    # demands one real competitor, not padding.
    data = result.get("competition_data")
    assert isinstance(data, CompetitionExtraction), (
        f"[{noun}] competition_data is not a CompetitionExtraction: {type(data).__name__} {data!r}"
    )
    competitors = list(data.competitors or [])
    assert 1 <= len(competitors) <= 5, (
        f"[{noun}] competitor set has {len(competitors)} entries, must be 1-5"
    )

    # The writer was anchored on the structured set: the notes must name at least
    # one of the extracted rivals, or the anchor did not work.
    names = [c.name for c in competitors if c.name]
    if names:
        findings_lower = findings.lower()
        echoed = [n for n in names if n.lower() in findings_lower]
        assert echoed, (
            f"[{noun}] writer never named any extracted competitor {names} -- "
            f"the structured-set anchor failed"
        )

    # Every named competitor is usable for downstream consumers.
    for c in competitors:
        assert c.name.strip(), "a competitor entry has an empty name"
        assert c.description.strip(), f"competitor {c.name!r} has an empty description"
        for f in data.strengths + data.weaknesses + data.opportunities + data.differentiators:
            assert isinstance(f, str) and f.strip(), "SWOD entry must be a non-empty string"


def _print_competition_report(offer: dict, result: dict, timings: dict) -> None:
    print(f"\n=== {offer['offer_name']} ({offer['offer_type']}) ===")
    print(f"  tasks: {[t.area for t in result['competition_tasks'].tasks]}")
    for b in result.get("competition_task_research") or []:
        status = "EMPTY" if b.search_failed else f"{len(b.sources)} source(s), {len(b.notes.split())} notes words"
        print(f"    - {b.area}: {status}")
    positioning = result.get("competitive_positioning_understanding") or ""
    print(f"  positioning understanding ({len(positioning.split())} words): {positioning}")
    data = result.get("competition_data")
    if data is not None:
        for c in data.competitors:
            print(f"    competitor: {c.name} -- {c.website or '(no website)'}")
        print(
            f"  competition_data: {len(data.competitors)} competitor(s), "
            f"{len(data.strengths)} strengths, {len(data.weaknesses)} weaknesses, "
            f"{len(data.opportunities)} opportunities, {len(data.differentiators)} differentiators"
        )
    for node in ("create_tasks_research", "conduct_research", "extract_competition_data", "note_down_record"):
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
            "competitors": [c.name for c in (data.competitors if data else [])],
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