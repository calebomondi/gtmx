from langgraph.graph import START, END, StateGraph
from langgraph.checkpoint.memory import MemorySaver
from langchain_core.messages import SystemMessage

from agents.llm.main import invoke_structured_with_fallback
from agents.states import DetermineIcpState, ICP
from agents.helpers import (
    as_offer_snapshot,
    format_offer_material,
    market_context_block,
    competition_context_block,
)
from agents.sub_graphs.understand_product import _offer_type_for


def _buyer_emphasis(buyer_type: str | None) -> tuple[str, str]:
    """Return (label, branch instructions) choosing how thoroughly the ICP should
    lean on personas + reach channels (B2C/both) vs firmographics (B2B)."""
    if buyer_type == "b2c":
        return (
            "B2C (consumer offer)",
            """This is a CONSUMER offer — the buyer is an individual, not a company, so INDUSTRIES,
COMPANY SIZES and BUYER TITLES are NOT the point of this profile. Instead make these the core:
- `buyer_personas`: 2-4 sharply-defined personas — each with a name, who they are, the
  job-to-be-done this {offer_noun} helps with, where they congregate, and their intent signals.
- `target_channels`: the DISCOVERABLE venues where those personas actually are — social platforms,
  communities (subreddits, Discords, Facebook/LinkedIn groups), creators + newsletters whose
  audience matches, and marketplaces. For each: a concrete name (or a typed placeholder like
  "LinkedIn groups for X"), WHY the right audience is there, and a `first_angle` for engaging.
- `event_focus`: the events/summits/conferences/meetups whose attendees match the ICP — the
  attendance profile (who shows up, why), not a specific event list.
- `messaging_angles`: opening hooks per channel — what to say where.
- `beachhead`: one line naming the first segment/channel to attack before scaling.
- `geo`: target geographies by name.
- `exclusions`, `pain_signals`, `intent_keywords`: still required.
- `competitor_leads`: competitors whose USERS/audiences are prime targets — for consumer offers
  these are often competitor communities, review threads, or channels where their customers
  complain.""",
        )
    if buyer_type == "both":
        return (
            "BOTH B2B and B2C",
            """This {offer_noun} serves BOTH companies and consumers. Cover both sides:
- B2B side: `industries`, `company_sizes`, `buyer_titles` — the companies that buy.
- Consumer side: `buyer_personas` (named, with where they congregate), `target_channels`
  (social platforms, communities, creators, newsletters, marketplaces, with audience_fit +
  first_angle), and `event_focus` (events/summits/meetups whose attendees match).
- `geo`, `exclusions`, `pain_signals`, `intent_keywords`, `messaging_angles`, `beachhead`:
  whichever segments are relevant.
- `competitor_leads`: companies AND communities/creators whose customers/audiences are prime
  targets.""",
        )
    return (
        "B2B",
        """This {offer_noun} sells to companies — build the firmographic profile precisely:
- `industries`: no more than 3 industries whose companies are the best fit.
- `company_sizes`: concrete size bands the {offer_noun} realistically serves (e.g. ["11-50", "51-200"]).
- `buyer_titles`: the job titles/personas who own the problem this {offer_noun} solves.
- `buyer_personas`: secondary depth — where the named personas congregate, for the account phase.
- `target_channels`: a light list is fine — only include venues that clearly concentrate the
  target accounts (relevant events/summits, associations, communities the role follows).
- `event_focus`: if a specific summit/conference/meetup concentrates the buyer titles, describe
  the attendees; otherwise leave it empty.""",
    )


icp_instructions = """
You are {specialist_name}, a {specialist_role}.

Your background: {specialist_background}
Your focus: {specialist_focus}
Your lens: {specialist_lens}
Your region: {specialist_region}
Your language/idiom: {specialist_language}
Your operating context: {specialist_operating_context}

You are the go-to-market specialist for this {offer_noun}. From the market and competition
understanding already gathered, produce the IDEAL CUSTOMER PROFILE (ICP) that the
account-discovery phase will use to find real targets — companies, AND for consumer offers the
communities, platforms, events and creators where the ideal buyers congregate.

OFFER
Name: {offer_name}
Description: {offer_description}

MARKET CONTEXT (already gathered — treat as fact)
{market_context}

COMPETITION CONTEXT (already gathered — treat as fact)
{competition_context}

KNOWN FACTS
{snapshot_summary}

BUYER TYPE
{buyer_type_label}

{buyer_emphasis}

GENERAL FIELDS (fill on both sides)
- `product_name`: the {offer_noun} being profiled.
- `buyer_type`: "{buyer_type_value}" (b2b / b2c / both).
- `exclusions`: be explicit about who is NOT a fit (e.g. "agencies", "hobbyists", "consumers not in
  the target geo"). These become hard filters during account validation.
- `pain_signals`: the problems/intents that indicate an audience/account is actively searching for a solution.
- `intent_keywords`: keywords that appear when audiences/accounts are in-market (e.g. "evaluate",
  "switch from", "compare", "rollout"), so searches stay grounded in buying intent.
- `messaging_angles`: opening angles/hooks — how to first engage the audience in each channel.
- `beachhead`: one line naming the segment/channel to attack first.
- `competitor_leads`: derive one lead per real competitor from the COMPETITION CONTEXT — use their
  name, generate 1-2 web queries that surface accounts/audiences evaluating/reviewing them, and
  derive concrete `pain_angles` from what the competitive research found their customers complain
  about. Never invent a competitor that isn't in the competition context.

Drive the profile through your distinctive lens, and keep it anchored to the markets in your
region — scope it to how this category actually buys where the {offer_noun} operates.

RULES
1. Be conservative — a tight, high-quality ICP beats a broad, fuzzy one.
2. Everything must be defensible from the {offer_noun}, market, or competition context given.
3. If a field cannot be derived, leave it empty rather than guessing.
4. Do NOT reach into live research — only synthesize from the context provided here.
"""


