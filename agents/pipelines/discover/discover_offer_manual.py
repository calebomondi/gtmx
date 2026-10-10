"""Manual (no-website) offer intake path.

Twin of `discover_offer.py` for offers that arrive with a free-text description
rather than a URL. It reuses the same rest-extraction LLM call (now over the
user-authored description instead of scraped page content) and emits the exact
same loose snapshot keys, so every downstream node handed them by
`discovery_agent` works identically on both paths.

Interrupt surface: no scrape, no candidate picker, no description confirmation.
The only interrupt is an optional "you didn't cover X yet" nudge when the
extraction comes back missing pieces — one round, then we accept what we have."""

from typing import Literal, Optional

from langchain_core.messages import HumanMessage
from langgraph.graph import START, END, StateGraph
from langgraph.checkpoint.memory import MemorySaver
from langgraph.types import interrupt, Command

from agents.helpers import as_follow_up, normalize_optional_text

from agents.schemas.sessions import DiscoverOfferState
from .discover_offer import retrieve_rest_product_service_info


def _missing_details(state: DiscoverOfferState) -> list[str]:
    missing: list[str] = []
    if not normalize_optional_text(state.get("problem")):
        missing.append("the core problem it solves")
    if not normalize_optional_text(state.get("how_it_works")):
        missing.append("how it works end-to-end")
    offer_type = state.get("offer_type")
    if offer_type == "service":
        if not list(state.get("service_uniqueness") or []):
            missing.append("what makes it different from alternatives")
    elif not list(state.get("features") or []):
        missing.append("its main features")
    return missing


def extract_rest(state: DiscoverOfferState) -> dict:
    """Run the shared rest-extraction over the user's description (+ any
    follow-up answers). With no scraped content in state this degrades to
    description-only extraction, which is exactly the manual path's evidence."""
    update = retrieve_rest_product_service_info(state)
    return update


def ask_for_missing_details(state: DiscoverOfferState) -> Command[Literal["extract_rest_retry", "__end__"]]:
    """One light interrupt when extraction left gaps: list what's missing and
    let the user fill it in. A reply that is just a confirmation / 'skip'
    accepts the gaps and we move on."""
    missing = _missing_details(state)
    follow_up = as_follow_up(state.get("follow_up"))
    offer_name = normalize_optional_text(state.get("offer_name")) or "your offer"

    question = (
        f"I have the basics on {offer_name}, but a few details would make the "
        f"research much better: {', '.join(missing)}.\n\n"
        "Add them in a sentence or two, or reply 'skip' to continue as-is."
    )

    user_answer = interrupt({
        "type": "offer_details_followup",
        "question": question,
        "offer_name": offer_name,
        "missing": missing,
    })

    update: dict = {
        "messages": [HumanMessage(content=user_answer)],
        "follow_up": {
            "follow_up_question": None,
            "user_replies": follow_up.user_replies + [user_answer],
        },
    }

    stripped = (user_answer or "").strip().lower()
    if stripped in {"skip", "continue", "no", "none", "n/a", "na"}:
        return Command(update={**update, "confirmed": True}, goto=END)

    return Command(update=update, goto="extract_rest_retry")


def extract_rest_retry(state: DiscoverOfferState) -> dict:
    """Second extraction pass now that the user's follow-up is in
    `follow_up.user_replies` — the shared prompt folds those in. Merge rather
    than replace: keep whatever the first pass found."""
    update = retrieve_rest_product_service_info(state)
    first_features = list(state.get("features") or [])
    first_uniqueness = list(state.get("service_uniqueness") or [])

    merged = dict(update)
    merged["features"] = update.get("features") or first_features
    merged["service_uniqueness"] = update.get("service_uniqueness") or first_uniqueness
    if not merged.get("problem") and state.get("problem"):
        merged["problem"] = state["problem"]
    if not merged.get("how_it_works") and state.get("how_it_works"):
        merged["how_it_works"] = state["how_it_works"]
    merged["confirmed"] = True
    return merged


def _route_after_extract(state: DiscoverOfferState) -> str:
    return "ask_for_missing_details" if _missing_details(state) else END


def build_manual_offer_discovery_graph(checkpointer: bool = True):
    """Manual offer-intake graph: extract → (optional details nudge) → done.
    Pass checkpointer=False when embedding as a subgraph node."""
    agent = StateGraph(DiscoverOfferState)

    agent.add_node("extract_rest", extract_rest)
    agent.add_node("ask_for_missing_details", ask_for_missing_details)
    agent.add_node("extract_rest_retry", extract_rest_retry)

    agent.add_edge(START, "extract_rest")
    agent.add_conditional_edges(
        "extract_rest",
        _route_after_extract,
        {"ask_for_missing_details": "ask_for_missing_details", END: END},
    )
    agent.add_edge("extract_rest_retry", END)

    if checkpointer:
        return agent.compile(checkpointer=MemorySaver())
    return agent.compile()
