"""
Scripted, real-LLM driver for the discover_product2 subgraph.

Rebuilds the production discovery flow (scrape -> existence check -> description
draft -> confirmation -> inline check -> rest-of-product extraction) and drives
it headless with pre-scripted human answers, exercising edge cases against live
scraped content (aphorion.co) with real LLM calls.

Usage:
    python agents/tests/test_discover_product2.py                 # run all scenarios
    python agents/tests/test_discover_product2.py <scenario>      # run one scenario
    python agents/tests/test_discover_product2.py --interactive   # fall back to input() when scripted answers run out
"""
import re
import sys
import time
import uuid
from pathlib import Path

# Walk up from cwd to find project root (has pyproject.toml)
root = Path.cwd()
while root != root.parent:
    if (root / "pyproject.toml").exists():
        break
    root = root.parent

sys.path.insert(0, str(root))

from langgraph.types import Command

from agents.states import OfferDataSnapshot
from agents.sub_graphs.discover_product_service import build_discovery_agent
from agents.helpers import as_follow_up

APPHORION = "https://aphorion.co/"


def norm(s):
    return re.sub(r"[^a-z0-9]", "", (s or "").lower())


# ---------------------------------------------------------------------------
# Scenario runner
# ---------------------------------------------------------------------------

def run_scenario(name, product_name, product_url, snapshot_extra=None, scripted=None, offer_type_answer="product"):
    snapshot_extra = snapshot_extra or {}
    scripted = list(scripted or [])
    # Answers keyed by interrupt type are used FIRST when that interrupt fires —
    # so an unexpected offer_type_clarification can be answered without shifting
    # the scripted answers meant for the expected protocol.
    offer_by_type = {"offer_type_clarification": offer_type_answer} if offer_type_answer else {}
    interactive = "--interactive" in sys.argv

    snapshot = OfferDataSnapshot(
        offer_name=product_name,
        website_url=product_url,
        **snapshot_extra,
    )
    initial = {"offer_snapshot": snapshot}
    config = {"configurable": {"thread_id": str(uuid.uuid4())}}

    print(f"\n{'='*70}\nScenario: {name}\n  name={product_name!r} url={product_url!r} extra={snapshot_extra or {}}\n  answers={scripted}")
    print(f"{'-'*70}")

    agent = build_discovery_agent()
    interrupt_types = []
    candidates_seen = []
    questions = []
    start = time.time()

    result = agent.invoke(initial, config)
    while result.get("__interrupt__"):
        payload = result["__interrupt__"][0].value
        itype = payload.get("type")
        question = payload.get("question")
        draft = payload.get("draft")
        candidates = list(payload.get("product_candidates") or [])

        interrupt_types.append(itype)
        candidates_seen.append(candidates)
        questions.append(question)

        print(f"[interrupt {len(interrupt_types)}] type={itype}")
        if question:
            print(f"  Q: {question}")
        if draft:
            print(f"     draft: {draft}")
        if candidates:
            for i, c in enumerate(candidates, 1):
                print(f"     {i}. {c}")

        answer = offer_by_type.get(itype)
        if answer is None and scripted:
            answer = scripted.pop(0) if scripted else None
        if answer is None and interactive:
            answer = input("  ANSWER >> ")
        if answer is None:
            print("  [!!] ran out of scripted answers")
            break
        print(f"  A: {answer}")

        result = agent.invoke(Command(resume=answer), config)

    snapshot_final = result.get("offer_snapshot")
    follow_up = as_follow_up(result.get("follow_up"))
    elapsed = time.time() - start

    results = {
        "name": getattr(snapshot_final, "offer_name", None),
        "url": getattr(snapshot_final, "website_url", None),
        "description": getattr(snapshot_final, "offer_description", None),
        "intent": getattr(snapshot_final, "intent", None),
        "geo": list(getattr(snapshot_final, "target_geo", None) or []),
        "problem_solved": getattr(snapshot_final, "problem_solved", None),
        "features": list(getattr(snapshot_final, "features", None) or []),
        "service_uniqueness": list(getattr(snapshot_final, "service_uniqueness", None) or []),
        "how_it_works": getattr(snapshot_final, "how_it_works", None),
        "confirmed": bool(result.get("confirmed")),
        "offer": result.get("offer"),
        "name_mismatch_flagged": bool(result.get("name_mismatch")),
        "user_replies": list(follow_up.user_replies or []),
        "scraped_content_len": len(result.get("scraped_content") or "") if result.get("scraped_content") else 0,
        "interrupt_types": interrupt_types,
        "candidates_seen": candidates_seen,
        "questions": questions,
        "elapsed": elapsed,
        "completed": not result.get("__interrupt__"),
    }

    print(f"{'-'*70}")
    print(f"[done] confirmed={results['confirmed']} offer={results['offer']} interrupts={len(interrupt_types)} elapsed={elapsed:.1f}s")
    print(f"  name         : {results['name']}")
    print(f"  url          : {results['url']}")
    print(f"  offer        : {results['offer']}")
    print(f"  description  : {results['description']}")
    print(f"  intent       : {results['intent']}")
    print(f"  target_geo   : {results['geo']}")
    print(f"  problem_solved: {results['problem_solved']}")
    print(f"  how_it_works : {results['how_it_works']}")
    print(f"  features     : {len(results['features'])}")
    for f in results["features"]:
        print(f"    - {f.name}: {f.description or ''}"
              + (f" (differentiator: {f.differentiator})" if f.differentiator else ""))
    print(f"  service_uniqueness: {len(results['service_uniqueness'])}")
    for f in results["service_uniqueness"]:
        print(f"    - {f.name}: {f.description or ''}"
              + (f" (differentiator: {f.differentiator})" if f.differentiator else ""))
    print(f"  scraped_content_len: {results['scraped_content_len']}")
    return results