def generate_icp(state: DetermineIcpState) -> dict:
    """Have the GTM specialist draft the structured, buyer-type-aware ICP from the
    offer's own material + market + competition understanding."""
    specialist = state["specialist"]
    offer = as_offer_snapshot(state.get("offer_snapshot"))
    offer_noun = _offer_type_for(state)

    market = state.get("market_data")
    buyer_value = None
    if market is not None:
        buyer_type = getattr(market, "buyer_type", None)
        buyer_value = buyer_type.value if buyer_type is not None else None
    buyer_label, buyer_emphasis = _buyer_emphasis(buyer_value)

    system_message = icp_instructions.format(
        offer_noun=offer_noun,
        specialist_name=specialist.name,
        specialist_role=specialist.role_title,
        specialist_background=specialist.background,
        specialist_focus=specialist.focus,
        specialist_lens=specialist.distinct_lens or "—",
        specialist_region=specialist.region or "—",
        specialist_language=specialist.language or "—",
        specialist_operating_context=specialist.operating_context or "—",
        offer_name=offer.offer_name or "Not yet named",
        offer_description=offer.offer_description or "Not yet described.",
        market_context=market_context_block(state.get("market_data")),
        competition_context=competition_context_block(state.get("competition_data")),
        snapshot_summary=offer.model_dump_json(indent=2, exclude_none=True),
        buyer_type_label=buyer_label,
        buyer_emphasis=buyer_emphasis,
        buyer_type_value=buyer_value or "b2b",
    )
    print("Drafting ICP ...")
    icp = invoke_structured_with_fallback(
        messages=[SystemMessage(content=system_message)],
        schema=ICP,
        log_label="generate_icp",
        thinking=False,
    )
    print(f"✅ ICP drafted.\n{icp.model_dump_json(indent=2, exclude_none=True)}")
    return {"icp": icp}


icp_refine_instructions = """
You are {specialist_name}, a {specialist_role}.

Your background: {specialist_background}
Your focus: {specialist_focus}
Your lens: {specialist_lens}
Your region: {specialist_region}
Your language/idiom: {specialist_language}
Your operating context: {specialist_operating_context}

You drafted the ICP below for this {offer_noun}. Review and finalize it before it seeds account
discovery.

DRAFT ICP
{draft_icp}

MARKET CONTEXT
{market_context}

COMPETITION CONTEXT
{competition_context}

REVIEW RULES
1. Fill every field the evidence supports; leave a field empty when the context cannot support it.
2. Prune guesses — anything not defensible from the {offer_noun}/market/competition context must go.
3. Buyer-type coherence: for consumer offers the `buyer_personas`, `target_channels` and
   `event_focus` must be rich enough to drive account discovery; for B2B the firmographics
   (`industries`, `company_sizes`, `buyer_titles`) carry the weight. Don't let a weak emphasis
   cripple the profile.
4. `competitor_leads` must come only from the competition context; never invent competitors.
5. Keep `geo` aligned to the market phase's target markets.
6. Expand `target_channels` with concrete names/typed placeholders + audience_fit + first_angle so
   account discovery can actually search them.

Return the FINAL, complete ICP — no commentary.
"""


def refine_icp(state: DetermineIcpState) -> dict:
    """Self-review pass: have the GTM specialist fill evidence-backed fields, prune
    guesses, and enforce buyer-type coherence on the draft ICP, marking completion."""
    specialist = state["specialist"]
    offer = as_offer_snapshot(state.get("offer_snapshot"))
    offer_noun = _offer_type_for(state)
    draft = state.get("icp")

    system_message = icp_refine_instructions.format(
        offer_noun=offer_noun,
        specialist_name=specialist.name,
        specialist_role=specialist.role_title,
        specialist_background=specialist.background,
        specialist_focus=specialist.focus,
        specialist_lens=specialist.distinct_lens or "—",
        specialist_region=specialist.region or "—",
        specialist_language=specialist.language or "—",
        specialist_operating_context=specialist.operating_context or "—",
        draft_icp=draft.model_dump_json(indent=2, exclude_none=True) if draft else "No draft — build the ICP from the context.",
        market_context=market_context_block(state.get("market_data")),
        competition_context=competition_context_block(state.get("competition_data")),
    )
    print("Refining ICP ...")
    icp = invoke_structured_with_fallback(
        messages=[SystemMessage(content=system_message)],
        schema=ICP,
        log_label="refine_icp",
        thinking=False,
    )
    print(f"✅ ICP finalized.\n{icp.model_dump_json(indent=2, exclude_none=True)}")
    return {"icp": icp, "icp_complete": True}


def build_icp_graph(checkpointer: bool = True):
    """Build the determine-ICP pipeline: the GTM specialist drafts a thorough,
    buyer-type-aware ICP from the market + competition understanding, then
    refines/prunes it in a self-review pass before it seeds account discovery.

    Compiled with a checkpointer by default so an interactive driver can resume
    interrupts; pass checkpointer=False when embedding as a subgraph node."""

    builder = StateGraph(DetermineIcpState)

    # -- Nodes --
    builder.add_node("generate_icp", generate_icp)
    builder.add_node("refine_icp", refine_icp)
    # -- Edges --
    builder.add_edge(START, "generate_icp")
    builder.add_edge("generate_icp", "refine_icp")
    builder.add_edge("refine_icp", END)

    # -- Compile --
    if checkpointer:
        memory_saver = MemorySaver()
        return builder.compile(checkpointer=memory_saver)
    return builder.compile()