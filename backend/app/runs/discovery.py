"""Discovery runs: offer intake (interactive) -> specialists -> offer and
market research -> competition -> ICP.

A run advances in segments. A segment streams the graph until it finishes or
interrupts with a question; then it ends, leaving the run `awaiting_input`
with the LangGraph checkpoint holding its state. An answer starts the next
segment from that checkpoint. Frames go to the run's event log, never straight
to a socket, so they survive disconnects.
"""

import uuid
from datetime import UTC, datetime

from langgraph.types import Command

from agents.helpers import as_follow_up
from agents.llm.main import llm_timing_report
from backend.app.agents_runtime import get_agent
from backend.app.database import models
from backend.app.database.connect import AsyncSessionLocal
from backend.app.runs import events, signals
from backend.app.schemas.agents import DiscoveryRequest
from backend.app.services import workspaces as workspace_service
from backend.app.services.runs import set_run_fields
from utils.log import logger

# Top-level nodes of agents.discovery_agent.build_discovery_agent(), in
# execution order. Used to turn node updates into phase frames for the
# workspace stepper.
NODE_ORDER = [
    "discover_offer",
    "create_specialists",
    "understand_offer",
    "understand_market",
    "understand_competition",
    "determine_icp",
]


def build_initial_state(discovery_req: DiscoveryRequest) -> dict:
    """Seed the loose intake keys the discovery agent reads. The pipelines
    family carries offer_name/website_url/target_market directly on the session
    (no OfferDataSnapshot model), so the initial input is a plain dict.

    `offer_type` arrives asserted from the intake form — the agent no longer
    classifies it, so this is the only place it enters the graph."""
    return {
        "offer_name": discovery_req.product_name,
        "website_url": discovery_req.product_url,
        "offer_type": discovery_req.offer_type,
        "target_market": discovery_req.target_geo or [],
        "source": discovery_req.source,
        "offer_description": discovery_req.offer_description,
        "messages": [],
    }


def serialize_offer_snapshot(values: dict) -> dict | None:
    """Assemble the OfferSnapshot JSON the client expects from the agent's loose
    state keys. The old gtmx_agent carried an OfferDataSnapshot model; the
    discovery agent writes plain offer_* channels, so the shape is rebuilt here
    (features/service_uniqueness are plain strings in the new schema)."""
    offer_name = values.get("offer_name")
    if not offer_name:
        return None
    return {
        "company_name": None,
        "offer_name": offer_name,
        "offer_description": values.get("offer_description"),
        "website_url": values.get("website_url"),
        "intent": None,
        "target_geo": list(values.get("target_market") or []),
        "problem_solved": values.get("problem"),
        "features": [
            {"name": f, "description": None, "differentiator": None}
            for f in (values.get("features") or [])
        ],
        "service_uniqueness": [
            {"name": f, "description": None, "differentiator": None}
            for f in (values.get("service_uniqueness") or [])
        ],
        "how_it_works": values.get("how_it_works"),
    }


def build_insights(values: dict) -> dict:
    """Final run results persisted with the workspace so tabs can show real
    data after a refresh."""
    return {
        "offer_snapshot": serialize_offer_snapshot(values),
        # Persisted because the standalone get_competitors agent runs later, from
        # the workspace, and switches its whole vocabulary on this noun ("product"
        # vs "service"). Without it a reload would hunt a service workspace using
        # product language.
        "offer_type": values.get("offer_type"),
        "confirmed": bool(values.get("confirmed")),
        "domain_understanding": values.get("offer_domain_fit_understanding"),
        "market_fit_understanding": values.get("product_market_fit_understanding"),
        "market_data": dump(values.get("market_data")),
        "competition_data": dump(values.get("competition_data")),
        # The archetype profile is persisted beside the SWOD, not inside it. It is
        # the competition stage's PRIMARY output and the input the standalone
        # get_competitors agent hunts with, so a reload must still have it.
        "ideal_competitor_profile": dump(values.get("ideal_competitor_profile")),
        "icp": dump(values.get("icp_data")),
        "specialists": dump(values.get("specialists")),
        # Each specialist's full research notes (with sources), not just the
        # 40-50 word understanding above: what the specialists answer from in
        # chat, outreach and replies, and what later agent runs build on.
        "research": {
            "offer": values.get("offer_findings"),
            "market": values.get("market_findings"),
            "competition": values.get("competition_findings"),
            "icp": values.get("icp_findings"),
        },
        "completed_at": datetime.now(UTC).isoformat(),
    }


def dump(value):
    """Checkpoint round-trips may hand back pydantic models, plain dicts/lists
    of models, or scalars. Recurses so a list of models (e.g. the specialist
    team) serializes like a single model does."""
    if value is None:
        return None
    if isinstance(value, dict):
        return {k: dump(v) for k, v in value.items()}
    if isinstance(value, list):
        return [dump(v) for v in value]
    if hasattr(value, "model_dump"):
        return value.model_dump(mode="json")
    return value


