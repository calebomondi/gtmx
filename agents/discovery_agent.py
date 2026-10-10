"""Discovery agent — the top-level workflow that amalgamates the pipelines
pipelines under agents/pipelines.

Mirror of `gtmx_agent.py` (same shape of wiring and parallelism reasoning), but
over the pipelines family instead of the interview-era subgraphs:

    discover_offer -> create_specialists -> [understand_offer ∥ understand_market]
        -> understand_competition -> determine_icp

The intake stage is a compiled subgraph added directly as a node (interrupts in
a nested subgraph propagate to the top-level invoke and resume via
Command(resume=...) — exactly like gtmx_agent's `discover_product_service`).
The five non-interactive stages run through thin `run_*` wrappers instead:
each wrapper invokes its compiled subgraph over the shared aggregate state (the
subgraph's schema filters it to the channels it reads) and folds back ONLY the
stage's own channels.

Why the distinction matters: the pipelines carry the loose snapshot keys
(offer_type/offer_name/...) as passthroughs, so both parallel stages would try
to write them into the parent in the same super-step — a non-reduced channel
like `offer_type` cannot take two values per step. The wrappers return disjoint
stage keys (offer_* / market_* / competition_* / icp_*), so the parallel
fan-out writes never collide. This is the same constraint gtmx_agent documents
for `run_interview` vs `run_market_interview`.
"""

from langgraph.graph import START, END, StateGraph
from langgraph.checkpoint.memory import MemorySaver
from langgraph.checkpoint.base import BaseCheckpointSaver

from agents.pipelines.schema_states import DiscoverySessionState
from agents.pipelines.discover.discover_offer import build_offer_discovery_graph
from agents.pipelines.discover.discover_offer_manual import build_manual_offer_discovery_graph
from agents.pipelines.discover.create_specialists import build_specialist_graph
from agents.pipelines.discover.understand_offer import build_product_graph
from agents.pipelines.discover.understand_market import build_market_graph
from agents.pipelines.discover.understand_competition import build_competition_graph
from agents.pipelines.discover.build_icp import build_icp_graph


# Nested subgraphs can't own a checkpointer — the parent agent does. Built once
# and reused across run_* invocations instead of recompiling per call.
_DISCOVER_OFFER = build_offer_discovery_graph(checkpointer=False)
_DISCOVER_OFFER_MANUAL = build_manual_offer_discovery_graph(checkpointer=False)
_SPECIALISTS = build_specialist_graph()
_UNDERSTAND_OFFER = build_product_graph(checkpointer=False)
_UNDERSTAND_MARKET = build_market_graph(checkpointer=False)
_UNDERSTAND_COMPETITION = build_competition_graph(checkpointer=False)
_DETERMINE_ICP = build_icp_graph(checkpointer=False)


# The channels each stage owns in the aggregate state. Only these are folded
# back from a subgraph's final state — the pipeline passthroughs (the loose
# snapshot keys, specialists, messages) stay with the stage that produced them,
# so the parallel offer/market fan-out never races on a shared channel.
_SPECIALIST_KEYS = ("specialists", "specialist_generation_complete")
_OFFER_KEYS = ("offer_findings", "offer_domain_fit_understanding", "offer_under_complete", "tasks", "task_research")
_MARKET_KEYS = ("market_findings", "product_market_fit_understanding", "market_data", "market_complete", "market_tasks", "market_task_research")
_COMPETITION_KEYS = ("competition_findings", "competitive_positioning_understanding", "ideal_competitor_profile", "competition_data", "competition_complete", "competition_tasks", "competition_task_research")
_ICP_KEYS = ("icp_data", "icp_findings", "icp_understanding", "icp_complete")


def _fold(result: dict, keys: tuple[str, ...]) -> dict:
    """Fold a subgraph's final state back into the parent: forward only the
    stage's own channels that actually hold a value (None means the stage did
    not produce it)."""
    return {k: result[k] for k in keys if result.get(k) is not None}


def run_create_specialists(state: DiscoverySessionState) -> dict:
    """Create the four-specialist team over the offer's intake material."""
    return _fold(_SPECIALISTS.invoke(state), _SPECIALIST_KEYS)


