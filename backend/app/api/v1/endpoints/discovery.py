import json
import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from langgraph.types import Command
from sqlalchemy import select

from agents.helpers import as_follow_up
from agents.llm.main import (
    LlmProvidersExhaustedError,
    classify_llm_error,
    llm_timing_report,
)

from backend.app.agents_runtime import get_agent
from backend.app.config.settings import settings
from backend.app.schemas.agents import DiscoveryRequest
from backend.app.database.connect import AsyncSessionLocal
from backend.app.naming import title_case
from backend.app.database.models import (
    ProductFeature,
    ProductProfile,
    User,
    Workspace,
)

from utils.log import logger


router = APIRouter()

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


def _build_initial_state(discovery_req: DiscoveryRequest) -> dict:
    """Seed the loose intake keys the discovery agent reads. The sub_agents
    family carries offer_name/website_url/target_market directly on the session
    (no OfferDataSnapshot model), so the initial input is a plain dict.

    `offer_type` arrives asserted from the intake form — the agent no longer
    classifies it, so this is the only place it enters the graph."""
    return {
        "offer_name": discovery_req.product_name,
        "website_url": discovery_req.product_url,
        "offer_type": discovery_req.offer_type,
        "target_market": discovery_req.target_geo or [],
        "messages": [],
    }


def _serialize_offer_snapshot(values: dict) -> dict | None:
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


async def _receive_answer(websocket: WebSocket) -> str | None:
    """Read one user reply. Accepts a plain-text answer or a JSON object with an
    'answer' field so WebSocket clients and simple tooling can both talk to us."""
    text = await websocket.receive_text()
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        return text
    if isinstance(data, dict):
        answer = data.get("answer")
        return answer if isinstance(answer, str) else None
    return text


async def _get_mock_user_id() -> uuid.UUID:
    """Auth is faked: resolve the seeded signed-in user by email."""
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(User).where(User.email == settings.MOCK_USER_EMAIL)
        )
        user = result.scalar_one_or_none()
    if user is None:
        raise RuntimeError(
            f"Mock user {settings.MOCK_USER_EMAIL!r} not found — seed ran?"
        )
    return user.id


async def _persist_workspace(values: dict, confirmed: bool) -> uuid.UUID:
    """Persist the offer the discovery phase settled on. `values` is the
    session state as loose keys (offer_name/website_url/problem/features: list
    of plain strings), mapped to the ProductProfile shape."""
    user_id = await _get_mock_user_id()
    offer_name = (values.get("offer_name") or "").strip() or None

    async with AsyncSessionLocal() as db:
        async with db.begin():
            workspace = Workspace(
                user_id=user_id,
                name=title_case(offer_name),
            )

            profile = ProductProfile(
                workspace=workspace,
                product_name=offer_name,
                product_url=values.get("website_url"),
                product_description=values.get("offer_description"),
                intent=None,
                problem_solved=values.get("problem"),
                how_it_works=values.get("how_it_works"),
                target_geo=list(values.get("target_market") or []),
                confirmed=confirmed,
                features=[
                    ProductFeature(
                        name=f,
                        description=None,
                        differentiator=None,
                    )
                    for f in values.get("features") or []
                ],
            )

            db.add(profile)

        return workspace.id


def _build_insights(values: dict) -> dict:
    """Final run results persisted with the workspace so tabs can show real
    data after a refresh."""
    return {
        "offer_snapshot": _serialize_offer_snapshot(values),
        # Persisted because the standalone get_competitors agent runs later, from
        # the workspace, and switches its whole vocabulary on this noun ("product"
        # vs "service"). Without it a reload would hunt a service workspace using
        # product language.
        "offer_type": values.get("offer_type"),
        "confirmed": bool(values.get("confirmed")),
        "domain_understanding": values.get("offer_domain_fit_understanding"),
        "market_fit_understanding": values.get("product_market_fit_understanding"),
        "market_data": _dump(values.get("market_data")),
        "competition_data": _dump(values.get("competition_data")),
        # The archetype profile is persisted beside the SWOD, not inside it. It is
        # the competition stage's PRIMARY output and the input the standalone
        # get_competitors agent hunts with, so a reload must still have it.
        "ideal_competitor_profile": _dump(values.get("ideal_competitor_profile")),
        "icp": _dump(values.get("icp_data")),
        "specialists": _dump(values.get("specialists")),
        "completed_at": datetime.now(UTC).isoformat(),
    }


