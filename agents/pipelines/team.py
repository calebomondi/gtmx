"""The workspace's specialist team as the agents speak through it.

Discovery creates four specialists (product or service, market, competition,
GTM). Outreach, replies and chat all answer in one specialist's voice and ask
the others for what only their research covers. This module is the one
place that turns a team member into a persona and runs a consultation.
"""

from langchain_core.messages import HumanMessage, SystemMessage

from agents.concurrency import ContextThreadPoolExecutor
from agents.llm.main import cheap_providers, invoke_structured_with_fallback
from agents.schemas.outreach import Consultation

MAX_CONSULTS = 2

# Used when a workspace predates its team or the team lacks a domain.
_GENERIC = {
    "gtm": {"name": "the GTM specialist", "role": "Go-to-market lead",
            "description": "Owns positioning, channels and outbound for this offer."},
    "product": {"name": "the product specialist", "role": "Product lead",
                "description": "Knows what the offer does, how, and for whom."},
    "market": {"name": "the market specialist", "role": "Market analyst",
               "description": "Knows the buyers, demand and pricing norms."},
    "competition": {"name": "the competition specialist", "role": "Competitive analyst",
                    "description": "Knows the rivals and where they are exposed."},
}

_CONSULT_PROMPT = """You are {persona}, the team's {domain} specialist. {asker} asks you one
question. Answer in 2-4 sentences, from your research below only; say plainly
if it does not cover the question.

YOUR RESEARCH
{research}

QUESTION
{question}"""


def member(team: dict[str, dict], domain: str) -> dict:
    """The team member for a domain ("product" also finds a "service" expert)."""
    found = team.get(domain) or (team.get("service") if domain == "product" else None)
    return found or _GENERIC["product" if domain == "service" else domain]


def persona(person: dict) -> str:
    return f"{person.get('name')}, {person.get('role')}. {person.get('description') or ''}".strip()


def consult(team: dict[str, dict], research: dict[str, str], ask: Consultation,
            asker: str, label_prefix: str) -> str:
    """One specialist's answer, from their own research."""
    answer = invoke_structured_with_fallback(
        [SystemMessage(content=_CONSULT_PROMPT.format(
            persona=persona(member(team, ask.domain)), domain=ask.domain, asker=asker,
            research=research.get(ask.domain) or "(no research on file)", question=ask.question,
        )), HumanMessage(content="Answer now.")],
        providers=cheap_providers(), log_label=f"{label_prefix}:{ask.domain}",
    )
    return f"{member(team, ask.domain).get('name')} ({ask.domain}) on '{ask.question}': {answer}"


def consult_all(team: dict[str, dict], research: dict[str, str], asks: list[Consultation],
                lead: str, asker: str, label_prefix: str) -> str:
    """Answers to up to MAX_CONSULTS questions for colleagues of `lead` (a
    specialist never consults itself), in parallel, as notes."""
    asks = [a for a in asks if a.domain != lead][:MAX_CONSULTS]
    if not asks:
        return "(none)"
    with ContextThreadPoolExecutor(max_workers=len(asks)) as pool:
        return "\n".join(pool.map(lambda a: consult(team, research, a, asker, label_prefix), asks))
