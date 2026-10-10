"""Workspace chat: answer a user's question about their offer, grounded in the
workspace's research, with an optional quick web lookup.

Pure: it receives the workspace context as text (the backend assembles it from
the database) and returns the answer. Two LLM calls at most: a cheap plan
(does this need the web?) and the answer.
"""

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from agents.concurrency import ContextThreadPoolExecutor
from agents.llm.main import cheap_providers, invoke_structured_with_fallback
from agents.pipelines.web_utils import call_with_timeout
from agents.schemas.chat import ChatResearchPlan
from config import get_settings
from data_sources.scraping.exa import search_and_scrape

MAX_QUERIES = 2
_SNIPPET_CHARS = 1500
_SEARCH_TIMEOUT_S = 20

_PLAN_PROMPT = """You decide whether a question about a company's go-to-market can be
answered from the WORKSPACE DATA below, or needs a quick web search.

Search only for facts the workspace data cannot contain: recent news, a company
that is not on the lists, current prices, events. Most questions about the
offer, its market, competitors, ICP or accounts need NO search.

WORKSPACE DATA
{context}

QUESTION
{question}"""

_ANSWER_PROMPT = """You are {offer_name}'s go-to-market specialist team. Answer the user's
question as a sharp, practical GTM strategist would.

Ground every claim in the WORKSPACE DATA (the team's own research on this
offer) or the WEB RESULTS. Cite inline: [workspace] or [web: <url>]. If neither
supports an answer, say what is missing instead of guessing. Never invent
companies, numbers or customers.

Be concise and concrete. Use short markdown (lists, bold) when it helps.

WORKSPACE DATA
{context}

WEB RESULTS
{web}"""


def _search(query: str) -> list[dict]:
    return call_with_timeout(
        lambda: search_and_scrape(query, get_settings(), num_results=3),
        _SEARCH_TIMEOUT_S, default=[], label=f"chat_search[{query}]",
    ) or []


def _web_results(queries: list[str]) -> str:
    queries = [q for q in queries if q.strip()][:MAX_QUERIES]
    if not queries:
        return "(no search was needed)"
    with ContextThreadPoolExecutor(max_workers=len(queries)) as pool:
        batches = list(pool.map(_search, queries))
    blocks = [
        f"<Document href=\"{r['url']}\">\n{r['title']}\n{(r.get('text') or '')[:_SNIPPET_CHARS]}\n</Document>"
        for batch in batches for r in batch
    ]
    return "\n\n".join(blocks) or "(the search returned nothing usable)"


def answer(question: str, context: str, history: list[tuple[str, str]], offer_name: str) -> str:
    """`history` is [(role, content)] oldest first, role in {"user", "assistant"}."""
    plan = invoke_structured_with_fallback(
        messages=[SystemMessage(content=_PLAN_PROMPT.format(context=context, question=question))],
        schema=ChatResearchPlan,
        log_label="chat_plan",
        providers=cheap_providers(),
        thinking=False,
    )
    web = _web_results(plan.queries) if plan.needs_web else "(no search was needed)"
    turns = [HumanMessage(content=c) if role == "user" else AIMessage(content=c) for role, c in history]
    return invoke_structured_with_fallback(
        messages=[
            SystemMessage(content=_ANSWER_PROMPT.format(offer_name=offer_name or "this offer", context=context, web=web)),
            *turns,
            HumanMessage(content=question),
        ],
        log_label="chat_answer",
        thinking=False,
    )
