"""
Timed, scriptable end-to-end driver for the gtmx agent.

Run (auto mode, resumes discovery interrupts itself with sensible defaults):
    python agents/tests/test_gtmx_agent.py --name HeatherDB --url https://aphorion.co/

Flags:
    --interactive        Ask on every discovery interrupt instead of auto-answering.
    --stop-after product Dry-run: stop once understand_product completes (still
                         instances create_specialists + understand_product).
    --name NAME          Offer name to seed into the offer snapshot.
    --url URL            Website URL to scrape.
    --quiet              Suppress extra state printout.

Timing is captured per top-level node (discover_product_service, create_specialists,
understand_product, understand_market, understand_competition, determine_icp,
account_discovery) via stream_mode="debug", and LLM wall-time per model by wrapping
ChatQwen.invoke at the class level (covers with_structured_output + repair paths).
No production code changes.
"""
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

import agents.llm.main as llm_main  # noqa: E402
import agents.gtmx_agent as gtmx_agent  # noqa: E402
from langchain_qwq import ChatQwen  # noqa: E402
from agents.states import OfferSessionState, OfferDataSnapshot, FollowUp  # noqa: E402
from langgraph.types import Command  # noqa: E402


# ---------------------------------------------------------------------------
# LLM call/wall-time stats (class-level invoke wrapper; notes model per call)
# ---------------------------------------------------------------------------
llm_stats = {"calls": 0, "by_model": {}, "elapsed": 0.0}
_orig_chat_invoke = ChatQwen.invoke


def _timed_invoke(self, input, *args, **kwargs):
    t0 = time.monotonic()
    try:
        return _orig_chat_invoke(self, input, *args, **kwargs)
    finally:
        model = getattr(self, "model", "?")
        rec = llm_stats["by_model"].setdefault(model, {"calls": 0, "elapsed": 0.0})
        rec["calls"] += 1
        rec["elapsed"] += time.monotonic() - t0
        llm_stats["calls"] += 1
        llm_stats["elapsed"] += time.monotonic() - t0


ChatQwen.invoke = _timed_invoke

TOP_LEVEL_NODES = {
    "discover_product_service",
    "create_specialists",
    "understand_product",
    "understand_market",
    "understand_competition",
    "determine_icp",
    "account_discovery",
}

node_times = {}  # node -> {"start": t, "end": t} (first start / last end span)
pending_interrupt_value = None


def _fmt(seconds):
    m, s = divmod(int(seconds), 60)
    return f"{m}m {s:02d}s"


def resolve_answer(payload, interactive) -> str:
    """Map an interrupt payload to a reply, or ask the user when interactive."""
    ptype = (payload or {}).get("type")
    auto = {
        "offer_name_mismatch": "1",
        "url_unscrappable": "continue",
        "offer_type_clarification": "product",
        "product_service_description_confirmation": "yes",
    }
    if ptype in auto and not interactive:
        print(f"  [auto] {ptype} -> {auto[ptype]!r}")
        return auto[ptype]
    if interactive:
        print(f"\n🤖 __Agent__\n>> {payload.get('question', payload) or payload}")
        return input("🧔‍♂️ Answer >> ")
    print(f"  [auto-fallback] {payload or '<no payload>'!r} -> 'yes'")
    return "yes"


def run_stream(agent, initial_input, config, interactive):
    """Consume a stream until it ends or a node interrupts. Records per-node
    timing (first start -> last end). Sets pending_interrupt_value when a node
    interrupts."""
    global pending_interrupt_value
    pending_interrupt_value = None
    for chunk in agent.stream(initial_input, config, stream_mode="debug"):
        ev_type = chunk.get("type")
        if ev_type not in ("task", "task_result"):
            continue
        name = chunk.get("payload", {}).get("name")
        if name not in TOP_LEVEL_NODES:
            continue
        rec = node_times.setdefault(name, {"start": None, "end": None})
        if ev_type == "task":
            if rec["start"] is None:
                rec["start"] = time.monotonic()
        else:
            rec["end"] = time.monotonic()
            interrupts = chunk.get("payload", {}).get("interrupts") or []
            if interrupts:
                item = interrupts[0]
                value = item.get("value", item) if isinstance(item, dict) else getattr(item, "value", item)
                pending_interrupt_value = value
                ptype = value.get("type") if isinstance(value, dict) else value
                print(f"  [interrupt] {name} -> {ptype}")


