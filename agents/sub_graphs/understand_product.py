from typing import Literal
from langgraph.graph import START, END, StateGraph
from langgraph.checkpoint.memory import MemorySaver
from langchain_core.messages import HumanMessage, SystemMessage, get_buffer_string, AIMessage

from agents.llm.main import invoke_structured_with_fallback
from agents.states import InterviewState, ProductFindings, SearchQuery
from agents.context_budget import DEFAULT_CONTEXT_BUDGET, budget_context, distill_documents
from agents.helpers import as_offer_snapshot, format_offer_material
from config import get_settings
from data_sources.scraping.exa import search_and_scrape
from utils.log import logger


# --- Further Product understanding ---


def _offer_type_for(state: InterviewState) -> str:
    """Resolve the captured offer kind (product or service) so the interview
    prompts adapt their wording. Prefers the session-level offer_type; falls
    back to the specialist's own domain when running standalone."""
    offer_type = state.get("offer_type")
    if offer_type in ("product", "service"):
        return offer_type
    specialist = state.get("specialist")
    domain = getattr(specialist, "domain", None) if specialist else None
    if domain in ("product", "service"):
        return domain
    return "product"


question_instructions = """
You are {specialist_name}, a {specialist_role}.

Your background: {specialist_background}
Your focus: {specialist_focus}
Your lens: {specialist_lens}
Your region: {specialist_region}
Your language/idiom: {specialist_language}
Your operating context: {specialist_operating_context}

You are interviewing an expert who knows this {offer_noun} domain/category well to deeply understand it.

OFFER
Name: {offer_name}
Description: {offer_description}

KNOWN FACTS
{snapshot_summary}

GOAL
Your goal is to understand this {offer_noun} as a whole in relation to how it fits into its domain. Treat the
KNOWN FACTS as background: don't re-litigate areas already covered, and steer
into areas that are still thin, missing, or vague so the picture becomes
complete. Each question should flow naturally from interviewing about the
{offer_noun} — not check a list of fields.

RULES
1. Introduce yourself briefly and ask your question.
2. Stay in character as {specialist_name} throughout.
3. Ask one focused question at a time.
4. Build on previous answers — don't repeat questions.
5. Drive your questioning through your distinctive lens, and keep it anchored to
   the markets in your region — ask in plain language, grounded in how the
   category actually works where this {offer_noun} operates.
6. When the {offer_noun} domain picture is sufficiently complete or you are otherwise
   satisfied with your understanding, end the interview with:
   "Thank you so much for your help!"

OUTPUT
Return only the message content — no structured fields.
"""