def run_understand_offer(state: DiscoverySessionState) -> dict:
    """Run the offer-research pipeline: specialist-led web research on the
    offer's domain/category, folded into offer_findings + fit understanding."""
    return _fold(_UNDERSTAND_OFFER.invoke(state), _OFFER_KEYS)


def run_understand_market(state: DiscoverySessionState) -> dict:
    """Run the market pipeline in parallel with understand_offer. Writes only
    market_* channels, so its concurrent writes never collide with the offer
    stage's."""
    return _fold(_UNDERSTAND_MARKET.invoke(state), _MARKET_KEYS)


def run_understand_competition(state: DiscoverySessionState) -> dict:
    """Run the competition pipeline strictly after offer + market: it reads the
    sibling findings and market_data from the shared aggregate state."""
    return _fold(_UNDERSTAND_COMPETITION.invoke(state), _COMPETITION_KEYS)


def run_determine_icp(state: DiscoverySessionState) -> dict:
    """Run the GTM synthesis stage: the ICP drafted+refined from every earlier
    stage's outputs (no web research of its own)."""
    return _fold(_DETERMINE_ICP.invoke(state), _ICP_KEYS)


def build_discovery_agent(checkpointer: BaseCheckpointSaver | None = None):
    """Build the discovery agent state graph: offer intake (interactive) ->
    create_specialists -> understand_offer -> understand_market ->
    understand_competition -> determine_icp.

    The discovery phase is interactive: its interrupts surface on the top-level
    invoke and resume via Command(resume=...) with the same thread config.

    `checkpointer` lets callers (e.g. the backend) supply a durable saver such
    as AsyncPostgresSaver; falls back to an in-memory saver for interactive
    drivers and tests."""

    builder = StateGraph(DiscoverySessionState)

    # -- Nodes --
    builder.add_node("discover_offer", _DISCOVER_OFFER)
    builder.add_node("discover_offer_manual", _DISCOVER_OFFER_MANUAL)
    builder.add_node("create_specialists", run_create_specialists)
    builder.add_node("understand_offer", run_understand_offer)
    builder.add_node("understand_market", run_understand_market)
    builder.add_node("understand_competition", run_understand_competition)
    builder.add_node("determine_icp", run_determine_icp)
    # builder.add_node("account_discovery", run_account_discovery)

    # -- Edges --
    # The intake source decides which discover_offer path runs: website URL →
    # scrape flow; anything else → manual description flow. Both write the same
    # loose snapshot keys, so create_specialists onwards is identical.
    def _route_intake(state: DiscoverySessionState) -> str:
        return "discover_offer_manual" if state.get("source") == "manual" else "discover_offer"

    builder.add_conditional_edges(
        START,
        _route_intake,
        {"discover_offer": "discover_offer", "discover_offer_manual": "discover_offer_manual"},
    )
    builder.add_edge("discover_offer", "create_specialists")
    builder.add_edge("discover_offer_manual", "create_specialists")
    # Offer and market research are independent, so they run in the same
    # super-step and LangGraph executes them concurrently (these are sync node
    # functions, so it hands them to a thread pool). Competition stays strictly
    # after both: it reads market_data and the sibling offer findings, and a
    # competitive analyst briefed without the market is the one thing that
    # would cost the report its coherence.
    #
    # Safe to overlap because the two nodes write disjoint keys — the wrappers
    # fold back only stage-owned channels (offer_* vs market_*), so nothing
    # shared is ever written concurrently. The only channel both subgraphs
    # carry is `messages`, which DiscoverySessionState already reduces with
    # add_messages — and neither pipeline writes it.
    builder.add_edge("create_specialists", "understand_offer")
    builder.add_edge("create_specialists", "understand_market")
    builder.add_edge("understand_offer", "understand_competition")
    builder.add_edge("understand_market", "understand_competition")
    builder.add_edge("understand_competition", "determine_icp")
    builder.add_edge("determine_icp", END)
    # builder.add_edge("account_discovery", END)

    # -- Compile --
    return builder.compile(checkpointer=checkpointer or MemorySaver())