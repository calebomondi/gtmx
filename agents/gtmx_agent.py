from langgraph.graph import START, END, StateGraph
from langgraph.checkpoint.memory import MemorySaver
from langgraph.checkpoint.base import BaseCheckpointSaver
from langchain_core.messages import HumanMessage, SystemMessage

from agents.states import OfferSessionState, OfferSections
from agents.llm.main import invoke_structured_with_fallback
from agents.sub_graphs.discover_product_service import build_discovery_agent
from agents.sub_graphs.create_specialists import build_specialist_graph
from agents.sub_graphs.understand_product import build_product_graph
from agents.sub_graphs.understand_market import build_market_graph
from agents.sub_graphs.understand_competition import build_competition_graph
from agents.sub_graphs.determine_icp import build_icp_graph
from agents.sub_graphs.account_discovery import build_account_discovery_graph
from agents.helpers import merge_snapshot, as_offer_snapshot, format_offer_material
from agents.sub_graphs.understand_product import _offer_type_for

from utils.log import logger


# Nested subgraphs can't own a checkpointer — the parent agent does. Built once
# and reused across run_* invocations instead of recompiling per call.
_DISCOVERY = build_discovery_agent(checkpointer=False)
_INTERVIEW_INTERVIEW = build_product_graph(checkpointer=False)
_MARKET_INTERVIEW = build_market_graph(checkpointer=False)
_COMPETITION_INTERVIEW = build_competition_graph(checkpointer=False)
_ICP_DETERMINATION = build_icp_graph(checkpointer=False)
_ACCOUNT_DISCOVERY = build_account_discovery_graph(checkpointer=False)


def run_interview(state: OfferSessionState) -> dict:
    """Run the product-specialist interview subgraph over the current session,
    feeding it the product/service specialist, the conversation so far, and the
    offer snapshot, then mapping the interview output back into session state."""

    result = _INTERVIEW_INTERVIEW.invoke({
        "specialist": state["specialist_team"].product_or_service_specialist,
        "max_num_turns": 4,
        "messages": list(state.get("messages") or []),
        "offer_snapshot": state.get("offer_snapshot"),
        "offer_type": state.get("offer"),
        "scraped_content": state.get("scraped_content"),
    })

    updates = {"messages": list(result.get("messages") or [])}
    if result.get("interview"):
        updates["product_transcript"] = result["interview"]
    if result.get("product_findings"):
        updates["product_findings"] = result["product_findings"]
    if result.get("product_domain_understanding"):
        updates["product_domain_understanding"] = result["product_domain_understanding"]
    if result.get("product_complete"):
        updates["product_complete"] = True
    return updates


def run_market_interview(state: OfferSessionState) -> dict:
    """Run the market-specialist interview subgraph: interview a market expert
    grounded on CURRENT web research, extract the structured market definition +
    product-market fit, write the market section, and fold the structured result
    into the product snapshot."""

    result = _MARKET_INTERVIEW.invoke({
        "specialist": state["specialist_team"].market_specialist,
        "max_num_turns": 5,
        "messages": list(state.get("messages") or []),
        "offer_snapshot": state.get("offer_snapshot"),
        "offer_type": state.get("offer"),
        "scraped_content": state.get("scraped_content"),
    })

    updates = {
        "messages": list(result.get("messages") or []),
    }
    if result.get("market_data"):
        updates["market_data"] = result["market_data"]
        snapshot = merge_snapshot(state.get("offer_snapshot"), result["market_data"])
        updates["offer_snapshot"] = snapshot
    if result.get("interview"):
        updates["market_transcript"] = result["interview"]
    if result.get("market_findings"):
        updates["market_findings"] = result["market_findings"]
    if result.get("product_market_fit_understanding"):
        updates["product_market_fit_understanding"] = result["product_market_fit_understanding"]
    if result.get("market_complete"):
        updates["market_complete"] = True
    return updates


