from datetime import date, timedelta

from langgraph.graph import START, END, StateGraph
from langgraph.checkpoint.memory import MemorySaver
from langchain_core.messages import HumanMessage, SystemMessage, get_buffer_string, AIMessage

from agents.llm.main import invoke_structured_with_fallback
from agents.states import InterviewState, SearchQuery, MarketExtraction, MarketFindings
from agents.context_budget import distill_documents
from agents.helpers import as_offer_snapshot, format_offer_material
from agents.sub_graphs.understand_product import (
    _offer_type_for,
    join_context,
    seed_product_context,
    save_interview,
    route_messages,
    route_after_question,
)
from config import Config
from data_sources.scraping.exa import search_and_scrape
from utils.log import logger


# --- Market understanding ---


def _recency_cutoff(days: int) -> str:
    """ISO date (YYYY-MM-DD) for the oldest source the market interview may use."""
    return (date.today() - timedelta(days=days)).isoformat()


market_question_instructions = """
You are {specialist_name}, a {specialist_role}.

Your background: {specialist_background}
Your focus: {specialist_focus}
Your lens: {specialist_lens}
Your region: {specialist_region}
Your language/idiom: {specialist_language}
Your operating context: {specialist_operating_context}

You are interviewing an expert who knows this {offer_noun}'s market and buyer landscape well
to define the market and determine the product-market fit, grounded in CURRENT market
conditions (not history).

OFFER
Name: {offer_name}
Description: {offer_description}

KNOWN FACTS
{snapshot_summary}

GOAL
Define the market for this {offer_noun} and determine whether/how well it fits:
- Who buys it (buyer type: B2B, B2C, or both) and who the target audience is
- What category it sits in and the conventions of that category (what buyers expect from
  an offering in it)
- Current demand and how ready/inclined the market is to buy
- Pricing norms and price points in the category, and what buyers are willing to pay
- How the {offer_noun} reaches buyers (channels/distribution)
- Which geographies it is or could be sold in
- The barriers standing between the target audience and adoption
- Whether the offering actually matches what the market wants and will pay for (the
  product-market fit verdict)

Treat KNOWN FACTS as background: don't re-litigate areas already covered, and steer
into areas that are still thin, missing, or vague so the picture becomes complete.
Each question should flow naturally from interviewing about the market — not check a
list of fields.

RULES
1. Introduce yourself briefly and ask your question.
2. Stay in character as {specialist_name} throughout.
3. Ask one focused question at a time.
4. Build on previous answers — don't repeat questions.
5. Drive your questioning through your distinctive lens, and keep it anchored to
   the markets in your region — ask in plain language, grounded in how the category
   actually works where this {offer_noun} operates.
6. When the market picture is sufficiently complete or you are otherwise satisfied with
   your understanding, end the interview with:
   "Thank you so much for your help!"

OUTPUT
Return only the message content — no structured fields.
"""


def generate_question(state: InterviewState) -> dict:
    """Have the market specialist ask the next gap-filling question."""

    specialist = state["specialist"]
    messages = state.get("messages", [])
    offer = as_offer_snapshot(state.get("offer_snapshot"))
    offer_noun = _offer_type_for(state)

    system_message = market_question_instructions.format(
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
        snapshot_summary=offer.model_dump_json(indent=2, exclude_none=True),
    )
    print(f"Generating market question ...")
    question = invoke_structured_with_fallback(
        messages=[SystemMessage(content=system_message)] + messages,
        log_label="generate_market_question",
        thinking=False,
    )
    print(f"✅ Market question generated.\n{question}")

    return {"messages": [AIMessage(content=question)]}


market_search_instructions = """
You will be given a conversation between a {offer_noun} market specialist and a market
expert, plus the {offer_noun}'s own material.

Your goal is to generate a well-structured web-search query about the CURRENT MARKET and
BUYER landscape for the category the {offer_noun} operates in — NOT about the {offer_noun}
or brand itself.

First, analyze the full conversation.

Pay particular attention to the final question posed by the market specialist.

RULES
1. Identify the category and market the {offer_noun} operates in (drawn from the
   {offer_noun}'s material and the conversation).
2. Build the query around that MARKET / CATEGORY only — buyer segments, demand, pricing
   norms and price points, category conventions, distribution channels, and geographic
   demand.
3. Bias toward RECENT, current market data — the query should surface today's conditions,
   not historical snapshots. (Recency is enforced on the search itself too.)
4. When target markets are given, scope the query toward how the market and buyers
   actually behave in those markets.
5. NEVER include the {offer_noun}'s name or brand in the query.
6. Also provide a `broader_query`: a simpler, less specific version of the same
   market/category query, to use as a fallback if the primary query gets no results.
"""


