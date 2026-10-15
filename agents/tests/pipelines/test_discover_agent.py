"""
End-to-end test of the discovery agent -- the top-level workflow that
amalgamates every pipelines pipeline -- with REAL LLM + Exa calls
(plus a real website scrape for the intake stage). Nothing is stubbed.

The intake stage is interactive, so like test_discover_offer.py this test
DRIVES INTERRUPTS: it streams the compiled agent, auto-answers each interrupt
from a type-keyed table, and resumes with Command(resume=...) on the same
thread until the whole DAG finishes:

    discover_offer -> create_specialists -> [understand_offer ∥ understand_market]
        -> understand_competition -> determine_icp

Each run pays for the intake draft/rest calls, the four-specialist
creation, and the full offer + market (parallel) + competition + ICP pipelines:
a plazer + 3-5 research tasks x Exa searches + distillation + a writer for each
of the three research stages, and the ICP stage's create/refine/note calls.

`offer_type` is asserted by the caller and seeded into the session up front — the
intake form owns it and the agent no longer classifies it — so the harness feeds
it directly, exactly as `_build_initial_state` does.

Run:
    python agents/tests/pipelines/test_discover_agent.py
Under pytest:
    pytest -m live agents/tests/pipelines/test_discover_agent.py

Assertions are invariants, not exact text: every stage's completion flag is set,
the three research stages carry a ### Sources block and the ICP stage is pure
synthesis (no Sources), the structured extractions are typed, and the specialists
are all four domains. Failures name the offender.
"""

import json
import sys
import time
import uuid
from pathlib import Path

from pydantic import BaseModel

# Walk up from cwd to find the repo root (has pyproject.toml).
root = Path.cwd()
while root != root.parent:
    if (root / "pyproject.toml").exists():
        break
    root = root.parent
sys.path.insert(0, str(root))

from agents.llm.main import llm_timing_report  # noqa: E402
from agents.schemas.competition import CompetitionExtraction, IdealCompetitorProfile  # noqa: E402
from agents.schemas.icp import ICP  # noqa: E402
from agents.schemas.market import MarketExtraction  # noqa: E402
from agents import discovery_agent  # noqa: E402
from langgraph.types import Command  # noqa: E402
import pytest

# Real LLM + web calls: opt-in with `uv run pytest -m live`.
pytestmark = pytest.mark.live

_OUT_DIR = Path(__file__).resolve().parent / "_out" / "discover_agent"

TOP_LEVEL_NODES = (
    "discover_offer",
    "create_specialists",
    "understand_offer",
    "understand_market",
    "understand_competition",
    "determine_icp",
)


# ---------------------------------------------------------------------------
# Fixture. One product branch keeps the run intentionally small -- of the
# family's tests this is the one that spends the most per run.
# ---------------------------------------------------------------------------

PRODUCT_OFFER = {
    "offer_name": "HeatherDB",
    "website_url": "https://aphorion.co/",
    "offer_type": "product",
}

BRANCHES = {"product": PRODUCT_OFFER}


# ---------------------------------------------------------------------------
# Runner: stream the compiled agent, answering interrupts by type.
# ---------------------------------------------------------------------------


def _answer_for(payload: dict) -> str:
    ptype = (payload or {}).get("type")
    auto = {
        "offer_name_mismatch": "1",
        "url_unscrappable": "continue",
        "product_service_description_confirmation": "yes",
    }
    return auto.get(ptype, "yes")


def _run_discovery(branch: str) -> tuple[dict, dict, list[dict], float]:
    """Run the full discovery agent once, auto-answering intake interrupts.

    Node timings are inter-chunk deltas (family convention): in updates mode a
    node appears once, the moment it finishes, so elapsed time since the previous
    update is the closest cheap proxy for how long the node ran.
    """
    offer = BRANCHES[branch]
    agent = discovery_agent.build_discovery_agent()
    thread_id = uuid.uuid4().hex
    config = {"configurable": {"thread_id": thread_id}}

    initial = {
        "offer_name": offer["offer_name"],
        "website_url": offer["website_url"],
        # Seeded the way _build_initial_state seeds it, so the run exercises the
        # same path the intake form drives in production.
        "offer_type": offer["offer_type"],
        "messages": [],
    }

    state = dict(initial)
    node_times: dict[str, float] = {}
    interrupt_log: list[dict] = []
    started = time.perf_counter()
    last = started

    while True:
        interrupts = []
        for chunk in agent.stream(state, config, stream_mode="updates"):
            now = time.perf_counter()
            for node, update in chunk.items():
                if node == "__interrupt__":
                    interrupts = list(update)
                    continue
                if node not in TOP_LEVEL_NODES:
                    continue
                node_times[node] = node_times.get(node, 0.0) + (now - last)
                last = now
        if not interrupts:
            break

        payload = interrupts[0].value
        answer = _answer_for(payload)
        interrupt_log.append({"type": payload.get("type"), "answer": answer})
        print(f"  [interrupt] {payload.get('type')} -> {answer!r}")
        state = Command(resume=answer)

    total = last - started
    final = agent.get_state(config).values
    return final, node_times, interrupt_log, total