# ---------------------------------------------------------------------------
# Checks
# ---------------------------------------------------------------------------

def check(label, cond):
    return (label, bool(cond))


def common_checks(r):
    return [
        check("completed without interrupt", r["completed"]),
        check("confirmed", r["confirmed"]),
        check("description non-empty", bool(r["description"])),
    ]


def anti_hallucination_checks(r, hallucinated=("aphorionlabs", "raspberrypi"), real_products=("heatherdb", "cloudofassociations")):
    """On a name mismatch the offered candidates must actual products of the
    site — never the organization itself, hardware it runs on, or other
    hallucinated names scraped from the page. Uses the first interrupt that
    actually carried candidates (mismatch interrupts), skipping earlier
    interrupts like url_unscrappable that carry none."""
    first_candidates = next((c for c in r["candidates_seen"] if c), [])
    norms = {norm(c) for c in first_candidates}
    bad = [n for n in norms for h in hallucinated if h in n]
    return [
        check("no hallucinated candidates (company/hardware)", not bad),
        check("candidates are real products of the site",
              bool(norms) and norms <= set(real_products)),
    ]


def scenario_checks(name, r):
    """Return (label, ok) pairs evaluating the run's results."""
    checks = common_checks(r)

    if name == "happy_heatherdb":
        checks += [
            check("name preserved as HeatherDB", norm(r["name"]) == "heatherdb"),
            check("offer classified as product", r["offer"] == "product"),
            check("no product features leaked into service_uniqueness", len(r["service_uniqueness"]) == 0),
            check("scraped content present", r["scraped_content_len"] > 500),
        ]
    elif name == "happy_coa":
        checks += [
            check("name mentions Cloud of Associations", "cloudofassociations" in norm(r["name"]) or "association" in norm(r["name"])),
            check("description mentions associations/intuition/logic",
                  any(w in norm(r["description"]) for w in ("association", "intuition", "logic", "creative", "lateral"))),
        ]
    elif name == "mismatch_pick_number":
        first_candidates = r["candidates_seen"][0] if r["candidates_seen"] else []
        resolved_ok = bool(first_candidates) and \
            norm(r["name"]) in {norm(c) for c in first_candidates}
        checks += [
            check("first interrupt is name mismatch",
                  bool(r["interrupt_types"]) and r["interrupt_types"][0] == "offer_name_mismatch"),
            check("offer classified as product", r["offer"] == "product"),
            check("candidates offered", len(first_candidates) >= 1),
            check("resolved name is one of offered candidates", resolved_ok),
        ] + anti_hallucination_checks(r)
    elif name == "mismatch_pick_name":
        checks += [
            check("first interrupt is name mismatch",
                  bool(r["interrupt_types"]) and r["interrupt_types"][0] == "offer_name_mismatch"),
            check("resolved name is HeatherDB", "heatherdb" in norm(r["name"])),
        ] + anti_hallucination_checks(r)
    elif name == "edit_fold":
        checks += [
            check("re-confirm happened (>=2 interrupts)", len(r["interrupt_types"]) >= 2),
            check("revised description mentions Raspberry Pi", "raspberrypi" in norm(r["description"])),
        ]
    elif name == "non_grounded_edit":
        checks += [
            check("note loop happened (>=3 interrupts)", len(r["interrupt_types"]) >= 3),
            check("fabricated 'free money' claim dropped", "freemoney" not in norm(r["description"])),
        ]
    elif name == "geo_user_priority":
        checks += [
            check("user-stated geo wins", set(r["geo"]) == {"Kenya", "Uganda"}),
        ]
    elif name == "geo_scraped_inference":
        joined = norm(" ".join(r["geo"]))
        checks += [
            check("target_geo inferred from content", len(r["geo"]) > 0),
            check("inferred geo is Africa/Kenya/Nairobi",
                  any(w in joined for w in ("kenya", "nairobi", "africa"))),
        ]
    elif name == "no_info_ask":
        checks += [
            check("first interrupt asks for product info",
                  bool(r["questions"]) and "tellmeabout" in norm(r["questions"][0])),
            check("no scrape attempted", r["scraped_content_len"] == 0),
            check("description reflects user's words",
                  any(w in norm(r["description"]) for w in ("hivedb", "balloon", "datalake"))),
        ]
    elif name == "dead_url":
        checks += [
            check("agent told the user the URL was unscrappable",
                  bool(r["interrupt_types"]) and r["interrupt_types"][0] == "url_unscrappable"),
            check("agent recovered after unscrappable URL (>=2 interrupts)", len(r["interrupt_types"]) >= 2),
            check("no scraped content", r["scraped_content_len"] == 0),
        ]
    elif name == "corrected_url":
        checks += [
            check("first interrupt told the user the URL was unscrappable",
                  bool(r["interrupt_types"]) and r["interrupt_types"][0] == "url_unscrappable"),
            check("corrected URL baked into snapshot", norm(r["url"]) == norm(APPHORION)),
            check("re-gathered corrected URL", r["scraped_content_len"] > 500),
            check("name mismatch offered candidates on second pass",
                  "offer_name_mismatch" in r["interrupt_types"]),
            check("offer classified as product", r["offer"] == "product"),
        ] + anti_hallucination_checks(r)
    elif name == "free_text_clarification":
        first_candidates = r["candidates_seen"][0] if r["candidates_seen"] else []
        checks += [
            check("first interrupt is name mismatch",
                  bool(r["interrupt_types"]) and r["interrupt_types"][0] == "offer_name_mismatch"),
            check("example.com yields no candidate products", len(first_candidates) == 0),
            check("description reflects user's free-text clarification",
                  any(w in norm(r["description"]) for w in ("hivedb", "offline", "datalake"))),
        ]
    elif name == "service_ambiguous_3d_printing":
        checks += [
            check("agent asked for offer type first (clarify interrupt)",
                  bool(r["interrupt_types"]) and r["interrupt_types"][0] == "offer_type_clarification"),
            check("offer classified as service", r["offer"] == "service"),
            check("no product features populated for a service", len(r["features"]) == 0),
        ]
    elif name == "service_confident_shapeways":
        checks += [
            check("no offer-type clarify interrupt (classified confidently from content)",
                  "offer_type_clarification" not in r["interrupt_types"]),
            check("offer classified as service", r["offer"] == "service"),
            check("no product features populated for a service", len(r["features"]) == 0),
        ]
    return checks