def search_web(state: InterviewState) -> dict:
    """Turn the specialist's latest question into a market-focused web-search
    query (excluding the {offer_noun} name), gather CURRENT supporting documents via
    Exa (recency-gated), and append them as formatted context for the expert."""

    specialist = state["specialist"]
    offer = as_offer_snapshot(state.get("offer_snapshot"))
    offer_noun = _offer_type_for(state)
    material = format_offer_material(offer, state.get("scraped_content"), offer_noun)
    markets = ", ".join(offer.target_geo or []) or "not specified"
    start_published_date = _recency_cutoff(Config().market_recency_days)

    print(f"Creating market search query...")
    # Degrade to "no web docs" rather than failing the run: the specialist still
    # has the offer's own material to interview from.
    try:
        search_query = invoke_structured_with_fallback(
            messages=[
                SystemMessage(content=market_search_instructions.format(
                    offer_noun=offer_noun,
                )),
                HumanMessage(content=(
                    f"SPECIALIST'S LENS: {specialist.distinct_lens or specialist.focus}\n"
                    f"TARGET MARKETS: {markets}\n\n"
                    f"{offer_noun.upper()} MATERIAL:\n{material or 'None provided.'}\n\n"
                    f"CONVERSATION:\n{get_buffer_string(state['messages'])}"
                )),
            ],
            schema=SearchQuery,
            log_label="search_web:market_search_query",
            thinking=False,
        )
    except Exception as exc:
        logger.warning(
            "search_web: could not build a market search query (%s); "
            "continuing without web search for this turn",
            exc,
        )
        print(f"⚠️  Market search query failed — continuing without web search.")
        return {"context": []}
    print(f"✅ Market search query generated.\n{search_query.search_query}")

    print(f"Searching web (published after {start_published_date}) ...")
    search_docs = search_and_scrape(
        search_query.search_query, Config(), num_results=3,
        start_published_date=start_published_date,
    )
    if not search_docs and search_query.broader_query:
        print(f"Primary search empty — retrying with broader query:\n{search_query.broader_query}")
        search_docs = search_and_scrape(
            search_query.broader_query, Config(), num_results=3,
            start_published_date=start_published_date,
        )
    print(f"{"✅ Search complete" if search_docs else "❌ Search failed"}")

    # Condensed once per URL and cached; see understand_product.search_web.
    formatted_search_docs = distill_documents(
        search_docs,
        focus=(
            f"current market conditions, buyer types and demand for this category, "
            f"as surfaced by this search: {search_query.search_query}"
        ),
        log_label="search_web:distill_market_doc",
    )

    return {"context": [formatted_search_docs]}


market_answer_instructions = """
You are a {offer_noun} market expert being interviewed by a {offer_noun} market specialist.

Here is the specialist's area of focus: {goals}.

Your goal is to answer a question posed by the interviewer about the {offer_noun}'s market,
grounded in CURRENT market facts.

To answer the question, use this context:

{context}

The context begins with the {offer_noun}'s OWN MATERIAL (the document labelled
"{offer_noun}'s own material") — treat that as authoritative, provided facts about the
{offer_noun} being interviewed (what it does, who it is for, any pricing or geographies
it states). The remaining documents describe the {offer_noun}'s market/category as of today.

When answering questions, follow these guidelines:

1. Use only the information provided in the context.
2. Do not introduce external information or make assumptions beyond what is explicitly
   stated in the context.
3. The context contains sources at the topic of each individual document.
4. Ground answers in CURRENT market conditions. If a claim relies on older/estimated data,
   say so explicitly rather than presenting it as today's fact.
5. If the context does not contain enough evidence to answer part of the question, say so
   explicitly rather than inventing facts — a partial answer with a stated gap is better
   than a confident guess.
6. List your sources in order at the bottom of your answer. [1] Source 1, [2] Source 2, etc
7. If the source is: <Document source="assistant/docs/llama3_1.pdf" page="7"/>' then just
   list: [1] assistant/docs/llama3_1.pdf, page 7. And skip the addition of the brackets
   as well as the Document source preamble in your citation.
"""


def generate_aswer(state: InterviewState) -> dict:
    """Have the market expert answer using only the context (offer material +
    current market docs)."""

    specialist = state["specialist"]
    messages = state.get("messages", [])
    context = join_context(state.get("context"))

    system_message = market_answer_instructions.format(
        offer_noun=_offer_type_for(state),
        goals=specialist.persona,
        context=context,
    )

    print("Generating market answer ...")
    answer = invoke_structured_with_fallback(
        messages=[SystemMessage(content=system_message)] + messages,
        log_label="generate_market_answer",
        thinking=True,
    )
    print(f"{"✅ Generated answer" if answer else "❌ Failed to generate answer!"}")

    return {"messages": [AIMessage(content=answer, name="expert")]}