def _jsonable(v):
    if isinstance(v, BaseModel):
        return v.model_dump(mode="json")
    if isinstance(v, dict):
        return {k: _jsonable(x) for k, x in v.items()}
    if isinstance(v, (list, tuple)):
        return [_jsonable(x) for x in v]
    if hasattr(v, "content"):
        try:
            return {"type": v.type, "content": str(v.content)}
        except Exception:
            return str(v)
    return v


def _sources_block(findings: str) -> bool:
    return "### Sources" in (findings or "")


def _assert_discovery_run(branch: str, final: dict, interrupt_log: list[dict], node_times: dict) -> None:
    noun = BRANCHES[branch]["offer_type"]

    # -- Intake completed and landed in the loose keys --
    # Nothing writes offer_type any more, so this is a passthrough check: the
    # seeded value has to survive the whole agent, since create_specialists reads
    # it off the same session to build the specialist roster.
    assert final.get("offer_type") == noun, (
        f"[{branch}] offer_type {final.get('offer_type')!r} must equal {noun!r}"
    )
    assert final.get("confirmed") is True, f"[{branch}] flow never confirmed the offer"
    desc = (final.get("offer_description") or "").strip()
    assert desc and desc.lower() not in ("none", "n/a", "unknown"), (
        f"[{branch}] placeholder/missing offer_description: {desc!r}"
    )

    # -- Specialist team: all four domains --
    specialists = list(final.get("specialists") or [])
    domains = {getattr(s, "domain", None) for s in specialists}
    assert domains == {"product", "market", "competition", "gtm"}, (
        f"[{branch}] specialist domains must be all four: {domains}"
    )

    # -- Every stage completed --
    flags = {
        g: final.get(f"{g}_complete")
        for g in ("offer_under", "market", "competition", "icp")
    }
    assert all(flags.values()), f"[{branch}] stages incomplete: {flags}"
    assert final.get("offer_under_complete") is True

    # -- Research findings: real prose + an auditable Sources block --
    for key in ("offer_findings", "market_findings", "competition_findings"):
        findings = (final.get(key) or "").strip()
        assert findings, f"[{branch}] {key} empty"
        assert _sources_block(findings), f"[{branch}] {key} missing the ### Sources block"
    icp_findings = (final.get("icp_findings") or "").strip()
    assert icp_findings, f"[{branch}] icp_findings empty"
    assert not _sources_block(icp_findings), (
        f"[{branch}] ICP stage is pure synthesis -- no Sources block allowed"
    )

    # -- The structured extractions reached the aggregate state --
    assert isinstance(final.get("market_data"), MarketExtraction), (
        f"[{branch}] market_data {type(final.get('market_data')).__name__} is not MarketExtraction"
    )
    assert isinstance(final.get("competition_data"), CompetitionExtraction), (
        f"[{branch}] competition_data not a CompetitionExtraction"
    )
    # The competition stage's PRIMARY output is the archetype profile, not the
    # SWOD record. It must survive the _COMPETITION_KEYS fold back into the
    # aggregate state, or the downstream competitor agent has nothing to hunt.
    profile = final.get("ideal_competitor_profile")
    assert isinstance(profile, IdealCompetitorProfile), (
        f"[{branch}] ideal_competitor_profile "
        f"{type(profile).__name__} is not IdealCompetitorProfile"
    )
    assert profile.archetypes, f"[{branch}] ideal_competitor_profile has no archetypes"
    # Geo-unbounded is the whole point of the change: an all-local profile means
    # the target_geo filter came back.
    assert {a.geography_scope for a in profile.archetypes} & {"global", "regional", "any"}, (
        f"[{branch}] every archetype is local -- the profile must span "
        f"international operators too"
    )
    assert isinstance(final.get("icp_data"), ICP), (
        f"[{branch}] icp_data {type(final.get('icp_data')).__name__} is not ICP"
    )
    assert final["market_data"].target_audience, f"[{branch}] market_data missing target_audience"

    # -- Every top-level stage actually ran --
    missing = [n for n in TOP_LEVEL_NODES if n not in node_times]
    assert not missing, f"[{branch}] stages never ran to completion: {missing}"

    assert interrupt_log, f"[{branch}] expected at least one intake interrupt to auto-answer"


