from datetime import date, timedelta

from langgraph.graph import START, END, StateGraph
from langgraph.checkpoint.memory import MemorySaver
from langchain_core.messages import HumanMessage, SystemMessage, get_buffer_string, AIMessage

from agents.llm.main import invoke_structured_with_fallback
from agents.states import InterviewState, CompetitionSearchQuery, CompetitionExtraction, CompetitionFindings
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
from data_sources.scraping.exa import search_and_scrape, scrape_url
from utils.log import logger


# --- Competition understanding ---


def _recency_cutoff(days: int) -> str:
    """ISO date (YYYY-MM-DD) for the oldest source the competition interview may use."""
    return (date.today() - timedelta(days=days)).isoformat()


def _market_context_block(state: InterviewState) -> str:
    """Render the market understanding so the competition specialist and section
    writer can scope the competitive landscape (category, buyer, geo, pricing)."""
    market = state.get("market_data")
    if not market:
        return "No market data available — scope to the offer/category alone."
    return market.model_dump_json(indent=2, exclude_none=True)


competition_question_instructions = """
You are {specialist_name}, a {specialist_role}.

Your background: {specialist_background}
Your focus: {specialist_focus}
Your lens: {specialist_lens}
Your region: {specialist_region}
Your language/idiom: {specialist_language}
Your operating context: {specialist_operating_context}

You are interviewing an expert who knows this {offer_noun}'s competitive landscape well to
identify the {offer_noun}'s REAL competitors — ideally 3 to 5 of them — and understand how
the {offer_noun} stacks up against each, grounded in CURRENT market research (not history).

OFFER
Name: {offer_name}
Description: {offer_description}

MARKET CONTEXT (already gathered — treat as fact)
{market_context}

KNOWN FACTS
{snapshot_summary}

GOAL
Determine the {offer_noun}'s ideal competitor set within the target geographies ({target_geo}):
- Who actually competes for this buyer/category (the strongest 3-5, not an exhaustive list)
- How each competitor positions and what they offer
- How the {offer_noun} compares to each — where it wins, where it loses, what is unique
- What gaps in the competitive landscape the {offer_noun} could exploit

Treat KNOWN FACTS and MARKET CONTEXT as background: don't re-litigate areas already
covered, and steer into areas that are still thin, missing, or vague so the picture
becomes complete. Each question should flow naturally from interviewing about the
competitive landscape — not check a list of fields.

RULES
1. Introduce yourself briefly and ask your question.
2. Stay in character as {specialist_name} throughout.
3. Ask one focused question at a time.
4. Build on previous answers — don't repeat questions.
5. Drive your questioning through your distinctive lens, and keep it anchored to
   the markets in your region — ask in plain language, grounded in how competition
   in this category actually works where the {offer_noun} operates.
6. When the competitive picture is sufficiently complete or you are otherwise satisfied
   with your understanding, end the interview with:
   "Thank you so much for your help!"

OUTPUT
Return only the message content — no structured fields.
"""


def generate_question(state: InterviewState) -> dict:
    """Have the competition specialist ask the next gap-filling question."""

    specialist = state["specialist"]
    messages = state.get("messages", [])
    offer = as_offer_snapshot(state.get("offer_snapshot"))
    offer_noun = _offer_type_for(state)
    target_geo = ", ".join(offer.target_geo or []) or "global"

    system_message = competition_question_instructions.format(
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
        market_context=_market_context_block(state),
        snapshot_summary=offer.model_dump_json(indent=2, exclude_none=True),
        target_geo=target_geo,
    )
    print(f"Generating competition question ...")
    question = invoke_structured_with_fallback(
        messages=[SystemMessage(content=system_message)] + messages,
        log_label="generate_competition_question",
        thinking=False,
    )
    print(f"✅ Competition question generated.\n{question}")

    return {"messages": [AIMessage(content=question)]}


