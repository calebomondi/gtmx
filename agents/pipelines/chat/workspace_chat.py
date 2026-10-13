"""Workspace chat: the user talks with their specialist team.

Each question goes to the specialist whose expertise it is about (product or
service, market, competition, GTM). That specialist answers in the first
person, from their own research, after consulting up to two colleagues when
the question crosses into their areas and, when the research cannot contain
the answer, a quick web search.

Pure: the backend supplies the team and each specialist's research as text
and stores the answer with the specialist who gave it.
"""

import re
from dataclasses import dataclass, field

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from agents.concurrency import ContextThreadPoolExecutor
from agents.llm.main import LlmProvidersExhaustedError, cheap_providers, invoke_structured_with_fallback
from agents.pipelines import team
from agents.pipelines.web_utils import call_with_timeout
from agents.schemas.chat import ChatDomain, ChatRoute, ChatSuggestions
from config import get_settings
from data_sources.scraping.exa import search_and_scrape
from utils.log import logger

MAX_QUERIES = 3
_SNIPPET_CHARS = 1500
_SEARCH_TIMEOUT_S = 20
_OTHERS_CHARS = 1_200
_HISTORY_CHARS = 1_500

_ROUTE_PROMPT = """You route a user's question to ONE specialist on {offer_name}'s team, who
will answer it: product (what the offer is, does, how it works), market
(buyers, demand, sizing, pricing norms), competition (rivals, positioning,
threats, where they are exposed), gtm (ICP, segments, channels, target
accounts, messaging, outreach, launch). When a good answer also needs a
colleague's expertise, add up to 2 consultations with a precise question each.
Search the web only for facts the research cannot contain.

THE TEAM
{team}

RECENT CONVERSATION
{history}

QUESTION
{question}"""

_ANSWER_PROMPT = """You are {persona} -- {offer_name}'s {domain} specialist, part of a four-person
team the user works with. You are talking with the user directly. Answer in
the first person, as yourself: your judgment, your recommendations. You are
not a chatbot and you never describe yourself as an AI.

Be the expert they would pay for:
- Answer the actual question first, then the reasoning behind it.
- Be specific to {offer_name} and its market: names, numbers, segments,
  channels, examples from the research. No generic advice.
- When a colleague's input shaped your answer, say so naturally ("I checked
  with <name> on pricing: ...").
- Ground claims in the research or the web results. Cite inline as
  [research] or [web: <url>]. If something isn't known, say what you'd need to
  find out -- never invent companies, customers or numbers.
- Finish with a concrete next step or recommendation when one fits. You
  can't act outside this conversation: never promise to draft, send, prepare
  or schedule anything later ("I'll draft three variations"). Write what is
  needed right here, or tell the user where GTMX does it: target accounts and
  outreach drafts in the workspace's Reach Out tab (where {gtm_name} drafts
  each message), competitors in the Competitors tab.
- Use short markdown (headings, lists, bold) when it helps; keep it tight.

YOUR RESEARCH ({domain})
{research}

WHAT YOUR COLLEAGUES KNOW (summaries)
{others}

COLLEAGUES' ANSWERS TO YOUR QUESTIONS
{notes}

WEB RESULTS
{web}"""


_GREETING_PROMPT = """You are {persona} -- {offer_name}'s {domain} specialist. The user just greeted
the team or asked who you are. Reply like a colleague would, in 2 to 4 short
sentences, in the first person: say hello, who you are, and who else is on the
team and what each of you can help with ({team}). Do not share any research
yet and do not answer questions they haven't asked. Never describe yourself as
an AI."""

_SUGGEST_PROMPT = """Suggest the 3 questions the user is most likely to want to ask {offer_name}'s
specialist team next, given the conversation below. Write them as the user
would type them: short, specific to {offer_name} and what was just said, and
covering different ground (for example the market, competitors, who to target,
outreach). Never repeat a question they already asked.

LAST QUESTION
{question}

ANSWER THEY GOT
{answer}"""

# Messages that greet or ask who the team is, not about the offer. They go to
# the offer's own specialist for a short hello, never a research dump.
_SMALL_TALK = re.compile(
    r"^\s*(?:(?:hi|hey|hello|hiya|hola|yo|howdy|greetings|good (?:morning|afternoon|evening))(?: there| team| guys| all)?"
    r"|who (?:are|r) (?:you|u)(?: guys| all)?|what(?:'s| is) your name|what can you (?:do|help with)"
    r"|what do you do|thanks?(?: you)?|thank you|ok(?:ay)?|cool|great)[\s!.?,]*$",
    re.I,
)
SUGGESTION_COUNT = 3


def is_small_talk(question: str) -> bool:
    return bool(_SMALL_TALK.match(question or ""))


@dataclass
class ChatContext:
    offer_name: str
    offer: str
    team: dict[str, dict] = field(default_factory=dict)
    research: dict[str, str] = field(default_factory=dict)


@dataclass
class ChatAnswer:
    domain: ChatDomain
    content: str
    suggestions: list[str] = field(default_factory=list)


def _greet(question: str, history: list[tuple[str, str]], context: ChatContext) -> ChatAnswer:
    lead = "product"
    roster = "; ".join(
        f"{team.member(context.team, d).get('name')} ({d})" for d in ("market", "competition", "gtm")
    )
    turns = [HumanMessage(content=c) if role == "user" else AIMessage(content=c) for role, c in history]
    content = invoke_structured_with_fallback(
        [SystemMessage(content=_GREETING_PROMPT.format(
            persona=team.persona(team.member(context.team, lead)), offer_name=context.offer_name or "the offer",
            domain=lead, team=roster,
        )), *turns, HumanMessage(content=question)],
        log_label="chat_answer:greeting", providers=cheap_providers(), thinking=False,
    )
    return ChatAnswer(domain=lead, content=content)