market_extraction_instructions = """
You are a market analyst. From the interview below plus the {offer_noun}'s own material and
the CURRENT market sources, produce the structured market definition for the {offer_noun}.

The {offer_noun}'s OWN material (the block labelled "{offer_noun}'s own material") is authoritative:
pricing stated there comes from the {offer_noun} itself; geographies stated there are where it
operates. The remaining documents describe the current market/category.

Only state what the interview and sources actually support. If an area is genuinely thin or
unsupported, return None / empty rather than inventing figures or claims.

Fields:
- buyer_type: B2B, B2C, or both, based on evidence. Use "both" when it clearly serves both.
- category: pick the closest ProductCategory enum value.
- target_audience: who the {offer_noun} is for (ICP + segments), grounded in evidence.
- pricing:
  * If pricing is present in the {offer_noun}'s OWN MATERIAL, extract those tiers as-is
    (tier name, monthly_sub, yearly_sub, features included) and set pricing_source = "site".
  * If the {offer_noun}'s own material does NOT provide pricing, suggest realistic tiers based
    on CURRENT market rates found in the research and set pricing_source = "market_suggestion".
  * Leave the list empty only when neither source supports a defensible tier.
- target_geo: geographies the {offer_noun} serves, prioritised by evidence from the
  {offer_noun}'s own material, else from current market research.
- category_conventions: the conventions, norms, and expectations an offering in this category
  must meet to be credible (what "good" looks like to buyers).
- market_demand: current demand level and readiness signals for the category — how much the
  market wants this, and the evidence of that demand.
- willingness_to_pay: what buyers in the category are willing to pay / the budget norms that
  govern purchase decisions.
- distribution_channels: how the {offer_noun} is bought and sold in the category — direct
  sales, marketplace/platform, partnerships, retail, etc.
- adoption_barriers: obstacles between the target audience and adoption (cost, trust,
  switching, regulatory, awareness, etc.).
- growth_outlook: growing / stable / declining / unclear — the category's current trajectory.
- market_fit: strong / moderate / weak / unclear — how well the {offer_noun} fits its defined
  market (matches buyer needs, price points, and category conventions).
- market_fit_reasoning: brief, evidence-based explanation citing the sources used.

OUTPUT
Return only the structured fields — no commentary.
"""


def extract_market_data(state: InterviewState) -> dict:
    """Extract the structured market definition + product-market fit from the
    interview transcript and the gathered context."""

    context = join_context(state.get("context"))
    interview = state.get("interview") or get_buffer_string(state.get("messages") or [])

    print("Extracting market data ...")
    market_data = invoke_structured_with_fallback(
        messages=[
            SystemMessage(content=market_extraction_instructions.format(
                offer_noun=_offer_type_for(state),
            )),
            HumanMessage(
                content=(
                    f"INTERVIEW TRANSCRIPT:\n{interview}\n\n"
                    f"SOURCES (offer material + current market docs):\n{context}"
                )
            ),
        ],
        schema=MarketExtraction,
        log_label="extract_market_data",
        thinking=False,
    )
    print(f"✅ Market data extracted: {market_data.model_dump_json(exclude_none=True)}")
    return {"market_data": market_data}


market_findings_instructions = """You are an expert market analyst.

Your task is to produce detailed RESEARCH NOTES that DEFINE the {offer_noun}'s market and
DETERMINE its product-market fit, from what the market specialist actually learned in the
interview, the {offer_noun}'s own material, and CURRENT market sources.

These notes are the raw material for one section of a finished report, written later by
someone who will also see the domain and competitive analyses. So:

- Write NOTES, not report prose. No report title, no "## Title" / "### Summary" scaffolding.
- Be specific and evidence-dense. Another writer cannot recover what you leave out, but they
  can trim what you give them.
- Keep every concrete claim: segment sizes, growth rates, price points, buyer segments,
  channel shares, named organisations, dates. These are what get cited.
- Note where the evidence is thin, estimated or may be dated, and say so.

The context contains the {offer_noun}'s OWN MATERIAL (the document labelled "{offer_noun}'s own
material" — authoritative facts about the {offer_noun}: what it is, who it is for, its
features, and any pricing/geographies it states) followed by documents about the
MARKET/CATEGORY the {offer_noun} operates in, as of today (buyers, demand, pricing norms,
geographies, channels, barriers).

1. Analyze the content of the source documents:
- The name of each source document is at the start of the document, with the <Document tag.
- Separate what is fact about the {offer_noun} itself from what describes the market/category.

2. Organise the notes with markdown sub-headers of your choosing (###). Cover:
- The current state of the market/category the {offer_noun} operates in
- The {offer_noun}'s market definition: who buys it (buyer type: B2B/B2C/both), the target
  audience, the category conventions it must meet, the geographies it serves, and the
  demand/readiness the market currently shows
- Pricing: the {offer_noun}'s actual tiers if present in its own material, else the
  current market-rate pricing it should use, benchmarked to the category, and what buyers
  are willing to pay
- How the {offer_noun} reaches buyers (channels) and the main barriers to adoption
- An explicit product-market fit verdict (strong / moderate / weak / unclear) with
  the evidence: where the offering matches what the market wants and will pay for, and where
  it deviates
- What the market specialist learned in the interview that the sources alone do not say
- Open questions and weak points

Keep the {offer_noun} as the subject and the market as the framing. Do not mention the names of
interviewers or experts. Ground everything in CURRENT market data; flag estimates or anything
that may be dated.

The focus area of the {offer_noun} market specialist is:
{focus}

3. Also return `product_market_fit_understanding` as a brief standalone synthesis of the fit;
    target 40 words and never exceed 50 words.

4. End with a numbered list of the source documents you actually used:

### Sources
[1] Link or Document name
[2] Link or Document name

Provide full links to relevant websites or specific document paths. Separate each source by a
newline. Use two spaces at the end of each line to create a newline in Markdown.

Be sure to combine sources. For example this is not correct:

[3] https://ai.meta.com/blog/meta-llama-3-1/
[4] https://ai.meta.com/blog/meta-llama-3-1/

There should be no redundant sources. It should simply be:

[3] https://ai.meta.com/blog/meta-llama-3-1/

5. Aim for approximately {word_count} words of notes, excluding the source list."""