def run_competition_interview(state: OfferSessionState) -> dict:
    """Run the competition-specialist interview subgraph: interview a competitive-
    intel expert grounded on CURRENT web research + the market context, extract
    the competitor set (3-5, URL-verified) + offer SWOD, write the section, and
    fold the competitors + SWOD into the offer snapshot."""

    result = _COMPETITION_INTERVIEW.invoke({
        "specialist": state["specialist_team"].competition_specialist,
        "max_num_turns": 5,
        "messages": list(state.get("messages") or []),
        "offer_snapshot": state.get("offer_snapshot"),
        "offer_type": state.get("offer"),
        "scraped_content": state.get("scraped_content"),
        "market_data": state.get("market_data"),
    })

    updates = {
        "messages": list(result.get("messages") or []),
    }
    competition_data = result.get("competition_data")
    if competition_data:
        updates["competition_data"] = competition_data
        snapshot = merge_snapshot(state.get("offer_snapshot"), competition_data)
        updates["offer_snapshot"] = snapshot
    if result.get("sections"):
        updates["sections"] = list(result["sections"])
    if result.get("interview"):
        updates["competition_transcript"] = result["interview"]
    if result.get("competition_findings"):
        updates["competition_findings"] = result["competition_findings"]
    if result.get("competitive_positioning_understanding"):
        updates["competitive_positioning_understanding"] = result["competitive_positioning_understanding"]
    if result.get("competition_complete"):
        updates["competition_complete"] = True
    return updates


def run_determine_icp(state: OfferSessionState) -> dict:
    """Run the determine-ICP subgraph: the GTM specialist drafts a buyer-type-
    aware ICP from the market + competition understanding, refines it in a
    self-review pass, and stores it in the session for account discovery."""

    result = _ICP_DETERMINATION.invoke({
        "specialist": state["specialist_team"].gtm_specialist,
        "offer_snapshot": state.get("offer_snapshot"),
        "offer_type": state.get("offer"),
        "scraped_content": state.get("scraped_content"),
        "market_data": state.get("market_data"),
        "competition_data": state.get("competition_data"),
    })

    updates = {}
    if result.get("icp"):
        updates["icp"] = result["icp"]
    if result.get("icp_complete"):
        updates["icp_complete"] = True
    return updates


# --- Final report sections -------------------------------------------------
#
# Every specialist produces research NOTES; the prose is written once, here, at
# the end. The reason is coherence rather than cost: a specialist writing its own
# section in isolation cannot know what the other two went on to find, so
# independently-written sections restate each other and quietly contradict each
# other — a market section asserting a segment the competition section has just
# shown is two companies, or a domain section using framing the market evidence
# does not support. One writer holding all three sets of notes cannot do that.
#
# It is also a large token saving: three long generation calls (each paying for
# the specialist's own accumulated sources) become one.