def _fmt(seconds):
    m, s = divmod(int(seconds), 60)
    return f"{m}m {s:02d}s"


def _print_discovery_report(branch, final, node_times, interrupt_log):
    print(f"\n=== discovery_agent: {branch} (offer_type={final.get('offer_type')}) ===")
    print(f"  description: {final.get('offer_description')}")
    print(f"  specialists: {[getattr(s, 'domain', '?') for s in (final.get('specialists') or [])]}")
    for key in ("offer_findings", "market_findings", "competition_findings", "icp_findings"):
        findings = (final.get(key) or "").strip()
        print(f"  {key}: {len(findings.split())} words, sources={'### Sources' in findings}")
    icp = final.get("icp_data")
    if icp is not None:
        print(
            f"  icp_data: {icp.product_name} ({icp.buyer_type}) -- "
            f"{len(icp.industries or [])} industries, {len(icp.buyer_personas or [])} personas, "
            f"{len(icp.target_channels or [])} channels"
        )
    print("  interrupts answered:", [e["type"] for e in interrupt_log])
    tl = 0.0
    for n in TOP_LEVEL_NODES:
        d = node_times.get(n, 0.0)
        tl += d
        print(f"  {n:<26} {d:6.1f}s   {_fmt(d)}")
    print(f"  {'TOTAL (nodes)':<26} {tl:6.1f}s   {_fmt(tl)}")


def _save_artifacts(branch, final, node_times, interrupt_log, total):
    _OUT_DIR.mkdir(parents=True, exist_ok=True)
    (Path(_OUT_DIR) / f"{branch}_final_state.json").write_text(
        json.dumps(_jsonable(final), indent=2), encoding="utf-8"
    )
    notes = []
    for key in ("offer_findings", "market_findings", "competition_findings", "icp_findings"):
        notes.append(f"# {key}\n\n{final.get(key) or ''}\n")
    (Path(_OUT_DIR) / f"{branch}_notes.md").write_text("\n\n---\n\n".join(notes), encoding="utf-8")
    log_path = Path(_OUT_DIR) / "run_log.json"
    log = []
    if log_path.exists():
        try:
            log = json.loads(log_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            log = []
    log.append(
        {
            "run_log_tag": "discover_agent",
            "branch": branch,
            "offer_type": final.get("offer_type"),
            "confirmed": final.get("confirmed"),
            "interrupts": [e["type"] for e in interrupt_log],
            "stages_seconds": node_times,
            "total_seconds": total,
        }
    )
    log_path.write_text(json.dumps(log, indent=2), encoding="utf-8")


def _run_and_assert(branch: str) -> None:
    final, node_times, interrupt_log, total = _run_discovery(branch)
    # Save and print first: a failing run must still leave its state behind.
    _save_artifacts(branch, final, node_times, interrupt_log, total)
    _print_discovery_report(branch, final, node_times, interrupt_log)
    _assert_discovery_run(branch, final, interrupt_log, node_times)


def test_discovery_agent_product() -> None:
    _run_and_assert("product")


def main() -> None:
    """Run the full discovery agent, then the cumulative LLM timing report."""
    print("Real discovery-agent run (real LLM + real Exa + real scrape, nothing stubbed)")
    branches = ("product",) if len(sys.argv) < 2 else (sys.argv[1],)
    failed = False
    for branch in branches:
        if branch not in BRANCHES:
            sys.exit(f"unknown branch {branch!r}; choose from {sorted(BRANCHES)}")
        try:
            _run_and_assert(branch)
        except SystemExit:
            raise
        except Exception:
            import traceback

            traceback.print_exc()
            failed = True
    # Traceback or not, a run that spent real money should still account for
    # where the time went.
    print("\nCumulative LLM wall clock (all branches):")
    print(llm_timing_report())
    if failed:
        sys.exit(1)


if __name__ == "__main__":
    main()