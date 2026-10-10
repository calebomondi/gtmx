"""
End-to-end test of the offer-domain subgraph with REAL LLM and Exa calls.

Nothing is stubbed. Each run pays for:
  - 1 flagship planner call (thinking off)
  - 3-5 tasks x 1-3 Exa searches each, plus cheap-tier distillation of every page
  - 1 flagship writer call (thinking on)

Run all branches:
    python agents/tests/sub_agents/test_understand_offer.py
Run one branch:
    python agents/tests/sub_agents/test_understand_offer.py product
Under pytest:
    pytest agents/tests/sub_agents/test_understand_offer.py

Assertions are invariants, not exact text: LLM output is nondeterministic, so we
assert the things the design actually promises (brand-free queries, the 3-5 task
clamp, a real research result, the two findings fields, a bounded fit
understanding, and no fabricated source URLs -- the sources block itself is
appended by the harness from the retrieved set, so fraud there is structural, and
this test also scans the model's own prose for URLs it was never given). Failures
print the offending values so they are actionable.

Timings are printed, not asserted: per-stage wall clock from LangGraph stream
arrival times, the total, and llm_timing_report() (which splits the LLM share
from the Exa share -- Exa latency is a large part of the wall clock and the LLM
gateway never sees it). Each branch's findings are also saved under
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
from agents.sub_agents.schema_states import Specialist  # noqa: E402
from agents.sub_agents.discover.understand_offer import build_product_graph  # noqa: E402

_OUT_DIR = Path(__file__).resolve().parent / "_out"


# ---------------------------------------------------------------------------
# Fixtures. One product and one service, so a run exercises specialist
# selection by `domain` and the offer_noun branching both ways.
# ---------------------------------------------------------------------------

PRODUCT_OFFER = {
    "offer_type": "product",
    "offer_name": "Cloud of Associations",
    "offer_description": (
        "Cloud of Associations is a drop-in associative layer for AI systems that adds intuition, creativity, "
        "and lateral reasoning capabilities to existing models without requiring GPU acceleration or full retraining."
    ),
    "target_market": ["Africa", "Middle East"],
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
            domain="product",
            name="Dr. Aris Thorne",
            role="Principal AI Architect",
            affiliation="Lagos Institute of Cognitive Systems",
            description=(
                "Analyses how storage-shaped intelligence matches what the most efficient "
                "reasoning architectures achieve in practice."
            ),
        ),
    ],
}

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
            domain="service",
            name="Amara Okafor",
            role="Principal On-Demand Operations Analyst",
            affiliation="Accra Service Economy Research",
            description=(
                "Judges the service against what customers in these markets expect from "
                "on-demand providers: reliability of fulfilment and clear service-level promises."
            ),
        ),
    ],
}

BRANCHES = {"product": PRODUCT_OFFER, "service": SERVICE_OFFER}


# ---------------------------------------------------------------------------
# Runner: stream through the compiled graph, timing each node.
# ---------------------------------------------------------------------------


def _run_offer(offer: dict) -> tuple[dict, dict]:
    """Run the real graph once for one offer.

    Streams in updates mode so each node's arrival time is its wall clock --
    including the planner's, Exa's, the distillers' and the writer's without a
    second run. State is accumulated the way the graph's channels reduce it:
    everything is a last-value channel except task_research (operator.add),
    which is appended.
    """
    initial = {k: v for k, v in offer.items() if k != "specialists"} | {
        "specialists": offer["specialists"],
        "scraped_content": None,
    }
    graph = build_product_graph(checkpointer=False)

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
                if key == "task_research":
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


def _assert_offer_run(offer: dict, result: dict) -> None:
    """The invariants this pipeline promises. Each failure names the offender."""
    brand = offer["offer_name"].lower()
    noun = offer["offer_type"]

    task_list = result.get("tasks")
    assert task_list is not None and task_list.tasks, "planner produced no tasks"
    plan = task_list.tasks
    assert 3 <= len(plan) <= 5, f"planner returned {len(plan)} tasks, expected 3-5"

    for t in plan:
        assert t.queries, f"task {t.area!r} has no queries"
        assert t.area and t.objective, f"task missing area/objective: {t.model_dump()}"
        for q in t.queries:
            assert brand not in q.lower(), (
                f"[{noun}] brand leaked into a query: {q!r} "
                "(queries must research the domain/category, never the offer)"
            )

    bundles = result.get("task_research") or []
    assert bundles, "no research bundles produced"
    ok = [b for b in bundles if not b.search_failed and b.notes.strip()]
    assert ok, (
        f"[{noun}] every task came back empty -- Exa down, bad key, or all queries dead. "
        f"Per-task: {[(b.area, b.search_failed, len(b.sources)) for b in bundles]}"
    )

    findings = result.get("offer_findings") or ""
    assert findings.strip(), f"[{noun}] offer_findings empty"
    assert "### Sources" in findings, f"[{noun}] findings missing the ### Sources block"

    fit = result.get("offer_domain_fit_understanding") or ""
    words = fit.split()
    assert 1 <= len(words) <= 50, (
        f"[{noun}] product_domain_understanding is {len(words)} words, must be 1-50: {fit!r}"
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

    assert result.get("offer_under_complete") is True, f"[{noun}] completion flag not set"


def _print_offer_report(offer: dict, result: dict, timings: dict) -> None:
    print(f"\n=== {offer['offer_name']} ({offer['offer_type']}) ===")
    print(f"  tasks: {[t.area for t in result['tasks'].tasks]}")
    for b in result.get("task_research") or []:
        status = "EMPTY" if b.search_failed else f"{len(b.sources)} source(s), {len(b.notes.split())} notes words"
        print(f"    - {b.area}: {status}")
    fit = result.get("offer_domain_fit_understanding") or ""
    print(f"  fit understanding ({len(fit.split())} words): {fit}")
    for node in ("create_tasks_research", "conduct_research", "note_down_record"):
        print(f"  {node:22s} {timings.get(node, 0.0):6.1f}s")
    print(f"  {'total':22s} {timings['_total']:6.1f}s")


def _save_artifacts(offer: dict, result: dict, timings: dict) -> None:
    _OUT_DIR.mkdir(parents=True, exist_ok=True)
    slug = offer["offer_name"].lower()
    (Path(_OUT_DIR) / f"{slug}_notes.md").write_text(
        f"# {offer['offer_name']} - offer_findings\n\n"
        f"{result.get('offer_findings') or ''}\n",
        encoding="utf-8",
    )
    log_path = Path(_OUT_DIR) / "run_log.json"
    log = []
    if log_path.exists():
        try:
            log = json.loads(log_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            log = []
    log.append(
        {
            "offer": offer["offer_name"],
            "type": offer["offer_type"],
            "stages_seconds": timings,
            "fit_words": len((result.get("offer_domain_fit_understanding") or "").split()),
        }
    )
    log_path.write_text(json.dumps(log, indent=2), encoding="utf-8")


def _run_and_assert(branch: str) -> None:
    offer = BRANCHES[branch]
    result, timings = _run_offer(offer)
    # Save and print first: a failing run must still leave its findings and
    # timings behind, or the failure is undiagnosable from the assert message.
    _save_artifacts(offer, result, timings)
    _print_offer_report(offer, result, timings)
    _assert_offer_run(offer, result)


def test_understand_offer_product() -> None:
    _run_and_assert("product")


def test_understand_offer_service() -> None:
    _run_and_assert("service")


def main() -> None:
    """Run one or both branches, then the cumulative LLM timing report."""
    print("Real offer-domain run (real LLM + Exa, nothing stubbed)")
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