def main():
    args = [a for a in sys.argv[1:]]
    interactive = "--interactive" in args
    quiet = "--quiet" in args
    stop_after = None
    if "--stop-after" in args:
        stop_after = args[args.index("--stop-after") + 1]

    def _val(flag, default):
        if flag in args and len(args) > args.index(flag) + 1:
            return args[args.index(flag) + 1]
        return default

    offer_name = _val("--name", "HeatherDB")
    website_url = _val("--url", "https://aphorion.co/")

    print("🚀Starting Agent (timed)\n")

    test_name = stop_after or "full"
    initial_state: OfferSessionState = {
        "offer": None,
        "offer_snapshot": OfferDataSnapshot(
            offer_name=offer_name,
            website_url=website_url,
        ),
        "messages": [],
        "follow_up": FollowUp(),
        "sections": [],
        "specilist_generation_complete": False,
        "product_complete": False,
        "competition_complete": False,
        "market_complete": False,
        "icp_complete": False,
        "gtm_complete": False,
    }

    try:
        print(f"🏃‍♂️Agent Running\n")
        session_id = str(uuid.uuid4())
        config = {"configurable": {"thread_id": session_id}}

        agent = gtmx_agent.build_agent()
        if stop_after == "product":
            agent.interrupt_before_nodes = ["understand_market"]
            print("  [dry-run] will pause after understand_product\n")

        input_to_agent = initial_state
        t_total = time.monotonic()
        while True:
            run_stream(agent, input_to_agent, config, interactive)
            if pending_interrupt_value is not None:
                answer = resolve_answer(pending_interrupt_value, interactive)
                input_to_agent = Command(resume=answer)
                continue
            break
        wall = time.monotonic() - t_total

        final = agent.get_state(config)
        values = final.values

        if not quiet:
            print(f"\n🏃 Stream done. Nodes timed: {sorted(k for k in node_times if node_times[k].get('end'))}")

        # --- Report ---
        print(f"\n🛑 Agent Completed\n")
        if not quiet:
            snapshot = values.get("offer_snapshot")
            if snapshot is not None:
                print(f"FINAL offer_snapshot:")
                print(f"  name       : {snapshot.offer_name}")
                print(f"  url        : {snapshot.website_url}")
                print(f"  description: {snapshot.offer_description}")

        print(f"\n⏱️  PHASE TIMING ({test_name} run, wall {_fmt(wall)}):")
        ordered = [
            "discover_product_service",
            "create_specialists",
            "understand_product",
            "understand_market",
            "understand_competition",
            "determine_icp",
            "write_sections",
            "account_discovery",
        ]
        tl = 0.0
        for n in ordered:
            rec = node_times.get(n)
            if rec and rec.get("start") and rec.get("end"):
                d = rec["end"] - rec["start"]
                tl += d
                print(f"  {n:<26} {d:6.1f}s   {_fmt(d)}")
            elif rec:
                print(f"  {n:<26}  (did not finish)")
        print(f"  {'TOTAL (nodes)':<26} {tl:6.1f}s   {_fmt(tl)}")

        print(f"\n🔢 LLM CALLS ({llm_stats['calls']} total, {_fmt(llm_stats['elapsed'])}):")
        for model, rec in sorted(llm_stats["by_model"].items(), key=lambda kv: -kv[1]["elapsed"]):
            avg = rec["elapsed"] / rec["calls"] if rec["calls"] else 0.0
            print(f"  {model:<28} {rec['calls']:>4} calls  {_fmt(rec['elapsed']):>8}   ({avg:.1f}s/call avg)")

        # --- Dry-run early exit ---
        if stop_after == "product":
            ok = bool(values.get("product_complete"))
            print("\n" + ("✅ DRY-RUN COMPLETE: paused after understand_product." if ok else "❌ DRY-RUN: product phase did not complete."))
            print(f"Product complete: {values.get('product_complete')}")
            print(f"Market complete: {values.get('market_complete')}")
            print(f"Next nodes: {list(final.next or [])}")
            return

        if not quiet:
            market_data = values.get("market_data")
            if market_data is not None:
                print(f"\nMARKET_DATA buyer type: {market_data.buyer_type}")

        icp = values.get("icp")
        if icp:
            print(f"\nICP: {icp.product_name} ({icp.buyer_type}) — personas: {len(icp.buyer_personas or [])}, channels: {len(icp.target_channels or [])}")

        accounts = values.get("accounts")
        if accounts:
            print(f"\nACCOUNTS ({len(accounts.accounts)}):")
            for acc in accounts.accounts:
                trigger = acc.trigger_event.signal_type if acc.trigger_event else "none"
                print(f"  - {acc.name} [{acc.account_type or 'company'} | {trigger}] {acc.geo or '?'} score={acc.score}")

        flags = {f: values.get(f) for f in ("product_complete", "market_complete", "competition_complete", "icp_complete", "gtm_complete")}
        print(f"\nFlags -> " + " ".join(f"{k.split('_')[0]}:{v}" for k, v in flags.items()))

        # --- Report sections ---
        # One writer composes all three at the end, from every specialist's
        # notes at once. Showing them together is the point: they are supposed
        # to agree with each other, and reviewing them side by side is the only
        # way to see whether they do.
        sections = list(values.get("sections") or [])
        print(f"\n📄 SECTIONS ({len(sections)} written by the single final writer):")
        for i, s in enumerate(sections, 1):
            words = len((s or "").split())
            has_title = (s or "").lstrip().startswith("## ")
            has_sources = "### Sources" in (s or "")
            print(f"  {i}. {words:>5} words | title:{'✅' if has_title else '❌'} | sources:{'✅' if has_sources else '❌'}")
        if sections:
            print("\n" + ("\n\n" + "=" * 78 + "\n\n").join(sections))

        # gtm_complete is reported but not required: the account_discovery node
        # is still commented out of the graph, so it can never be set.
        required = {k: v for k, v in flags.items() if k != "gtm_complete"}
        done = all(required.values()) and len(sections) == 3
        print("\n" + ("✅ E2E complete: all wired phases finished and 3 sections written." if done
                      else "⚠️ E2E ended but phases or sections incomplete."))

    except KeyboardInterrupt:
        print("\n⌨️ Cancelled.")
        print(f"\nPartial phase timing: {_fmt(sum((r['end'] - r['start']) for r in node_times.values() if r.get('start') and r.get('end')))}")
        print(f"LLM calls so far: {llm_stats['calls']}")
    except Exception as e:
        print(f"❌❌\n> Error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()