# ---------------------------------------------------------------------------
# Scenario registry
# ---------------------------------------------------------------------------

SCENARIOS = [
    dict(
        name="happy_heatherdb",
        product_name="HeatherDB",
        product_url=APPHORION,
        scripted=["yes"],
        description="Product name matches the page; straight confirm path.",
    ),
    dict(
        name="happy_coa",
        product_name="Cloud of Associations",
        product_url=APPHORION,
        scripted=["yes"],
        description="Second product on the same page; straight confirm path.",
    ),
    dict(
        name="mismatch_pick_number",
        product_name="KlingonDB",
        product_url=APPHORION,
        scripted=["1", "yes"],
        description="Fictional product not on the page; user picks candidate #1.",
    ),
    dict(
        name="mismatch_pick_name",
        product_name="KlingonDB",
        product_url=APPHORION,
        scripted=["HeatherDB", "yes"],
        description="Fictional product not on the page; user types the real name.",
    ),
    dict(
        name="edit_fold",
        product_name="HeatherDB",
        product_url=APPHORION,
        scripted=["emphasize it runs on a Raspberry Pi", "yes"],
        description="Grounded edit should be folded into the description via inline check.",
    ),
    dict(
        name="non_grounded_edit",
        product_name="HeatherDB",
        product_url=APPHORION,
        scripted=["say it gives users free money", "drop the 'free money' claim, keep it accurate", "yes"],
        description="Fabricated edit rejected with a note; loop re-confirms.",
    ),
    dict(
        name="geo_user_priority",
        product_name="HeatherDB",
        product_url=APPHORION,
        snapshot_extra={"target_geo": ["Kenya", "Uganda"]},
        scripted=["yes"],
        description="User-provided geo must win over scraped inference.",
    ),
    dict(
        name="geo_scraped_inference",
        product_name="HeatherDB",
        product_url=APPHORION,
        scripted=["yes"],
        description="No user geo -> inferred from scraped content (Kenya/Africa).",
    ),
    dict(
        name="no_info_ask",
        product_name=None,
        product_url=None,
        scripted=["It is called HiveDB, an offline data lake for balloons.", "yes"],
        description="No name/no URL initially; agent must ask the user.",
    ),
    dict(
        name="dead_url",
        product_name="HeatherDB",
        product_url="https://zz-void-domain-nowhere.invalid/",
        scripted=["It is HiveDB, an offline data lake for balloons.", "yes"],
        offer_type_answer="product",
        description="Scrape fails -> agent interrupts and tells the user the URL failed, then proceeds.",
    ),
    dict(
        name="corrected_url",
        product_name="HiveDB",
        product_url="https://zz-void-domain-nowhere.invalid/",
        scripted=["https://aphorion.co/", "1", "yes"],
        description="Dead URL -> user supplies a working URL -> re-scraped exactly as given, normal flow resumes.",
    ),
    dict(
        name="free_text_clarification",
        product_name="KlingonDB",
        product_url="https://example.com/",
        scripted=["It is HiveDB, an offline data lake.", "yes"],
        offer_type_answer="product",
        description="Non-existent product; user clarifies the product in free text (cannot be name-matched to candidates).",
    ),
    dict(
        name="service_ambiguous_3d_printing",
        product_name="3D Printing",
        product_url=None,
        scripted=["yes"],
        offer_type_answer="it is a service that prints custom 3D parts for customers",
        description="Ambiguous offer (3D printing) with no URL: agent must ask via ask_for_offer_clarity.",
    ),
    dict(
        name="service_confident_shapeways",
        product_name="Shapeways",
        product_url="https://www.shapeways.com/",
        scripted=["yes"],
        offer_type_answer="service",
        description="On-demand 3D-printing service with real content: agent classifies as service without asking.",
    ),
]