competition_search_instructions = """
You will be given a conversation between a {offer_noun} competition specialist and a
competitive-intel expert, plus the {offer_noun}'s own material and the market context
already gathered.

Your goal is to generate web-search queries that surface the {offer_noun}'s REAL competitors
and its competitive landscape as of today — grounded in CURRENT sources.

First, analyze the full conversation and the market context (especially the target
geographies).

Generate TWO queries:

1. `direct_query` — hunts for the {offer_noun}'s DIRECT competitors. This query MAY include
   the {offer_noun}/brand name (e.g., "{offer_name} competitors", "alternatives to
   {offer_name}"). Only include the {offer_noun} name when it is distinctive enough to
   surface meaningful comparison content.

2. `landscape_query` — paints the competitive LANDSCAPE for the category in the target
   geographies (e.g., "top <category> platforms in <geo>", "best <category> tools for
   <geo> <year>"). NEVER include the {offer_noun}'s or brand's name in this one — it must
   stand alone as a category search.

RULES
1. Bias both queries toward RECENT, current competitive data — today's players, today's
   positioning. (Recency is enforced on the search itself too.)
2. State the target geographies in the landscape query when they are known.
3. NEVER fabricate competitor names in the queries — let the search surface them.
4. Also provide a `broader_query`: a simpler, less specific fallback of the same
   market/category landscape, used when the direct/landscape queries get no results.
"""


def search_web(state: InterviewState) -> dict:
    """Turn the specialist's latest question into direct + landscape search queries
    (product name allowed in the direct query, geo baked into the landscape query),
    gather CURRENT sources via Exa (recency-gated), and append them as formatted
    context for the expert."""

    specialist = state["specialist"]
    offer = as_offer_snapshot(state.get("offer_snapshot"))
    offer_noun = _offer_type_for(state)
    material = format_offer_material(offer, state.get("scraped_content"), offer_noun)
    markets = ", ".join(offer.target_geo or []) or "not specified"
    start_published_date = _recency_cutoff(Config().market_recency_days)
    year = date.today().year

    print(f"Creating competition search queries...")
    # Same degradation as the other interviews: no web docs beats no interview.
    try:
        queries = invoke_structured_with_fallback(
            messages=[
                SystemMessage(content=competition_search_instructions.format(
                    offer_noun=offer_noun,
                    offer_name=offer.offer_name or "the offer",
                    year=year,
                )),
                HumanMessage(content=f"SPECIALIST'S LENS: {specialist.distinct_lens or specialist.focus}\nTARGET MARKETS: {markets}\n\nMARKET CONTEXT:\n{_market_context_block(state)}\n\n{offer_noun.upper()} MATERIAL:\n{material or 'None provided.'}\n\nCONVERSATION:\n{get_buffer_string(state['messages'])}"),
            ],
            schema=CompetitionSearchQuery,
            log_label="search_web:competition_search_queries",
            thinking=False,
        )
    except Exception as exc:
        logger.warning(
            "search_web: could not build competition search queries (%s); "
            "continuing without web search for this turn",
            exc,
        )
        print(f"⚠️  Competition search query failed — continuing without web search.")
        return {"context": []}
    print(f"✅ Competition queries generated.\ndirect: {queries.direct_query}\nlandscape: {queries.landscape_query}")

    print(f"Searching web (published after {start_published_date}, geo: {markets}) ...")
    docs = []
    seen = set()
    for q in [queries.direct_query, queries.landscape_query]:
        if not q:
            continue
        results = search_and_scrape(
            q, Config(), num_results=3, start_published_date=start_published_date
        )
        for d in results:
            if d["url"] not in seen:
                seen.add(d["url"])
                docs.append(d)
        if not results:
            print(f"  -> empty: {q}")

    if not docs and queries.broader_query:
        print(f"Direct/landscape empty — retrying with broader query:\n{queries.broader_query}")
        docs = search_and_scrape(
            queries.broader_query, Config(), num_results=3,
            start_published_date=start_published_date,
        )
    print(f"{"✅ Search complete" if docs else "❌ Search failed"} ({len(docs)} unique docs)")

    # Condensed once per URL and cached; see understand_product.search_web. This
    # one fans out over 6 docs (two queries x three results), so it is the
    # single biggest win from the concurrent helper.
    formatted_search_docs = distill_documents(
        docs,
        focus=(
            f"named competitors and how the {offer_noun} stacks up against them, "
            f"as surfaced by these searches: {queries.direct_query} / "
            f"{queries.landscape_query}"
        ),
        log_label="search_web:distill_competition_doc",
    )

    return {"context": [formatted_search_docs]}


