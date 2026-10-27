"""Suggested replies the Lace forgot to offer. A reply that ends on an offer
("Want me to dig into Velinex, or look for target accounts?") should come
with chips the founder taps instead of typing. The model offers them with
suggest_replies, but not every time; when it doesn't, the cheap model reads
the closing question and writes them."""

from langchain_core.messages import HumanMessage, SystemMessage

from agents.lace.ask_tools import CHOICE_CHARS, MAX_SUGGESTIONS, MIN_SUGGESTIONS
from agents.llm.main import cheap_providers, invoke_structured_with_fallback
from agents.schemas.lace_ui import FollowUps

# The end of the reply the model reads: the closing question and its lead-in.
TAIL_CHARS = 600

_SYSTEM = (
    "An assistant's reply to a startup founder ends with a question. Decide which kind it is.\n"
    "1. An offer of things the assistant could do next (\"Want me to dig into X, or look for Y?\"). Write "
    "2 or 3 short replies the founder would tap to accept one: a few words each, as the founder would say "
    f"them (\"Dig into X\", \"Look for Y\"), under {CHOICE_CHARS} characters, and only steps the reply offered.\n"
    "2. Anything else: a request for facts only the founder knows (their pricing, a name, an email, their "
    "plans), an open question, or a check (\"Does that look right?\"). Return no options. Never invent an "
    "answer on the founder's behalf.\n"
    "When unsure, return no options."
)


def ends_on_question(reply: str) -> bool:
    """Whether the reply's last paragraph asks something."""
    paragraphs = [p for p in reply.strip().split("\n\n") if p.strip()]
    return bool(paragraphs) and "?" in paragraphs[-1]


def follow_ups(reply: str, ask=invoke_structured_with_fallback) -> list[str]:
    """2 or 3 replies to the question the reply ends on; [] when it offers
    nothing to tap. Raises LlmProvidersExhaustedError when no model answers."""
    tail = reply.strip()[-TAIL_CHARS:]
    found: FollowUps = ask([SystemMessage(content=_SYSTEM), HumanMessage(content=tail)], FollowUps,
                           providers=cheap_providers(), log_label="lace:follow_ups", max_retries=1)
    options = [o.strip() for o in found.options if o.strip() and len(o.strip()) <= CHOICE_CHARS]
    return options[:MAX_SUGGESTIONS] if len(options) >= MIN_SUGGESTIONS else []