async def _persist_insights(workspace_id: uuid.UUID, insights: dict) -> None:
    async with AsyncSessionLocal() as db:
        async with db.begin():
            result = await db.execute(
                select(ProductProfile).where(
                    ProductProfile.workspace_id == workspace_id
                )
            )
            profile = result.scalar_one_or_none()
            if profile is not None:
                profile.insights = insights


@router.websocket("")
async def start_product_discovery(websocket: WebSocket):
    """Run the discovery agent (discover_offer -> specialists ->
    understand_offer -> market -> competition -> determine_icp) over a
    full-duplex WebSocket.

    The connection stays open for the whole run: every time the discovery phase
    interrupts, the question is streamed to the client, the client replies, and
    the agent resumes. Once discovery completes the workspace is persisted and a
    `workspace_created` frame lets the client jump into it while `phase` /
    `phase_data` frames stream the remaining progress for the stepper UI.
    """
    await websocket.accept()

    session_id = str(uuid.uuid4())
    try:
        raw = await websocket.receive_text()
    except WebSocketDisconnect:
        return

    try:
        discovery_req = DiscoveryRequest.model_validate_json(raw)
        initial_state = _build_initial_state(discovery_req)
    except Exception as e:
        await websocket.send_json({"type": "error", "message": f"Invalid request: {e}"})
        await websocket.close(code=1008)
        return

    config = {"configurable": {"thread_id": session_id}}

    try:
        agent = get_agent()
    except Exception as e:
        logger.exception("Agent runtime unavailable: %s", e)
        await websocket.send_json({"type": "error", "message": f"{e}"})
        await websocket.close(code=1011)
        return

    workspace_id: uuid.UUID | None = None
    # understand_offer and understand_market run concurrently, so a node
    # completing no longer implies the previous one did. Track both sets across
    # the whole session (interrupt resumes re-enter this loop) so the stepper is
    # driven by what has actually happened rather than by array position.
    announced_started: set[str] = set()
    completed: set[str] = set()

    try:
        input_to_agent = initial_state

        while True:
            pending_interrupt = None

            async for event in agent.astream(input_to_agent, config, stream_mode="updates"):
                if "__interrupt__" in event:
                    pending_interrupt = event["__interrupt__"][0]
                    continue

                node, _update = next(iter(event.items()))
                if node not in NODE_ORDER:
                    continue

                state = await agent.aget_state(config)
                values = state.values if state is not None else {}
                node_index = NODE_ORDER.index(node)
                completed.add(node)

                # Discovery finished: persist the workspace before the client
                # navigates into it, then tell it the id.
                if node == "discover_offer" and workspace_id is None:
                    snapshot = _serialize_offer_snapshot(values)
                    if snapshot is None:
                        raise RuntimeError(
                            "Discovery completed without an offer snapshot."
                        )
                    workspace_id = await _persist_workspace(
                        values=values,
                        confirmed=bool(values.get("confirmed")),
                    )
                    await websocket.send_json({
                        "type": "workspace_created",
                        "session_id": session_id,
                        "workspace_id": str(workspace_id),
                    })

                await websocket.send_json({
                    "type": "phase",
                    "session_id": session_id,
                    "node": node,
                    "status": "done",
                })

                phase_payload = _phase_payload(node, values)
                if phase_payload is not None:
                    await websocket.send_json({
                        "type": "phase_data",
                        "session_id": session_id,
                        "node": node,
                        **phase_payload,
                    })

                # Announce the next phase that has not begun yet. Scanning
                # forward from the node that just finished, rather than taking
                # index+1, is what makes this correct now that two interviews
                # overlap: whichever finishes first hands the stepper to its
                # sibling, which is genuinely the phase in flight.
                for candidate in NODE_ORDER[node_index:]:
                    if candidate in completed or candidate in announced_started:
                        continue
                    announced_started.add(candidate)
                    await websocket.send_json({
                        "type": "phase",
                        "session_id": session_id,
                        "node": candidate,
                        "status": "started",
                    })
                    break

            if pending_interrupt is None:
                break  # run finished

            payload = pending_interrupt.value
            await websocket.send_json({
                "type": "interrupt",
                "session_id": session_id,
                "interrupt_type": payload.get("type"),
                "question": payload.get("question"),
                "offer_name": payload.get("offer_name"),
                "product_candidates": list(payload.get("product_candidates") or []),
                "draft": payload.get("draft"),
                "url": payload.get("url"),
                "lean": payload.get("lean"),
            })

            answer = await _receive_answer(websocket)
            if not answer or not answer.strip():
                await websocket.send_json({
                    "type": "error",
                    "message": "No user input was provided.",
                })
                await websocket.close(code=1008)
                return

            input_to_agent = Command(resume=answer)

        state = await agent.aget_state(config)
        values = state.values if state is not None else {}
        follow_up = as_follow_up(values.get("follow_up"))

        # Where the run's wall clock actually went. This is the LLM share only --
        # Exa search and scrape time never passes through the LLM layer, so treat
        # the gap between this total and the run duration as search/network.
        logger.info("Discovery run LLM breakdown:\n%s", llm_timing_report())

        # Persist final insights before announcing completion so the client can
        # refetch them right after the `complete` frame.
        if workspace_id is not None:
            try:
                await _persist_insights(workspace_id, _build_insights(values))
            except Exception:
                logger.exception(
                    "Failed to persist insights for workspace %s", workspace_id
                )

        await websocket.send_json({
            "type": "complete",
            "session_id": session_id,
            "workspace_id": str(workspace_id) if workspace_id else None,
            "confirmed": bool(values.get("confirmed")),
            "offer_snapshot": _serialize_offer_snapshot(values),
            "user_replies": list(follow_up.user_replies or []),
        })

        await websocket.close(code=1000)
    except WebSocketDisconnect:
        return
    except Exception as e:
        logger.exception("Agent run failed for session %s: %s", session_id, e)
        try:
            await websocket.send_json({"type": "error", "message": _user_facing_error(e)})
            await websocket.close(code=1011)
        except Exception:
            pass