def write_findings(state: InterviewState):
    """Node to write the market specialist's research notes.

    Produces notes rather than a report section: the report prose is composed
    once at the end, by a single writer that can see the domain and competition
    specialists' notes as well, so the three sections can agree with each other.
    """

    context = join_context(state.get("context"), label="market_findings")
    interview = state.get("interview") or ""
    specialist = state["specialist"]
    offer = as_offer_snapshot(state.get("offer_snapshot"))
    offer_noun = _offer_type_for(state)
    material = format_offer_material(offer, state.get("scraped_content"), offer_noun)

    system_message = market_findings_instructions.format(
        offer_noun=offer_noun,
        focus=specialist.focus,
        word_count=state.get("section_word_count", 500),
    )
    print("Writing market findings ...")
    notes = invoke_structured_with_fallback(
        messages=[
            SystemMessage(content=system_message),
            HumanMessage(content=(
                "Write the notes from what the market specialist actually learned in the "
                f"interview, the {offer_noun}'s own material, and the current market sources.\n\n"
                f"SPECIALIST'S LENS: {specialist.distinct_lens or specialist.focus}\n\n"
                f"INTERVIEW TRANSCRIPT:\n{interview or 'None provided.'}\n\n"
                f"{offer_noun.upper()} MATERIAL:\n{material or 'None provided.'}\n\n"
                f"MARKET SOURCES:\n{context}"
            )),
        ],
        schema=MarketFindings,
        log_label="write_findings:market",
    )
    print("✅ Market findings written" if notes else "❌ Market findings not written!")
    return {
        "market_findings": notes.findings,
        "product_market_fit_understanding": notes.product_market_fit_understanding,
        "market_complete": True,
    }


def build_market_graph(checkpointer: bool = True):
    """Build the understand-market interview loop: market specialist interviews a
    market expert grounded on CURRENT web research + the {offer_noun}'s own material,
    then extracts structured market data and writes its research notes.

    Compiled with a checkpointer by default so an interactive driver can resume
    interrupts; pass checkpointer=False when embedding as a subgraph node."""

    builder = StateGraph(InterviewState)

    # -- Nodes --
    builder.add_node("seed_product_context", seed_product_context)
    builder.add_node("ask_question", generate_question)
    builder.add_node("search_web", search_web)
    builder.add_node("answer_question", generate_aswer)
    builder.add_node("save_interview", save_interview)
    builder.add_node("extract_market_data", extract_market_data)
    builder.add_node("write_findings", write_findings)
    # -- Edges --
    builder.add_edge(START, "seed_product_context")
    builder.add_edge("seed_product_context", "ask_question")
    builder.add_conditional_edges(
        "ask_question",
        route_after_question,
        ['search_web', 'save_interview']
    )
    builder.add_edge("search_web", "answer_question")
    builder.add_conditional_edges(
        "answer_question",
        route_messages,
        ['ask_question', 'save_interview']
    )
    builder.add_edge("save_interview", "extract_market_data")
    builder.add_edge("extract_market_data", "write_findings")
    builder.add_edge("write_findings", END)

    # -- Compile --
    if checkpointer:
        memory_saver = MemorySaver()
        return builder.compile(checkpointer=memory_saver)
    return builder.compile()