"""
End-to-end test of the interactive offer-intake subgraph with REAL LLM calls and
REAL website scraping (nothing stubbed).

The intake pipeline is interactive, so this is the one pipelines test that
DRIVES INTERRUPTS: it streams the graph, auto-answers every interrupt from a
type-keyed table (the same table test_gtmx_agent.py uses), and resumes with
Command(resume=...) and the same thread config until the flow completes.

Each branch pays for:
  - 1 description-draft call (get_product_service_description)
  - 1 rest-extraction call (retrieve_rest_product_service_info)
plus a real website scrape when the fixture carries a website_url.

`offer_type` is asserted by the caller and seeded into the session up front (the
intake form owns it; the agent no longer classifies it), so the harness feeds
each branch's type directly, exactly as `_build_initial_state` does. Asserting
the type still round-trips through the run is the point — it rides the session
untouched all the way to the specialists downstream.

Branches:
  - product:  real scrape of https://aphorion.co/ (HeatherDB is named on the
              page, so the name-existence gate passes) -> draft, confirm.
  - service:  real scrape of https://thoughtbot.com/ (a real design and
              development agency) -> draft, confirm. The name gate passes on the
              agency's own name and the scraped copy gives the extraction step
              genuine material, so this branch actually exercises the service
              path instead of running on an empty page.

Run all branches:
    python agents/tests/pipelines/test_discover_offer.py
Run one branch:
    python agents/tests/pipelines/test_discover_offer.py product
Under pytest:
    pytest -m live agents/tests/pipelines/test_discover_offer.py

Assertions are invariants, not exact text (LLM output is nondeterministic): the
flow reached the end, the seeded offer_type survived the run, confirmed is True,
the description is real prose (no 'None'/'N/A' placeholders), the extraction
fields are the right shapes, and every interrupt that fired was auto-answered
and recorded in follow_up.user_replies AND messages. Failures name the offender.
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
from agents.pipelines.discover.discover_offer import build_offer_discovery_graph  # noqa: E402
from langgraph.types import Command  # noqa: E402
import pytest

# Real LLM + web calls: opt-in with `uv run pytest -m live`.
pytestmark = pytest.mark.live

_OUT_DIR = Path(__file__).resolve().parent / "_out" / "discover_offer"


# ---------------------------------------------------------------------------
# Fixtures. Both branches drive a real scrape, so each has genuine material for
# the extraction step to work from. `offer_type` is an input here — asserted by
# the caller and carried on the session — not something the graph is expected to
# decide.
#
# `description` is what a user would supply if the agent asks what the offer is
# and has nothing to draft from. With a scrape that works the agent drafts its
# own and this is never consulted, so it stays None; _answer_for only reaches for
# it on an empty-draft confirmation, where answering "yes" would strand the run.
# ---------------------------------------------------------------------------

PRODUCT_OFFER = {
    "offer_name": "HeatherDB",
    "website_url": "https://aphorion.co/",
    "offer_type": "product",
    "description": None,
}

# thoughtbot is a real design and development agency. Its own name appears in the
# scraped copy, so the name-existence gate passes on the agency's actual identity
# rather than on a lucky substring, and the page carries enough prose for
# retrieve_rest_product_service_info to extract real features and problems.
SERVICE_OFFER = {
    "offer_name": "thoughtbot",
    "website_url": "https://thoughtbot.com/",
    "offer_type": "service",
    "description": None,
}

BRANCHES = {"product": PRODUCT_OFFER, "service": SERVICE_OFFER}


# ---------------------------------------------------------------------------
# Runner: stream through the compiled graph, answering interrupts by type.
# ---------------------------------------------------------------------------


def _answer_for(payload: dict, branch: str) -> str:
    """Map an interrupt payload to a deterministic reply (mirrors
    test_gtmx_agent.py's resolve_answer)."""
    ptype = (payload or {}).get("type")

    # A confirmation interrupt with no draft isn't a confirmation at all — the
    # agent has nothing to draft from and is asking what the offer is. Answering
    # "yes" there strands the run, so supply the branch's description instead.
    if ptype == "product_service_description_confirmation" and not payload.get("draft"):
        return BRANCHES[branch]["description"] or "yes"

    auto = {
        "offer_name_mismatch": "1",          # pick the first candidate found
        "url_unscrappable": "continue",      # work from the name/description
        "product_service_description_confirmation": "yes",
    }
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
        # Seeded the way _build_initial_state seeds it, so the run exercises the
        # same path the intake form drives in production.
        "offer_type": offer["offer_type"],
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
    noun = BRANCHES[branch]["offer_type"]

    # Nothing writes offer_type any more, so this is purely a passthrough check:
    # the seeded value has to survive every node untouched, because
    # create_specialists reads it off the same session.
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

    # With a usable scrape, the extraction step must return *something* real, not
    # a silent empty. Features vs service_uniqueness differ by type, so assert the
    # branch-appropriate one is non-empty and the others are well-shaped lists.
    if noun == "product":
        feats = final.get("features") or []
        assert isinstance(feats, list), f"[{branch}] features is not a list: {feats!r}"
        assert feats, f"[{branch}] features must be non-empty for a real product scrape"
        uniq = final.get("service_uniqueness") or []
        assert isinstance(uniq, list), f"[{branch}] service_uniqueness is not a list: {uniq!r}"
    else:  # service
        uniq = final.get("service_uniqueness") or []
        assert isinstance(uniq, list), f"[{branch}] service_uniqueness is not a list: {uniq!r}"
        assert uniq, f"[{branch}] service_uniqueness must be non-empty for a real service scrape"
        feats = final.get("features") or []
        assert isinstance(feats, list), f"[{branch}] features is not a list: {feats!r}"

    for key in ("target_market", "problem", "how_it_works"):
        v = final.get(key)
        if key in ("problem", "how_it_works"):
            assert v, f"[{branch}] {key} must be non-empty for a real scrape"
            continue
        assert isinstance(v, list), f"[{branch}] {key} is not a list: {v!r}"

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
        "scrape_website", "check_product_service_exist", "proceed_to_description",
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


def _run_and_assert_with_fixture(offer: dict, label: str = "cli") -> None:
    """Run a single offer through the real intake graph.

    This is the same runner as _run_and_assert, just with an explicit offer dict
    instead of a branch name so the CLI can drive arbitrary inputs."""
    graph = build_offer_discovery_graph()  # checkpointer=True -> MemorySaver
    thread_id = uuid.uuid4().hex
    config = {"configurable": {"thread_id": thread_id}}

    initial = {
        "offer_name": offer["offer_name"],
        "website_url": offer["website_url"],
        "offer_type": offer["offer_type"],
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
        answer = _answer_for_with_offer(payload, offer)
        interrupt_log.append(
            {"type": payload.get("type"), "answer": answer, "question": payload.get("question")}
        )
        print(f"  [interrupt] {payload.get('type')} -> {answer!r}")

        state = Command(resume=answer)

    timings["_total"] = time.perf_counter() - started
    final = graph.get_state(config).values

    # Save and print first: a failing run must still leave its state behind, or
    # the failure is undiagnosable from the assert message.
    _save_artifacts(label, final, timings, interrupt_log)
    _print_intake_report(label, final, timings, interrupt_log)
    _assert_intake_run_with_offer(label, final, interrupt_log, offer)


def _answer_for_with_offer(payload: dict, offer: dict) -> str:
    ptype = (payload or {}).get("type")

    if ptype == "product_service_description_confirmation" and not payload.get("draft"):
        return offer["description"] or "yes"

    auto = {
        "offer_name_mismatch": "1",
        "url_unscrappable": "continue",
        "product_service_description_confirmation": "yes",
    }
    return auto.get(ptype, "yes")


def _assert_intake_run_with_offer(label: str, final: dict, interrupt_log: list[dict], offer: dict) -> None:
    noun = offer["offer_type"]

    # Terminal failure path: the URL was unscrappable. No description or extraction.
    if interrupt_log and interrupt_log[0]["type"] == "url_unscrappable":
        assert not final.get("confirmed"), f"[{label}] confirmed should not be True after unscrappable URL"
        assert final.get("scrape_failed") is True, f"[{label}] scrape_failed should be True"
        return

    assert final.get("offer_type") == noun, (
        f"[{label}] offer_type {final.get('offer_type')!r} must equal {noun!r}"
    )
    assert final.get("confirmed") is True, f"[{label}] flow never confirmed"

    desc = (final.get("offer_description") or "").strip()
    assert desc, f"[{label}] offer_description empty"
    assert desc.lower() not in ("none", "n/a", "unknown"), (
        f"[{label}] placeholder description leaked through: {desc!r}"
    )

    if noun == "product":
        feats = final.get("features") or []
        assert isinstance(feats, list), f"[{label}] features is not a list: {feats!r}"
        assert feats, f"[{label}] features must be non-empty for a real product scrape"
        uniq = final.get("service_uniqueness") or []
        assert isinstance(uniq, list), f"[{label}] service_uniqueness is not a list: {uniq!r}"
    else:
        uniq = final.get("service_uniqueness") or []
        assert isinstance(uniq, list), f"[{label}] service_uniqueness is not a list: {uniq!r}"
        assert uniq, f"[{label}] service_uniqueness must be non-empty for a real service scrape"
        feats = final.get("features") or []
        assert isinstance(feats, list), f"[{label}] features is not a list: {feats!r}"

    for key in ("target_market", "problem", "how_it_works"):
        v = final.get(key)
        if key in ("problem", "how_it_works"):
            assert v, f"[{label}] {key} must be non-empty for a real scrape"
            continue
        assert isinstance(v, list), f"[{label}] {key} is not a list: {v!r}"

    replies = list(as_follow_up(final.get("follow_up")).user_replies or [])
    for entry in interrupt_log:
        assert entry["answer"] in replies, (
            f"[{label}] answer {entry['answer']!r} for {entry['type']} missing from "
            f"follow_up.user_replies {replies}"
        )
    contents = [str(m.content) for m in (final.get("messages") or []) if hasattr(m, "content")]
    for entry in interrupt_log:
        assert any(entry["answer"] in c for c in contents), (
            f"[{label}] answer {entry['answer']!r} for {entry['type']} missing from messages"
        )


def main() -> None:
    """Run one or both branches, then the cumulative LLM timing report."""
    print("Real offer-intake run (real LLM + real website scrape, nothing stubbed)")

    if len(sys.argv) >= 4:
        offer = {
            "offer_name": sys.argv[1],
            "website_url": sys.argv[2],
            "offer_type": sys.argv[3],
            "description": sys.argv[4] if len(sys.argv) >= 5 else None,
        }
        try:
            _run_and_assert_with_fixture(offer, label="cli")
        except Exception:
            import traceback

            traceback.print_exc()
            sys.exit(1)
        print("\nCumulative LLM wall clock:")
        print(llm_timing_report())
        return

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
    print("\nCumulative LLM wall clock (all branches):")
    print(llm_timing_report())
    if failed:
        sys.exit(1)

if __name__ == "__main__":
    main()