_SECTION_WRITER_INSTRUCTIONS = """You are an expert technical writer and editor.

Three specialists have independently researched this {offer_noun} and produced detailed
research NOTES. Your job is to turn those notes into the {offer_noun} section of a finished
report — three sections, all three written in this single pass so they agree with each other.

Write each section in markdown following this structure:
a. Title (## header)
b. Summary (### header)
c. Sources (### header)

The three sections are:

1. `domain_section` — grounds the {offer_noun} in its {offer_noun}/category domain space. Open
   with the domain background a reader needs in order to judge the {offer_noun}, then what the
   {offer_noun} is and how it works, then explicitly connect the two: how does the {offer_noun}
   fit its domain space, where does it align with, extend, deviate from, or outpace how
   {offer_nouns} in this category are expected to work, and what is novel about it relative to
   the domain? The {offer_noun} is the subject; the domain is the framing.

2. `market_section` — defines the {offer_noun}'s market and delivers a product-market fit
   verdict. Who buys it (buyer type: B2B/B2C/both), the target audience, the category
   conventions it must meet, the geographies, current demand/readiness, pricing (its actual
   tiers if the material states them, else current market-rate pricing benchmarked to the
   category, and what buyers will actually pay), how it reaches buyers, and the main barriers
   to adoption. Close with an explicit fit verdict (strong / moderate / weak / unclear) and
   the evidence for it.

3. `competition_section` — lays out the competitive landscape and how the {offer_noun} stacks
   up. Who the principal players are, then a comparison against the real named competitors:
   where the {offer_noun} beats them, where it falls short, what is genuinely unique about it,
   and its strengths, weaknesses, opportunities and differentiators in relation to them. Name
   only competitors that actually appear in the notes.

Rules that apply to all three:
- Use the notes as your evidence base. Do not introduce a fact that is not in them, and do not
  invent a competitor, a number, or a citation.
- Be specific. Keep named technologies, products, organisations, figures and dates exactly as
  the notes state them. These are what the reader will act on.
- The three sections are one report, so: do not restate a point that another section already
  makes, refer to it instead where a cross-reference helps, and never contradict another
  section. If two specialists disagree, say so explicitly rather than picking one silently.
- Preserve the honesty of the research. Weak evidence, contested claims and genuine gaps
  should stay visible — a report that overstates the evidence is worse than one that admits
  the limits.
- In the Sources section, list only the sources the notes attribute to that section. Provide
  full links. Separate each by a newline, with two trailing spaces to force the line break in
  Markdown. Combine duplicate sources, for example this is not correct:

  [3] https://example.com/a
  [4] https://example.com/a

  There should be no redundant sources. It should simply be:

  [3] https://example.com/a

- Make each title engaging based on that specialist's focus area.
- Include no preamble before the title of the report, and do not mention the names of
  interviewers or experts.
- Aim for approximately {domain_words} words maximum for the domain summary, {market_words}
  for the market summary, and {competition_words} for the competition summary, each excluding
  its own title and sources."""


def write_sections(state: OfferSessionState) -> dict:
    """Compose the report's three sections in one pass, from all three sets of notes.

    Runs after every interview has finished, so the writer can see what each
    specialist actually found. Returns the sections in the fixed order the
    frontend expects: domain, market, competition.
    """

    offer = as_offer_snapshot(state.get("offer_snapshot"))
    offer_noun = _offer_type_for(state)
    material = format_offer_material(offer, state.get("scraped_content"), offer_noun)

    notes = {
        "DOMAIN": state.get("product_findings") or "",
        "MARKET": state.get("market_findings") or "",
        "COMPETITION": state.get("competition_findings") or "",
    }
    missing = [k for k, v in notes.items() if not v]
    if missing:
        # Rather than emit a section with nothing behind it, say which
        # specialist is missing so the gap is visible in the logs and in the
        # user-facing error path.
        logger.warning("write_sections: no research notes from %s", ", ".join(missing))

    system_message = _SECTION_WRITER_INSTRUCTIONS.format(
        offer_noun=offer_noun,
        offer_nouns=f"{offer_noun}s",
        domain_words=400,
        market_words=500,
        competition_words=500,
    )

    body = [
        f"{offer_noun.upper()} MATERIAL:\n{material or 'None provided.'}\n",
        f"DOMAIN RESEARCH NOTES:\n{notes['DOMAIN'] or 'None provided.'}\n",
        f"MARKET RESEARCH NOTES:\n{notes['MARKET'] or 'None provided.'}\n",
        f"COMPETITION RESEARCH NOTES:\n{notes['COMPETITION'] or 'None provided.'}\n",
    ]
    # The transcripts are the raw record behind the notes. Include them only when
    # there is room, since the notes already carry the distilled substance and
    # three transcripts are the largest single input in the run.
    transcripts = {
        "DOMAIN": state.get("product_transcript") or "",
        "MARKET": state.get("market_transcript") or "",
        "COMPETITION": state.get("competition_transcript") or "",
    }
    if any(transcripts.values()):
        body.append(
            "INTERVIEW TRANSCRIPTS (for verification of the notes; where the two "
            "disagree, trust the notes):\n"
            + "\n".join(f"[{k} INTERVIEW]\n{v}" for k, v in transcripts.items() if v)
        )

    logger.info("write_sections: composing 3 sections from %d chars of notes", sum(len(v) for v in notes.values()))
    sections = invoke_structured_with_fallback(
        messages=[
            SystemMessage(content=system_message),
            HumanMessage(content="Write the three report sections from these notes.\n\n" + "\n".join(body)),
        ],
        schema=OfferSections,
        log_label="write_sections",
        thinking=True,
    )

    if sections is None:
        # The interviews' own output is already saved; only the prose is missing.
        logger.error("write_sections: could not compose sections; interviews and notes are preserved")
        return {}

    return {
        "sections": [
            sections.domain_section,
            sections.market_section,
            sections.competition_section,
        ],
    }