def _user_facing_error(err: BaseException) -> str:
    """Turn a provider failure into something the user can act on.

    The raw exception is an "All LLM providers failed for <step>" RuntimeError,
    which says nothing useful in the UI. Name the step, name the likely cause,
    and say whether retrying is worth it — the run is resumable from the
    workspace, not lost.
    """
    if isinstance(err, LlmProvidersExhaustedError):
        if err.last_err is None:
            return (
                f"Stopped while running '{err.log_label}'. The AI provider is rate "
                "limiting requests across the whole run. This is a provider-side "
                "limit, not a problem with your input — wait a minute and start "
                "the workspace again. Nothing already saved is lost."
            )
        # Same classifier the retry ladder uses, so the message can't contradict
        # how we actually reacted to the error.
        kind = classify_llm_error(err.last_err)
        if kind == "rate_limit":
            reason = (
                "The AI provider is rate limiting requests right now. This is a "
                "provider-side limit, not a problem with your input — it usually "
                "clears within a minute."
            )
        elif kind == "context_overflow":
            return (
                f"Stopped while running '{err.log_label}'. The accumulated "
                "research grew past what the AI model can read in one request. "
                "This is a limit on our side, not your input — nothing already "
                "saved is lost, but the interview needs to be re-run with a "
                "shorter starting point to get past it."
            )
        elif kind == "auth":
            reason = (
                "The AI provider rejected the API key. Check DASHSCOPE_API_KEY in "
                "your .env and that the model is enabled for your account."
            )
        elif kind == "billing":
            reason = (
                "The AI provider reports the account is out of credit. Add funds "
                "or raise the quota on your DashScope account and start the "
                "workspace again — nothing already saved is lost."
            )
        else:
            reason = "The AI provider rejected the request."

        return (
            f"Stopped while running '{err.log_label}'. {reason} "
            "Wait a moment and start the workspace again — nothing already "
            "saved is lost."
        )
    return f"{err}"


def _dump(value):
    """Checkpoint round-trips may hand back pydantic models, plain dicts/lists
    of models, or scalars. Recurses so a list of models (e.g. the specialist
    team) serializes like a single model does."""
    if value is None:
        return None
    if isinstance(value, dict):
        return {k: _dump(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_dump(v) for v in value]
    if hasattr(value, "model_dump"):
        return value.model_dump(mode="json")
    return value


def _phase_payload(node: str, values: dict) -> dict | None:
    """Extract the structured result of a finished phase for the stepper panel."""
    if node == "create_specialists":
        specialists = _dump(values.get("specialists"))
        return {"specialists": specialists} if specialists else None
    if node == "understand_offer":
        understanding = values.get("offer_domain_fit_understanding")
        if not understanding:
            return None
        return {"offer_domain_fit_understanding": understanding}
    if node == "understand_market":
        market = _dump(values.get("market_data"))
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
        competition = _dump(values.get("competition_data"))
        profile = _dump(values.get("ideal_competitor_profile"))
        if competition is None and profile is None:
            return None
        return {
            "competition_data": competition,
            "ideal_competitor_profile": profile,
        }
    if node == "determine_icp":
        icp = _dump(values.get("icp_data"))
        return {"icp_data": icp} if icp else None
    return None