def generate_question(state: InterviewState) -> dict:
    """Have the product specialist ask the next gap-filling question."""

    specialist = state["specialist"]
    messages = state.get("messages", [])
    offer = as_offer_snapshot(state.get("offer_snapshot"))
    offer_noun = _offer_type_for(state)

    system_message = question_instructions.format(
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
    print(f"Generating question ...")
    question = invoke_structured_with_fallback(
        messages=[SystemMessage(content=system_message)] + messages,
        log_label="generate_question",
        thinking=False,
    )
    print(f"✅ Question generated.\n{question}")

    return {"messages": [AIMessage(content=question)]}


def join_context(context, budget_tokens: int = DEFAULT_CONTEXT_BUDGET, label: str = "context") -> str:
    """Render accumulated context chunks as one block that fits the model's window.

    Context accumulates via operator.add and is re-sent in full on every call, so
    an unbounded pile eventually exceeds the provider's context limit and kills
    the run mid-interview. The budgeting itself lives in `context_budget`; this
    stays the shared entry point because the other subgraphs import it from here.
    """
    return budget_context(context, budget_tokens=budget_tokens, label=label)


def seed_product_context(state: InterviewState) -> dict:
    """Seed the interview context with the product's own material (scraped
    content or a snapshot-derived brief) so the expert and section writer can
    ground the conversation on the product itself, not only domain search docs."""
    offer = as_offer_snapshot(state.get("offer_snapshot"))
    material = format_offer_material(offer, state.get("scraped_content"), _offer_type_for(state))
    return {"context": [material]}


search_instructions = """
You will be given a conversation between a {offer_noun} specialist and a {offer_noun} expert,
plus the {offer_noun}'s own material.

Your goal is to generate a well-structured web-search query about the TECHNOLOGY and
DOMAIN SPACE the {offer_noun} operates in — NOT about the {offer_noun} or brand itself.

First, analyze the full conversation.

Pay particular attention to the final question posed by the {offer_noun} specialist.

RULES
1. Identify the technology, approach, and domain category the {offer_noun} uses or sits in
   (drawn from the {offer_noun}'s material and the conversation).
2. Build the query around that TECHNOLOGY / DOMAIN only — standards {offer_nouns} in this
   category are held to, how they are expected to perform, architecture conventions,
   adjacent approaches. This lets the expert speak to the domain WITHOUT knowing the {offer_noun}.
3. When target markets are given, scope the query toward how the category actually
   works and is held to standards in those markets.
4. NEVER include the {offer_noun}'s name or brand in the query.
5. Also provide a `broader_query`: a simpler, less specific version of the same
   technology/domain query, to use as a fallback if the primary query gets no results.
"""

def search_web(state: InterviewState) -> dict:
    """Turn the specialist's latest question into a technology/domain-focused
    web-search query (excluding the product name), gather supporting documents
    via Exa, and append them as formatted context for the expert's answer."""

    specialist = state["specialist"]
    offer = as_offer_snapshot(state.get("offer_snapshot"))
    offer_noun = _offer_type_for(state)
    material = format_offer_material(offer, state.get("scraped_content"), offer_noun)
    markets = ", ".join(offer.target_geo or []) or "not specified"

    print(f"Creating search query...")
    # A failed search query must not kill the interview. The specialist can still
    # work from the offer's own material, so degrade to "no web docs" and keep
    # going rather than propagating a provider error out of the whole run.
    try:
        search_query = invoke_structured_with_fallback(
            messages=[
                SystemMessage(content=search_instructions.format(
                    offer_noun=offer_noun,
                    offer_nouns=f"{offer_noun}s",
                )),
                HumanMessage(content=(
                    f"SPECIALIST'S LENS: {specialist.distinct_lens or specialist.focus}\n"
                    f"TARGET MARKETS: {markets}\n\n"
                    f"{offer_noun.upper()} MATERIAL:\n{material or 'None provided.'}\n\n"
                    f"CONVERSATION:\n{get_buffer_string(state['messages'])}"
                )),
            ],
            schema=SearchQuery,
            log_label="search_web:search_query",
            thinking=False,
        )
    except Exception as exc:
        logger.warning(
            "search_web: could not build a search query (%s); "
            "continuing without web search for this turn",
            exc,
        )
        print(f"⚠️  Search query failed — continuing without web search.")
        return {"context": []}
    print(f"✅ Search query generated.\n{search_query.search_query}")

    print(f"Searching web ...")
    search_docs = search_and_scrape(search_query.search_query, get_settings(), num_results=3)
    if not search_docs and search_query.broader_query:
        print(f"Primary search empty — retrying with broader query:\n{search_query.broader_query}")
        search_docs = search_and_scrape(search_query.broader_query, get_settings(), num_results=3)
    print(f"{"✅ Search complete" if search_docs else "❌ Search failed"}")

    # Condense each page once, against the query that surfaced it. The note is
    # cached by URL, so later turns and later subgraphs reuse it rather than
    # re-sending (and re-paying for) the full article text on every call.
    formatted_search_docs = distill_documents(
        search_docs,
        focus=(
            f"the technology and domain space {offer_noun}s like this operate in, "
            f"as surfaced by this search: {search_query.search_query}"
        ),
        log_label="search_web:distill_product_doc",
    )

    return {"context": [formatted_search_docs]}

answer_instructions = """
You are a {offer_noun} domain expert being interviewed by a {offer_noun} specialist.

Here is the specialist's area of focus: {goals}. 
        
Your goal is to answer a question posed by the interviewer.

To answer the question, use this context:
        
{context}

The context begins with the {offer_noun}'s OWN MATERIAL (the document labelled
"{offer_noun}'s own material") — treat that as authoritative, provided facts about the {offer_noun}
being interviewed. The remaining documents describe the {offer_noun}'s domain/category.

When answering questions, follow these guidelines:
        
1. Use only the information provided in the context. 
        
2. Do not introduce external information or make assumptions beyond what is explicitly stated in the context.

3. The context contains sources at the topic of each individual document.

4. List your sources in order at the bottom of your answer. [1] Source 1, [2] Source 2, etc
        
5. If the source is: <Document source="assistant/docs/llama3_1.pdf" page="7"/>' then just list: 
        
[1] assistant/docs/llama3_1.pdf, page 7 
        
And skip the addition of the brackets as well as the Document source preamble in your citation.
"""

def generate_aswer(state: InterviewState) -> dict:
    """Have the product domain expert answer using only the context (product
    material + search context)."""

    specialist = state["specialist"]
    messages = state.get("messages", [])
    context = join_context(state.get("context"))

    system_message = answer_instructions.format(
        offer_noun=_offer_type_for(state),
        goals=specialist.persona,
        context=context,
    )

    print("Generating answer ...")
    answer = invoke_structured_with_fallback(
        messages=[SystemMessage(content=system_message)] + messages,
        log_label="generate_answer",
        thinking=True,
    )
    print(f"{"✅ Generated Anser" if answer else "❌ Failed to generate anser!"}")

    # Name the message as coming from the expert
    return {"messages": [AIMessage(content=answer, name="expert")]}

def save_interview(state: InterviewState):
    """ Save interviews """

    # Get messages
    messages = state["messages"]
    print(f"Saving interview ...")
    # Convert interview to a string
    interview = get_buffer_string(messages)
    print("✅ Saved interview")
    
    # Save to interviews key
    return {"interview": interview}


def route_messages(state: InterviewState, name: str = "expert") -> dict:
    """"""

    # Get messages
    messages = state["messages"]
    max_num_turns = state.get('max_num_turns',2)

    # Check the number of expert answers 
    num_responses = len(
        [m for m in messages if isinstance(m, AIMessage) and m.name == name]
    )

    # End if expert has answered more than the max turns
    if num_responses >= max_num_turns:
        return 'save_interview'

    # This router is run after each question - answer pair 
    # Get the last question asked to check if it signals the end of discussion
    last_question = messages[-2]
    
    if "Thank you so much for your help" in last_question.content:
        return 'save_interview'
    return "ask_question"


# Signals that the expert is wrapping up. Checked right after the question is
# generated so a closing turn skips the pointless search + answer round-trip.
CLOSING_SIGNALS = ("thank you so much for your help", "thank you for your help")


def route_after_question(state: InterviewState) -> str:
    """Decide, immediately after a question is generated, whether it is worth
    researching/answering at all. A closing 'thank you' question needs no search
    or answer, so jump straight to save_interview — otherwise the interview would
    pay for a search-query LLM call, an Exa search, and an answer LLM call before
    the post-answer router discards the turn. Route on a case-insensitive match of
    the same signals route_messages uses, so this only changes timing, not which
    turns are dropped."""

    messages = state.get("messages") or []
    if not messages:
        return "search_web"
    last = messages[-1]
    content = getattr(last, "content", "") or ""
    if not isinstance(content, str):
        content = str(content)
    lowered = content.lower()
    if any(sig in lowered for sig in CLOSING_SIGNALS):
        return "save_interview"
    return "search_web"


# Research notes for the product-domain specialist. Not the report section — the
# report prose is written once at the end by a single writer that can see every
# specialist's notes, so this output has to be dense with evidence rather than
# polished.
domain_findings_instructions = """You are an expert technical analyst.

Your task is to produce detailed RESEARCH NOTES that GROUND the {offer_noun} in its
{offer_noun}/category domain space, from an interview transcript and a set of source documents.

These notes are the raw material for one section of a finished report, written later by
someone who will also see the market and competitive analyses. So:

- Write NOTES, not report prose. No report title, no "## Title" / "### Summary" scaffolding.
- Be specific and evidence-dense. Another writer cannot recover what you leave out, but they
  can trim what you give them.
- Keep every concrete claim: named technologies, architectures, standards, limits, latencies,
  numbers, dates, versions, named organisations and products. These are what get cited.
- Note where the evidence is thin or contested, and say so. Do not smooth over a gap.

The context contains the {offer_noun}'s OWN MATERIAL (the document labelled "{offer_noun}'s own
material" — authoritative facts about the {offer_noun}: what it is, how it works, {offer_features},
intent, and the problem it solves) followed by documents about the DOMAIN/CATEGORY the
{offer_noun} sits in (standards, how {offer_nouns} in this category are expected to perform,
architecture conventions, adjacent approaches).

1. Analyze the content of the source documents:
- The name of each source document is at the start of the document, with the <Document tag.
- Separate what is fact about the {offer_noun} itself from what describes the domain/category.

2. Organise the notes with markdown sub-headers of your choosing (###). Cover:
- The domain/category background a reader needs in order to judge the {offer_noun}
- What the {offer_noun} is and how it works mechanically, from its own material
- How the {offer_noun} fits its domain space: where it aligns with, extends, deviates from, or
  outpaces how {offer_nouns} in this category are expected to work and the standards they are held
  to. What is novel, interesting or surprising about it relative to the domain
- What the specialist learned in the interview that the sources alone do not say
- Open questions and weak points

Keep the {offer_noun} as the subject and the domain as the framing. Do not mention the names of
interviewers or experts.

3. Also return `product_domain_understanding` as a brief standalone synthesis of the {offer_noun}'s
fit within its domain; target 40 words and never exceed 50 words.

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
    """Node to write the product specialist's research notes.

    Produces notes rather than a report section: the report prose is composed
    once at the end, by a single writer that can see the market and competition
    specialists' notes as well, so the three sections can agree with each other.
    """

    context = join_context(state.get("context"), label="product_findings")
    interview = state.get("interview") or ""
    specialist = state["specialist"]
    offer = as_offer_snapshot(state.get("offer_snapshot"))
    offer_noun = _offer_type_for(state)
    material = format_offer_material(offer, state.get("scraped_content"), offer_noun)

    system_message = domain_findings_instructions.format(
        offer_noun=offer_noun,
        offer_nouns=f"{offer_noun}s",
        offer_features="its features/service elements" if offer_noun == "service" else "its features",
        focus=specialist.focus,
        word_count=state.get("section_word_count", 400),
    )
    print("Writing domain findings ...")
    notes = invoke_structured_with_fallback(
        messages=[
            SystemMessage(content=system_message),
            HumanMessage(content=(
                "Write the notes from what the specialist actually learned in the interview, "
                f"the {offer_noun}'s own material, and the domain sources.\n\n"
                f"SPECIALIST'S LENS: {specialist.distinct_lens or specialist.focus}\n\n"
                f"INTERVIEW TRANSCRIPT:\n{interview or 'None provided.'}\n\n"
                f"{offer_noun.upper()} MATERIAL:\n{material or 'None provided.'}\n\n"
                f"DOMAIN SOURCES:\n{context}"
            )),
        ],
        schema=ProductFindings,
        log_label="write_findings:product",
    )
    print("✅ Domain findings written" if notes else "❌ Domain findings not written!")
    return {
        "product_findings": notes.findings,
        "product_domain_understanding": notes.product_domain_understanding,
        "product_complete": True,
    }


def build_product_graph(checkpointer: bool = True): 
    """Build the understand-product interview loop. Compiled with a checkpointer by
    default so an interactive driver can resume interrupts; pass checkpointer=False
    when embedding this as a subgraph node in the main agent (nested subgraphs
    cannot own a checkpointer)."""

    builder = StateGraph(InterviewState)

    # -- Nodes --
    builder.add_node("seed_product_context", seed_product_context)
    builder.add_node("ask_question", generate_question)
    builder.add_node("search_web", search_web)
    builder.add_node("answer_question", generate_aswer)
    builder.add_node("save_interview", save_interview)
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
    builder.add_edge("save_interview", "write_findings")
    builder.add_edge("write_findings", END)

    # -- Compile --
    if checkpointer:
        memory_saver = MemorySaver()
        return builder.compile(checkpointer=memory_saver)
    return builder.compile()