competition_answer_instructions = """
You are a {offer_noun} competitive-intelligence expert being interviewed by a {offer_noun}
competition specialist.

Here is the specialist's area of focus: {goals}.

Your goal is to answer a question posed by the interviewer about the {offer_noun}'s real
competitors and how it compares, grounded in CURRENT competitive facts.

To answer the question, use this context:

{context}

The context begins with the {offer_noun}'s OWN MATERIAL (the document labelled
"{offer_noun}'s own material") — treat that as authoritative, provided facts about the
{offer_noun} being interviewed. The remaining documents describe the {offer_noun}'s
competitive landscape as of today: who competes, how they position, what they offer.

When answering questions, follow these guidelines:

1. Use only the information provided in the context.
2. Do not introduce external information or make assumptions beyond what is explicitly
   stated in the context.
3. Name REAL competitors only — those that actually appear in the context or are well
   established in this category. Never invent a competitor name.
4. Ground answers in CURRENT competitive conditions. If a claim relies on older/estimated
   data, say so explicitly rather than presenting it as today's fact.
5. If the context does not contain enough evidence to answer part of the question, say so
   explicitly rather than inventing facts — a partial answer with a stated gap is better
   than a confident guess.
6. List your sources in order at the bottom of your answer. [1] Source 1, [2] Source 2, etc
7. If the source is: <Document source="assistant/docs/llama3_1.pdf" page="7"/>' then just
   list: [1] assistant/docs/llama3_1.pdf, page 7. And skip the addition of the brackets
   as well as the Document source preamble in your citation.
"""


def generate_aswer(state: InterviewState) -> dict:
    """Have the competitive-intel expert answer using only the context (offer
    material + current competitive docs)."""

    specialist = state["specialist"]
    messages = state.get("messages", [])
    context = join_context(state.get("context"))

    system_message = competition_answer_instructions.format(
        offer_noun=_offer_type_for(state),
        goals=specialist.persona,
        context=context,
    )

    print("Generating competition answer ...")
    answer = invoke_structured_with_fallback(
        messages=[SystemMessage(content=system_message)] + messages,
        log_label="generate_competition_answer",
        thinking=True,
    )
    print(f"{"✅ Generated answer" if answer else "❌ Failed to generate answer!"}")

    return {"messages": [AIMessage(content=answer, name="expert")]}


competition_extraction_instructions = """
You are a competitive analyst. From the interview below plus the {offer_noun}'s own material,
the market context, and the CURRENT competitive sources, produce the structured competitive
output for the {offer_noun}.

The {offer_noun}'s OWN material (the block labelled "{offer_noun}'s own material") is authoritative:
features there are the {offer_noun}'s features, and the `feature_flags` on each competitor map
whether THAT competitor also offers each of those features. The market context tells you the
category, buyer, and target geographies the {offer_noun} competes in — scope the competitor set
to that market.

Rules:

- competitors: Identify the {offer_noun}'s IDEAL competitor set — between 3 and 5 real
  competitors (aim for 5, never fewer than 3). Each must be grounded in the research or
  conversation:
  * name: the real product/company name, as it appears in the sources.
  * description: what they do and how they position, from the sources.
  * website: their official website URL ONLY if it appears in the research/conversation;
    otherwise null — never invent a URL.
  * offering: key features/services they offer.
  * positioning: how they position themselves in the market.
  * comparison: how the {offer_noun} compares to this competitor — where it wins, where it loses.
  * feature_flags: for each of the {offer_noun}'s features, whether this competitor also offers it.
  Do NOT pad the list with generic names — every competitor must be real and defensible
  from the sources. If fewer than 3 defensible competitors are found in the research,
  return only what is defensible rather than inventing names.

- strengths: where the {offer_noun} meets or beats the industry/competitive standard.
- weaknesses: where the {offer_noun} falls short of its competitors / the industry standard.
- opportunities: gaps in the competitive landscape the {offer_noun} could exploit.
- differentiators: things that genuinely set the {offer_noun} apart from the competitors named.

Only state what the interview and sources actually support. If an area is genuinely thin or
unsupported, return empty rather than inventing claims.

OUTPUT
Return only the structured fields — no commentary.
"""


