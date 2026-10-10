"""
End-to-end test of the MANUAL (no-website) offer-intake subgraph with REAL LLM
calls (nothing stubbed).

The manual path has no scrape: the user's description on the intake form is the
only evidence. It runs the same rest-extraction call as the web path and may
interrupt once to ask for what's missing.

Branches:
  - product: thin description (missing problem/how_it_works) -> expect the
             offer_details_followup interrupt, answered with real details.
  - service: thin description -> interrupt answered with "skip", so the run
             must still finish with confirmed=True and well-shaped (possibly
             empty) extraction fields.
  - rich:    a complete description -> extraction should produce enough that
             NO interrupt fires at all.

Run: python agents/tests/sub_agents/test_discover_offer_manual.py
Under pytest: pytest agents/tests/sub_agents/test_discover_offer_manual.py
"""

import json
import sys
import time
import uuid
from pathlib import Path

from pydantic import BaseModel

root = Path.cwd()
while root != root.parent:
    if (root / "pyproject.toml").exists():
        break
    root = root.parent
sys.path.insert(0, str(root))

from agents.helpers import as_follow_up  # noqa: E402
from agents.llm.main import llm_timing_report  # noqa: E402
from agents.sub_agents.discover.discover_offer_manual import (  # noqa: E402
    build_manual_offer_discovery_graph,
)
from langgraph.types import Command  # noqa: E402

_OUT_DIR = Path(__file__).resolve().parent / "_out" / "discover_offer_manual"


PRODUCT_THIN = {
    "offer_name": "HeatherDB",
    "offer_type": "product",
    "target_geo": ["Kenya"],
    "offer_description": (
        "HeatherDB is a mobile database app for small retailers in East Africa "
        "that need to track stock without a computer."
    ),
}

SERVICE_THIN = {
    "offer_name": "thoughtbot",
    "offer_type": "service",
    "target_geo": ["United States"],
    "offer_description": (
        "thoughtbot is a design and development agency that builds web and "
        "mobile products for startups."
    ),
}

PRODUCT_RICH = {
    "offer_name": "HeatherDB",
    "offer_type": "product",
    "target_geo": ["Kenya"],
    "offer_description": (
        "HeatherDB is a mobile database app for small retailers in East Africa. "
        "It solves the problem of losing stock records when keeping them in "
        "notebooks. Retailers use it to record sales and stock levels on their "
        "phone and get simple reports. Its main features are offline-first "
        "storage, low-data USSD mode for basic phones, and one-tap stock "
        "reports. It works end-to-end by syncing phone records to the cloud "
        "when data is available."
    ),
}

BRANCHES = {"product": PRODUCT_THIN, "service": SERVICE_THIN, "rich": PRODUCT_RICH}


def _answer_for(payload: dict, branch: str) -> str:
    ptype = (payload or {}).get("type")
    auto = {
        "offer_details_followup": (
            "It solves the problem of manual stock records getting lost. "
            "It works by recording sales on the phone and syncing to the cloud. "
            "Its main features are offline storage and one-tap reports."
            if branch == "product"
            else "skip"
        ),
    }
    return auto.get(ptype, "skip")


def _run_intake(branch: str) -> tuple[dict, dict, list[dict]]:
    offer = BRANCHES[branch]
    graph = build_manual_offer_discovery_graph()
    thread_id = uuid.uuid4().hex
    config = {"configurable": {"thread_id": thread_id}}

    initial = {
        "offer_name": offer["offer_name"],
        "website_url": "",
        "offer_type": offer["offer_type"],
        "offer_description": offer["offer_description"],
        "target_market": offer["target_geo"],
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

    timings["_total"] = time.perf_counter() - started
    final = graph.get_state(config).values
    return final, timings, interrupt_log


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


def _assert_run(branch: str, final: dict, interrupt_log: list[dict]) -> None:
    offer = BRANCHES[branch]
    kind = offer["offer_type"]

    assert final.get("offer_type") == kind, (
        f"[{branch}] offer_type {final.get('offer_type')!r} must equal {kind!r}"
    )
    assert final.get("confirmed") is True, f"[{branch}] flow never confirmed"
    assert list(final.get("target_market") or []) == offer["target_geo"], (
        f"[{branch}] target_market must carry the intake geo, got {final.get('target_market')!r}"
    )

    desc = (final.get("offer_description") or "").strip()
    assert desc and desc.lower() not in ("none", "n/a", "unknown"), (
        f"[{branch}] bad offer_description: {desc!r}"
    )

    # Well-shaped extraction output on every branch.
    feats = final.get("features") or []
    uniq = final.get("service_uniqueness") or []
    assert isinstance(feats, list) and isinstance(uniq, list), (
        f"[{branch}] features/service_uniqueness must be lists"
    )

    if branch == "product":
        # Thin description + a follow-up answer should yield real extraction.
        assert any(i["type"] == "offer_details_followup" for i in interrupt_log), (
            f"[{branch}] expected the offer_details_followup interrupt"
        )
        assert feats, f"[{branch}] features should be non-empty after the follow-up answer"
        assert final.get("problem"), f"[{branch}] problem should be extracted"

    if branch == "service":
        # "skip" must not strand the run and must not fabricate a follow-up.
        assert any(i["type"] == "offer_details_followup" for i in interrupt_log), (
            f"[{branch}] expected the offer_details_followup interrupt"
        )
        assert any(i["answer"] == "skip" for i in interrupt_log), (
            f"[{branch}] skip answer must be honored"
        )

    if branch == "rich":
        # A complete description should need zero interrupts.
        assert not interrupt_log, f"[{branch}] complete description should not interrupt: {interrupt_log!r}"
        assert final.get("problem"), f"[{branch}] problem should be extracted from a rich description"
        assert feats or uniq, f"[{branch}] features/service_uniqueness should be non-empty"


def _write_artifact(branch: str, final: dict, timings: dict, interrupt_log: list[dict]) -> None:
    _OUT_DIR.mkdir(parents=True, exist_ok=True)
    artifact = {
        "branch": branch,
        "interrupts": interrupt_log,
        "timings_s": {k: round(v, 2) for k, v in timings.items()},
        "final": {k: _jsonable(v) for k, v in final.items() if k != "messages"},
    }
    path = _OUT_DIR / f"{branch}.json"
    path.write_text(json.dumps(artifact, indent=2, default=str))
    print(f"  wrote {path}")


def run_branch(branch: str) -> None:
    print(f"== manual branch: {branch} ==")
    final, timings, interrupt_log = _run_intake(branch)
    _assert_run(branch, final, interrupt_log)
    _write_artifact(branch, final, timings, interrupt_log)
    print(f"  OK ({timings['_total']:.1f}s)")


def main() -> None:
    selected = sys.argv[1:] or list(BRANCHES)
    for branch in selected:
        if branch not in BRANCHES:
            raise SystemExit(f"unknown branch {branch!r}; choose from {sorted(BRANCHES)}")
        run_branch(branch)
    print(llm_timing_report())


if __name__ == "__main__":
    main()


def test_product_manual_intake():
    run_branch("product")


def test_service_manual_intake():
    run_branch("service")


def test_rich_manual_intake_no_interrupt():
    run_branch("rich")