def run_account_discovery(state: OfferSessionState) -> dict:
    """Run the GTM-stage account-discovery subgraph: given the ICP already
    determined upstream, find target accounts / consumer-reach channels with
    current trigger events, validate them, and write the GTM section."""

    result = _ACCOUNT_DISCOVERY.invoke({
        "specialist": state["specialist_team"].gtm_specialist,
        "offer_snapshot": state.get("offer_snapshot"),
        "offer_type": state.get("offer"),
        "scraped_content": state.get("scraped_content"),
        "market_data": state.get("market_data"),
        "competition_data": state.get("competition_data"),
        "icp": state.get("icp"),
    })

    updates = {}
    if result.get("accounts"):
        updates["accounts"] = result["accounts"]
    if result.get("sections"):
        updates["sections"] = list(result["sections"])
    if result.get("go_to_market_understanding"):
        updates["go_to_market_understanding"] = result["go_to_market_understanding"]
    if result.get("gtm_complete"):
        updates["gtm_complete"] = True
    return updates


def build_agent(checkpointer: BaseCheckpointSaver | None = None):
    """Build the GTMX agent state graph: product discovery ->
    create_specialists -> understand_product -> understand_market ->
    understand_competition -> determine_icp -> account_discovery (GTM). The
    discovery phase is interactive: its interrupts surface on the top-level
    invoke and resume via Command(resume=...) with the same thread config.

    `checkpointer` lets callers (e.g. the backend) supply a durable saver such
    as AsyncSqliteSaver; falls back to an in-memory saver for interactive
    drivers and tests."""

    builder = StateGraph(OfferSessionState)

    # -- Nodes (subgraph-based) --
    builder.add_node("discover_product_service", _DISCOVERY)
    builder.add_node("create_specialists", build_specialist_graph())
    builder.add_node("understand_product", run_interview)
    builder.add_node("understand_market", run_market_interview)
    builder.add_node("understand_competition", run_competition_interview)
    builder.add_node("determine_icp", run_determine_icp)
    builder.add_node("write_sections", write_sections)
    # builder.add_node("account_discovery", run_account_discovery)

    # -- Edges --
    builder.add_edge(START, "discover_product_service")
    builder.add_edge("discover_product_service", "create_specialists")
    # Product and market research are independent, so they run in the same
    # super-step and LangGraph executes them concurrently (these are sync node
    # functions, so it hands them to a thread pool). Competition stays strictly
    # after both: it reads market_data and the merged message history, and a
    # competitive analyst briefed without the market is the one thing that
    # would cost the report its coherence.
    #
    # Safe to overlap because the two nodes write disjoint keys -- run_interview
    # never touches offer_snapshot, and the only shared channel is `messages`,
    # which OfferSessionState already reduces with add_messages (states.py:730).
    # The per-interview turn counters are keyed on the expert's name, so they
    # cannot collide either.
    builder.add_edge("create_specialists", "understand_product")
    builder.add_edge("create_specialists", "understand_market")
    builder.add_edge("understand_product", "understand_competition")
    builder.add_edge("understand_market", "understand_competition")
    builder.add_edge("understand_competition", "determine_icp")
    # The single section writer runs last so it can see all three specialists'
    # notes at once. Putting it after determine_icp rather than after the last
    # interview keeps it correct if the GTM stage is re-enabled.
    builder.add_edge("determine_icp", "write_sections")
    builder.add_edge("write_sections", END)
    # builder.add_edge("account_discovery", END)

    # -- Compile --
    return builder.compile(checkpointer=checkpointer or MemorySaver())