def extract_competitors(state: InterviewState) -> dict:
    """Extract the structured competitor set + product SWOD from the transcript
    and the gathered competitive docs, scoped to the defined market."""

    context = join_context(state.get("context"))
    interview = state.get("interview") or get_buffer_string(state.get("messages") or [])
    offer = as_offer_snapshot(state.get("offer_snapshot"))
    offer_noun = _offer_type_for(state)

    print("Extracting competition data ...")
    competition_data = invoke_structured_with_fallback(
        messages=[
            SystemMessage(content=competition_extraction_instructions.format(
                offer_noun=offer_noun,
            )),
            HumanMessage(
                content=(
                    f"{offer_noun.upper()} OWN MATERIAL:\n{format_offer_material(offer, state.get('scraped_content'), offer_noun) or 'None provided.'}\n\n"
                    f"MARKET CONTEXT (scope the competitor set to this market):\n{_market_context_block(state)}\n\n"
                    f"INTERVIEW TRANSCRIPT:\n{interview}\n\n"
                    f"SOURCES ({offer_noun} material + current competitive docs):\n{context}"
                )
            ),
        ],
        schema=CompetitionExtraction,
        log_label="extract_competitors",
        thinking=False,
    )

    # Enforce the 3-5 competitor floor/ceiling even if the model over-collects.
    competitors = list(competition_data.competitors or [])
    competitors = competitors[:5]
    if len(competitors) < 3:
        print(f"⚠️ Only {len(competitors)} competitor(s) extracted — keeping defensible set, not inventing more.")
    competition_data = competition_data.model_copy(update={"competitors": competitors})

    print(f"✅ Competition data extracted: {competition_data.model_dump_json(exclude_none=True)[:1200]}")
    return {"competition_data": competition_data}


def verify_competitors(state: InterviewState) -> dict:
    """URL check: attempt a light scrape of each competitor's stated website; drop
    a competitor whose URL fails to resolve. Competitors without a URL are kept —
    they were name/description-grounded in the sources."""

    competition_data = state.get("competition_data")
    if not competition_data:
        return {}

    kept = []
    for comp in competition_data.competitors:
        if comp.website:
            try:
                scrape_url(comp.website, Config())
                kept.append(comp)
            except Exception as e:
                print(f"❌ Dropping competitor '{comp.name}' — website failed to resolve: {e}")
        else:
            kept.append(comp)

    verified = competition_data.model_copy(update={"competitors": kept})
    print(f"✅ Verified competitors: {len(kept)} (kept {len(competition_data.competitors) - len(kept)} with dead URLs)")
    return {"competition_data": verified}