def suggest(question: str, answer_text: str, context: ChatContext) -> list[str]:
    """What the user might ask next. Optional: on any provider failure, none."""
    try:
        result = invoke_structured_with_fallback(
            [SystemMessage(content=_SUGGEST_PROMPT.format(
                offer_name=context.offer_name or "the offer", question=question, answer=answer_text[:4000],
            )), HumanMessage(content="Suggest them now.")],
            ChatSuggestions, log_label="chat_suggestions", providers=cheap_providers(), thinking=False,
        )
    except LlmProvidersExhaustedError:
        logger.warning("No chat suggestions: every model failed")
        return []
    asked = question.strip().lower()
    return [s.strip() for s in result.suggestions if s.strip() and s.strip().lower() != asked][:SUGGESTION_COUNT]


def reply(question: str, history: list[tuple[str, str]], context: ChatContext) -> ChatAnswer:
    """The answer to the user's message, with suggested follow-ups. A greeting
    gets a short hello from the offer's own specialist instead of research."""
    result = _greet(question, history, context) if is_small_talk(question) else answer(question, history, context)
    result.suggestions = suggest(question, result.content, context)
    return result


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


def _team_text(context: ChatContext) -> str:
    return "\n".join(f"- {domain}: {team.persona(team.member(context.team, domain))}"
                      for domain in ("product", "market", "competition", "gtm"))


def _history_text(history: list[tuple[str, str]]) -> str:
    return "\n".join(f"{role}: {content[:300]}" for role, content in history[-6:])[-_HISTORY_CHARS:] or "(none)"


def route(question: str, history: list[tuple[str, str]], context: ChatContext) -> ChatRoute:
    return invoke_structured_with_fallback(
        [SystemMessage(content=_ROUTE_PROMPT.format(
            offer_name=context.offer_name or "the offer", team=_team_text(context),
            history=_history_text(history), question=question,
        ))],
        ChatRoute, providers=cheap_providers(), log_label="chat_route", thinking=False,
    )


def answer(question: str, history: list[tuple[str, str]], context: ChatContext) -> ChatAnswer:
    """`history` is [(role, content)] oldest first, role in {"user", "assistant"}."""
    plan = route(question, history, context)
    lead = plan.lead
    notes = team.consult_all(context.team, context.research, plan.consult, lead,
                             f"{team.member(context.team, lead).get('name')}, answering the user,", "chat_consult")
    web = _web_results(plan.queries) if plan.needs_web else "(no search was needed)"
    others = "\n\n".join(
        f"{domain}: {(context.research.get(domain) or '')[:_OTHERS_CHARS]}"
        for domain in ("product", "market", "competition", "gtm") if domain != lead
    )
    turns = [HumanMessage(content=c) if role == "user" else AIMessage(content=c) for role, c in history]
    system = SystemMessage(content=_ANSWER_PROMPT.format(
        persona=team.persona(team.member(context.team, lead)), offer_name=context.offer_name or "the offer",
        domain=lead, research=context.research.get(lead) or context.offer, others=others,
        notes=notes, web=web, gtm_name=team.member(context.team, "gtm").get("name"),
    ))
    content = invoke_structured_with_fallback(
        messages=[system, *turns, HumanMessage(content=question)], log_label=f"chat_answer:{lead}",
    )
    problems = voice_problems(content)
    if problems:
        content = invoke_structured_with_fallback(
            messages=[system, *turns, HumanMessage(content=question), AIMessage(content=content),
                      HumanMessage(content="Rewrite your answer: " + " ".join(problems))],
            log_label=f"chat_answer:{lead}:rewrite",
        )
    return ChatAnswer(domain=lead, content=content)


_PROMISE = re.compile(r"\bI(?:'ll|’ll| will| can) (?:draft|prepare|send|schedule|create|put together|build|follow up)\b", re.I)
_FIRST_PERSON = re.compile(r"\bI(?:'m|’m|'d|’d|'ve|’ve)?\b|\b(?i:my|we|we're|we’re|our|us)\b")
# Work the chat never did: it can't send or book anything, and a draft it
# claims to have left somewhere else doesn't exist. A draft written out in
# the answer itself ("I've drafted it below") is fine.
_CLAIMED = re.compile(
    r"\bI(?:'ve|’ve| have)? (?:already )?(?:sent|scheduled|booked|emailed|messaged|launched|posted)\b|"
    r"\bI(?:'ve|’ve| have)? (?:already )?(?:drafted|prepared|created|set up|queued)\b[^.\n]{0,80}?"
    r"\b(?:tab|inbox|folder|calendar|queue)\b",
    re.I,
)


def voice_problems(content: str) -> list[str]:
    """What breaks the specialist's voice: promising work after the
    conversation, claiming work that never happened, or not speaking as
    themselves at all."""
    problems = []
    if match := _PROMISE.search(content):
        problems.append(f'You can\'t act after this conversation ("{match.group(0)}"): write it here, or say where in '
                        "GTMX it gets done.")
    if match := _CLAIMED.search(content):
        problems.append(f'You haven\'t done that ("{match.group(0)}"): describe only what is in this answer, and say '
                        "where in GTMX the user does the rest.")
    if not _FIRST_PERSON.search(content):
        problems.append("Answer in your own voice, in the first person (I / we), as the specialist you are.")
    return problems