def main():
    want = None
    interactive = "--interactive" in sys.argv
    if len(sys.argv) > 1 and not interactive:
        want = sys.argv[1]

    selected = [s for s in SCENARIOS if want is None or s["name"] == want]
    if not selected:
        print(f"Unknown scenario: {want}")
        print("Available:", ", ".join(s['name'] for s in SCENARIOS))
        return

    print(f"discover_product2 real-LLM scenario driver")
    print(f"Running {len(selected)} scenario(s)...")

    passed, failed, errored = [], [], []
    for scenario in selected:
        print(f"\n--- {scenario['description']} ---")
        try:
            r = run_scenario(**{k: v for k, v in scenario.items() if k != "description"})
            lab_checks = scenario_checks(scenario["name"], r)
        except Exception as e:
            import traceback
            traceback.print_exc()
            errored.append((scenario["name"], str(e)))
            print(f"  RESULT: ERROR ({e})")
            continue

        ok_labels = [label for label, ok in lab_checks if ok]
        bad = [(label, ok) for label, ok in lab_checks if not ok]
        print(f"  RESULT: {'PASS' if not bad else 'FAIL'} ({len(ok_labels)}/{len(lab_checks)} checks)")
        for label, ok in lab_checks:
            print(f"    [{'OK' if ok else 'XX'}] {label}")
        (passed if not bad else failed).append(scenario["name"])

    print(f"\n{'='*70}\nSUMMARY")
    for p in passed:
        print(f"  PASS  {p}")
    for f in failed:
        print(f"  FAIL  {f}")
    for e, msg in errored:
        print(f"  ERROR {e}: {msg}")
    print(f"  -> passed={len(passed)} failed={len(failed)} errored={len(errored)}")


if __name__ == "__main__":
    main()