def phase_payload(node: str, values: dict) -> dict | None:
    """Extract the structured result of a finished phase for the stepper panel."""
    if node == "create_specialists":
        specialists = dump(values.get("specialists"))
        return {"specialists": specialists} if specialists else None
    if node == "understand_offer":
        understanding = values.get("offer_domain_fit_understanding")
        if not understanding:
            return None
        return {"offer_domain_fit_understanding": understanding}
    if node == "understand_market":
        market = dump(values.get("market_data"))
        if market is None:
            return None
        return {
            "market_data": market,
            "product_market_fit_understanding": values.get(
                "product_market_fit_understanding"
            ),
        }
    if node == "understand_competition":
        # Both halves of the stage's output ship together. The PROFILE is the
        # primary one -- it is what the downstream competitor agent reads, and
        # what the UI's archetype view renders -- but the SWOD is the part the
        # report and the ICP consume, so neither can be dropped to save bytes.
        #
        # Kept as two sibling keys rather than merged into one record: they are
        # different claims (a construct vs a judgment about the offer), and the
        # frontend needs them separable for the same reason the backend does.
        competition = dump(values.get("competition_data"))
        profile = dump(values.get("ideal_competitor_profile"))
        if competition is None and profile is None:
            return None
        return {
            "competition_data": competition,
            "ideal_competitor_profile": profile,
        }
    if node == "determine_icp":
        icp = dump(values.get("icp_data"))
        return {"icp_data": icp} if icp else None
    return None


def _interrupt_payload(value: dict) -> dict:
    return {
        "interrupt_type": value.get("type"),
        "question": value.get("question"),
        "offer_name": value.get("offer_name"),
        "product_candidates": list(value.get("product_candidates") or []),
        "draft": value.get("draft"),
        "url": value.get("url"),
        "lean": value.get("lean"),
    }


async def run_segment(run_id: uuid.UUID, agent_input: dict | Command) -> None:
    """Advance a discovery run until it completes or asks the user something."""
    agent = get_agent()
    config = {"configurable": {"thread_id": str(run_id)}}
    async with AsyncSessionLocal() as db:
        run = await db.get(models.Run, run_id)
        user_id, workspace_id = run.user_id, run.workspace_id
        progress = dict(run.progress or {})
    # understand_offer and understand_market run concurrently, so a node
    # finishing does not imply the previous one did. Track what has actually
    # happened, across segments, to drive the stepper.
    completed: set[str] = set(progress.get("completed", []))
    announced: set[str] = set(progress.get("announced", []))

    async def save_progress(**extra) -> None:
        progress.update(completed=sorted(completed), announced=sorted(announced), **extra)
        await set_run_fields(models.Run, run_id, progress=dict(progress), workspace_id=workspace_id)

    pending_interrupt = None
    async for update in agent.astream(agent_input, config, stream_mode="updates"):
        if "__interrupt__" in update:
            pending_interrupt = update["__interrupt__"][0]
            continue
        node, node_output = next(iter(update.items()))
        # The manual intake path is a sibling subgraph; for the stepper it is
        # the same step.
        if node == "discover_offer_manual":
            node = "discover_offer"
        if node not in NODE_ORDER:
            continue

        state = await agent.aget_state(config)
        # Parallel stages (offer + market) share a super-step, whose state is
        # committed only when BOTH finish -- so the snapshot read when one
        # finishes lacks its own output. Overlay the node's own update.
        values = {**(state.values if state is not None else {}), **(node_output or {})}
        completed.add(node)

        # Intake finished: persist the workspace before the client navigates
        # into it, then tell it the id.
        if node == "discover_offer" and workspace_id is None:
            if serialize_offer_snapshot(values) is None:
                raise RuntimeError("Discovery completed without an offer snapshot.")
            async with AsyncSessionLocal() as db:
                workspace_id = await workspace_service.create_from_discovery(db, user_id, values)
            await events.publish(run_id, "workspace_created", {"workspace_id": str(workspace_id)})

        await events.publish(run_id, "phase", {"node": node, "status": "done"})
        payload = phase_payload(node, values)
        if payload is not None:
            await events.publish(run_id, "phase_data", {"node": node, **payload})

        # Announce the next phase that has not begun. Scanning forward from the
        # node that just finished (not index+1) stays correct while two
        # stages overlap.
        for candidate in NODE_ORDER[NODE_ORDER.index(node):]:
            if candidate not in completed and candidate not in announced:
                announced.add(candidate)
                await events.publish(run_id, "phase", {"node": candidate, "status": "started"})
                break
        await save_progress()

    if pending_interrupt is not None:
        question = _interrupt_payload(pending_interrupt.value)
        await save_progress(interrupt=question)
        await set_run_fields(models.Run, run_id, status="awaiting_input")
        await events.publish(run_id, "interrupt", question)
        return

    state = await agent.aget_state(config)
    values = state.values if state is not None else {}
    follow_up = as_follow_up(values.get("follow_up"))
    # The LLM share of the run's wall clock; the rest is search/scraping.
    logger.info("Discovery run %s LLM breakdown:\n%s", run_id, llm_timing_report())

    # Persist insights BEFORE announcing completion, so the client can refetch
    # them right after the `complete` frame.
    if workspace_id is not None:
        async with AsyncSessionLocal() as db:
            await workspace_service.save_insights(db, workspace_id, build_insights(values))

    await save_progress(interrupt=None)
    await set_run_fields(models.Run, run_id, status="completed", finished_at=datetime.now(UTC))
    if workspace_id is not None:
        await signals.discovery_finished(run_id, user_id, workspace_id, values)
    await events.publish(run_id, "complete", {
        "workspace_id": str(workspace_id) if workspace_id else None,
        "confirmed": bool(values.get("confirmed")),
        "offer_snapshot": serialize_offer_snapshot(values),
        "user_replies": list(follow_up.user_replies or []),
    })
