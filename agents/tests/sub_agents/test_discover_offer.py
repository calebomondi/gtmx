"""
End-to-end test of the interactive offer-intake subgraph with REAL LLM calls and
REAL website scraping (nothing stubbed).

The intake pipeline is interactive, so this is the one sub_agents test that
DRIVES INTERRUPTS: it streams the graph, auto-answers every interrupt from a
type-keyed table (the same table test_gtmx_agent.py uses), and resumes with
Command(resume=...) and the same thread config until the flow completes.

Each branch pays for:
  - 1-2 offer-type classifier calls (a second deep pass only when the first is unsure)
  - 1 description-draft call (get_product_service_description)
  - 1 rest-extraction call (retrieve_rest_product_service_info)
plus a real website scrape when the fixture carries a website_url.

Branches:
  - product:  real scrape of https://aphorion.co/ (HeatherDB is named on the
              page, so the name-existence gate passes and the classifier has
              content) -> confident product, draft, confirm.
  - service:  URL-less ("StitchUp") -> the classifier has only a name, so the
              flow deterministically interrupts with offer_type_clarification;
              the harness answers "service", then confirms the description.

Run all branches:
    python agents/tests/sub_agents/test_discover_offer.py
Run one branch:
    python agents/tests/sub_agents/test_discover_offer.py product
Under pytest:
    pytest agents/tests/sub_agents/test_discover_offer.py

Assertions are invariants, not exact text (LLM output is nondeterministic): the
flow reached the end, offer_type matches the branch, confirmed is True, the
description is real prose (no 'None'/'N/A' placeholders), the extraction fields
are the right shapes, and every interrupt that fired was auto-answered and
recorded in follow_up.user_replies AND messages. Failures name the offender.
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
from agents.helpers import as_follow_up  # noqa: E402
from agents.sub_agents.discover_offer import build_offer_discovery_graph  # noqa: E402
from langgraph.types import Command  # noqa: E402

_OUT_DIR = Path(__file__).resolve().parent / "_out" / "discover_offer"


# ---------------------------------------------------------------------------
# Fixtures. One branch drives a real scrape; the other is deliberately URL-less
# so the classifier must give up and the flow interrupts for the type.
# ---------------------------------------------------------------------------

PRODUCT_OFFER = {
    "offer_name": "HeatherDB",
    "website_url": "https://aphorion.co/",
    "offer_type_answer": "product",
}

SERVICE_OFFER = {
    "offer_name": "StitchUp",
    "website_url": None,
    "offer_type_answer": "service",
}

BRANCHES = {"product": PRODUCT_OFFER, "service": SERVICE_OFFER}


# ---------------------------------------------------------------------------
# Runner: stream through the compiled graph, answering interrupts by type.
# ---------------------------------------------------------------------------


def _answer_for(payload: dict, branch: str) -> str:
    """Map an interrupt payload to a deterministic reply (mirrors
    test_gtmx_agent.py's resolve_answer)."""
    ptype = (payload or {}).get("type")
    auto = {
        "offer_name_mismatch": "1",          # pick the first candidate found
        "url_unscrappable": "continue",      # work from the name/description
        "product_service_description_confirmation": "yes",
    }
    if ptype == "offer_type_clarification":
        return BRANCHES[branch]["offer_type_answer"]
    return auto.get(ptype, "yes")


def _run_intake(branch: str) -> tuple[dict, dict, list[dict]]:
    """Run one branch of the real intake graph with interrupts auto-answered.

    Each call builds a fresh graph (own MemorySaver) and thread, so branches can
    never contaminate each other's checkpoints. Interrupts are collected from
    the updates-mode stream (`__interrupt__` chunks), answered, and resumed with
    Command(resume=...) against the same thread config until the flow ends.
    """
    offer = BRANCHES[branch]
    graph = build_offer_discovery_graph()  # checkpointer=True -> MemorySaver
    thread_id = uuid.uuid4().hex
    config = {"configurable": {"thread_id": thread_id}}

    initial = {
        "offer_name": offer["offer_name"],
        "website_url": offer["website_url"],
        "messages": [],
    }

    state = dict(initial)
    timings: dict[str, float] = {}
    interrupt_log: list[dict] = []
    started = time.perf_counter()
    last = started

    while True:
        interrupts = []
        for chunk in graph.stream(state, config, stream_mode="updates"):
            now = time.perf_counter()
            for node, update in chunk.items():
                if node == "__interrupt__":
                    interrupts = list(update)
                    continue
                timings[node] = now - last
                last = now
        if not interrupts:
            break

        payload = interrupts[0].value
        answer = _answer_for(payload, branch)
        interrupt_log.append(
            {"type": payload.get("type"), "answer": answer, "question": payload.get("question")}
        )
        print(f"  [interrupt] {payload.get('type')} -> {answer!r}")

        state = Command(resume=answer)
        # Resume against the SAME thread so the checkpointed node re-enters.

    timings["_total"] = time.perf_counter() - started
    final = graph.get_state(config).values
    return final, timings, interrupt_log


def _jsonable(v):
    """Best-effort conversion of state values for JSON artifacts."""
    if isinstance(v, BaseModel):
        return v.model_dump(mode="json")
    if isinstance(v, dict):
        return {k: _jsonable(x) for k, x in v.items()}
    if isinstance(v, (list, tuple)):
        return [_jsonable(x) for x in v]
    if hasattr(v, "content"):  # LangChain message
        try:
            return {"type": v.type, "content": str(v.content)}
        except Exception:
            return str(v)
    return v


def _assert_intake_run(branch: str, final: dict, interrupt_log: list[dict]) -> None:
    """The invariants this intake flow promises. Each failure names the offender."""
    noun = BRANCHES[branch]["offer_type_answer"]

    assert final.get("offer_type") == noun, (
        f"[{branch}] offer_type {final.get('offer_type')!r} must equal {noun!r}"
    )
    assert final.get("confirmed") is True, f"[{branch}] flow never confirmed"

    desc = (final.get("offer_description") or "").strip()
    assert desc, f"[{branch}] offer_description empty"
    assert desc.lower() not in ("none", "n/a", "unknown"), (
        f"[{branch}] placeholder description leaked through: {desc!r}"
    )
    assert desc.lower() != final.get("offer_name", "").lower(), (
        f"[{branch}] description is just a repeat of the offer name: {desc!r}"
    )

    for key in ("target_market", "features", "service_uniqueness"):
        value = final.get(key)
        assert isinstance(value, list), f"[{branch}] {key} is not a list: {value!r}"

    # Every interrupt that fired was answered, and the answer is in BOTH the
    # follow_up trail and the message history.
    replies = list(as_follow_up(final.get("follow_up")).user_replies or [])
    for entry in interrupt_log:
        assert entry["answer"] in replies, (
            f"[{branch}] answer {entry['answer']!r} for {entry['type']} missing from "
            f"follow_up.user_replies {replies}"
        )
    contents = [str(m.content) for m in (final.get("messages") or []) if hasattr(m, "content")]
    for entry in interrupt_log:
        assert any(entry["answer"] in c for c in contents), (
            f"[{branch}] answer {entry['answer']!r} for {entry['type']} missing from messages"
        )


def _print_intake_report(branch: str, final: dict, timings: dict, interrupt_log: list[dict]) -> None:
    print(f"\n=== discover_offer: {branch} (offer_type={final.get('offer_type')}) ===")
    print(f"  description ({len((final.get('offer_description') or '').split())} words): {final.get('offer_description')}")
    print(f"  target_market: {final.get('target_market')}")
    print(f"  features: {final.get('features')} | service_uniqueness: {final.get('service_uniqueness')}")
    print(f"  problem: {final.get('problem')}")
    print(f"  interrupts answered: {[(e['type'], e['answer']) for e in interrupt_log]}")
    for node in (
        "scrape_website", "check_product_service_exist", "determine_offer_type",
        "get_product_service_description", "ask_for_confirmation",
        "retrieve_rest_product_service_info",
    ):
        if node in timings:
            print(f"  {node:36s} {timings[node]:6.1f}s")
    print(f"  {'total':36s} {timings['_total']:6.1f}s")


def _save_artifacts(branch: str, final: dict, timings: dict, interrupt_log: list[dict]) -> None:
    _OUT_DIR.mkdir(parents=True, exist_ok=True)
    (Path(_OUT_DIR) / f"{branch}_final_state.json").write_text(
        json.dumps(_jsonable(final), indent=2), encoding="utf-8"
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
            "run_log_tag": "discover_offer",
            "branch": branch,
            "offer_type": final.get("offer_type"),
            "confirmed": final.get("confirmed"),
            "offer_description_words": len((final.get("offer_description") or "").split()),
            "target_market": final.get("target_market"),
            "features": final.get("features"),
            "service_uniqueness": final.get("service_uniqueness"),
            "interrupts": [e["type"] for e in interrupt_log],
            "stages_seconds": timings,
        }
    )
    log_path.write_text(json.dumps(log, indent=2), encoding="utf-8")


def _run_and_assert(branch: str) -> None:
    final, timings, interrupt_log = _run_intake(branch)
    # Save and print first: a failing run must still leave its state behind, or
    # the failure is undiagnosable from the assert message.
    _save_artifacts(branch, final, timings, interrupt_log)
    _print_intake_report(branch, final, timings, interrupt_log)
    _assert_intake_run(branch, final, interrupt_log)


def test_discover_offer_product() -> None:
    _run_and_assert("product")


def test_discover_offer_service() -> None:
    _run_and_assert("service")


def main() -> None:
    """Run one or both branches, then the cumulative LLM timing report."""
    print("Real offer-intake run (real LLM + real website scrape, nothing stubbed)")
    branches = tuple(BRANCHES) if len(sys.argv) < 2 else (sys.argv[1],)
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
    print("\nCumulative LLM wall clock (all branches):")
    print(llm_timing_report())
    if failed:
        sys.exit(1)


if __name__ == "__main__":
    main()