competition_findings_instructions = """You are an expert competitive analyst.

Your task is to produce detailed RESEARCH NOTES that lay out the {offer_noun}'s competitive
landscape and how it stacks up, from what the competition specialist actually learned in the
interview, the {offer_noun}'s own material, the market context, and CURRENT competitive sources.

These notes are the raw material for one section of a finished report, written later by
someone who will also see the domain and market analyses. So:

- Write NOTES, not report prose. No report title, no "## Title" / "### Summary" scaffolding.
- Be specific and evidence-dense. Another writer cannot recover what you leave out, but they
  can trim what you give them.
- Keep every concrete claim: named competitors, their pricing, their positioning, feature
  gaps, funding and traction figures, dates. These are what get cited.
- Name only real competitors you actually found in the sources. Never infer or invent one.
- Note where the evidence is thin, estimated or may be dated, and say so.

The context contains the {offer_noun}'s OWN MATERIAL (the document labelled "{offer_noun}'s own
material" — authoritative facts about the {offer_noun}: what it is, who it is for, its
features) followed by documents about the COMPETITIVE LANDSCAPE the {offer_noun} operates in,
as of today (real competitors, their offerings, positioning).

1. Analyze the content of the source documents:
- The name of each source document is at the start of the document, with the <Document tag.
- Separate what is fact about the {offer_noun} itself from what describes its competitors.

2. Organise the notes with markdown sub-headers of your choosing (###). Cover:
- The competitive landscape the {offer_noun} operates in (who the principal players are, scoped
  to the market context already gathered)
- A comparison of the {offer_noun} to its real competitors: where it beats them, where it
  falls short, and what is genuinely unique about it
- The {offer_noun}'s strengths, weaknesses, opportunities and differentiators in relation to
  the named competitors
- What the competition specialist learned in the interview that the sources alone do not say
- Open questions, contested claims and weak points

Keep the {offer_noun} as the subject and the competitive landscape as the framing. Do not
mention the names of interviewers or experts. Ground everything in CURRENT competitive data;
flag anything that is an estimate or may be dated.

The focus area of the {offer_noun} competition specialist is:
{focus}

3. Also return `competitive_positioning_understanding` as a brief standalone synthesis of how
  the {offer_noun} is positioned vs. its real competitors;
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
    """Node to write the competition specialist's research notes.

    Produces notes rather than a report section: the report prose is composed
    once at the end, by a single writer that can see the domain and market
    specialists' notes as well, so the three sections can agree with each other.
    """

    context = join_context(state.get("context"), label="competition_findings")
    interview = state.get("interview") or ""
    specialist = state["specialist"]
    offer = as_offer_snapshot(state.get("offer_snapshot"))
    offer_noun = _offer_type_for(state)
    material = format_offer_material(offer, state.get("scraped_content"), offer_noun)

    system_message = competition_findings_instructions.format(
        offer_noun=offer_noun,
        focus=specialist.focus,
        word_count=state.get("section_word_count", 500),
    )
    print("Writing competition findings ...")
    notes = invoke_structured_with_fallback(
        messages=[
            SystemMessage(content=system_message),
            HumanMessage(content=(
                "Write the notes from what the competition specialist actually learned in the "
                f"interview, the {offer_noun}'s own material, the market context, and the current "
                "competitive sources.\n\n"
                f"SPECIALIST'S LENS: {specialist.distinct_lens or specialist.focus}\n\n"
                f"INTERVIEW TRANSCRIPT:\n{interview or 'None provided.'}\n\n"
                f"{offer_noun.upper()} MATERIAL:\n{material or 'None provided.'}\n\n"
                f"MARKET CONTEXT:\n{_market_context_block(state)}\n\n"
                f"COMPETITIVE SOURCES:\n{context}"
            )),
        ],
        schema=CompetitionFindings,
        log_label="write_findings:competition",
    )
    print("✅ Competition findings written" if notes else "❌ Competition findings not written!")
    return {
        "competition_findings": notes.findings,
        "competitive_positioning_understanding": notes.competitive_positioning_understanding,
        "competition_complete": True,
    }


def build_competition_graph(checkpointer: bool = True):
    """Build the understand-competition interview loop: competition specialist
    interviews a competitive-intel expert grounded on CURRENT web research + the
    {offer_noun}'s own material + market context, then extracts the competitor set
    (3-5, URL-verified), merges the product SWOD, and writes its research notes.

    Compiled with a checkpointer by default so an interactive driver can resume
    interrupts; pass checkpointer=False when embedding as a subgraph node."""

    builder = StateGraph(InterviewState)

    # -- Nodes --
    builder.add_node("seed_product_context", seed_product_context)
    builder.add_node("ask_question", generate_question)
    builder.add_node("search_web", search_web)
    builder.add_node("answer_question", generate_aswer)
    builder.add_node("save_interview", save_interview)
    builder.add_node("extract_competitors", extract_competitors)
    builder.add_node("verify_competitors", verify_competitors)
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
    builder.add_edge("save_interview", "extract_competitors")
    builder.add_edge("extract_competitors", "verify_competitors")
    builder.add_edge("verify_competitors", "write_findings")
    builder.add_edge("write_findings", END)

    # -- Compile --
    if checkpointer:
        memory_saver = MemorySaver()
        return builder.compile(checkpointer=memory_saver)
    return builder.compile()