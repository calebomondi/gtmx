"""The replies a founder can tap under the Lace's answer.

Written after the answer is finished, by the cheap model, rather than by the
Lace itself through a tool: a tool call mid-answer made the answer stream,
vanish and stream again. Here the answer streams once, and the chips arrive
with it.

They are a varied handful, not a menu of what the reply offered: the next
step it points to, a dig into something it named, a challenge to its own
conclusion, and a nudge about what waits for the founder. Specific (names
from the reply and from what's on file), and none when the reply is asking
the founder for something only they know."""

from langchain_core.messages import HumanMessage, SystemMessage

from agents.lace.ask_tools import CHOICE_CHARS
from agents.llm.main import cheap_providers, invoke_structured_with_fallback
from agents.schemas.lace_ui import FollowUps

MIN_SUGGESTIONS, MAX_SUGGESTIONS = 2, 3
# What the model reads of each: the reply's end carries its point and offer.
REPLY_CHARS = 1_800
ASKED_CHARS = 400
SITUATION_CHARS = 900

_SYSTEM = f"""You write the 2 or 3 replies a startup founder is most likely to tap next, shown as
chips under their assistant's answer. The founder taps one and it is sent as their message, so
write each as the founder would say it to their assistant, in a few words.

Make them a varied handful, each a different kind, chosen from:
- next: the obvious next step the answer points to, as an instruction ("Draft emails to both fintechs").
- dig: go deeper into something specific the answer named ("What's AiSDR doing in Nigeria?").
- challenge: question the answer's own conclusion, the way a sharp cofounder would ("Is SunCulture too big for us?").
- nudge: something waiting for the founder in their situation, when it matters more than the answer's topic
  ("StartupEast closes in 29 days: draft it").

Rules:
- Specific, never generic: use the names, places and numbers from the answer and the situation.
  Not "Tell me more" or "Find leads", but "Find fintech leads in Lagos".
- Only things the assistant can do or answer: research, find leads, competitors, opportunities and the
  people to reach, draft and edit emails, check its own saved work, read connected apps. Saving or
  dismissing a find, and sending a draft, are the founder's own clicks on its card: never suggest them.
- Never answer a question for the founder, and never invent facts about them. If the answer ends by
  asking for something only the founder knows (their pricing, a name, an email, a decision about
  their plans) or is a check like "Does that look right?", return no options: they should type it.
- Don't repeat what the founder just said, and don't offer what the answer says is already done.
- Each under {CHOICE_CHARS} characters, no quotes, no trailing full stop.
- When nothing useful fits, return no options."""


def follow_ups(reply: str, asked: str = "", situation: str = "", ask=invoke_structured_with_fallback) -> list[str]:
    """2 or 3 replies the founder would tap next; [] when the answer wants
    them to type instead. Raises LlmProvidersExhaustedError when no model
    answers."""
    parts = [f"The founder asked:\n{asked.strip()[-ASKED_CHARS:]}" if asked.strip() else "",
             f"The assistant answered:\n{reply.strip()[-REPLY_CHARS:]}",
             f"Their situation:\n{situation.strip()[:SITUATION_CHARS]}" if situation.strip() else ""]
    found: FollowUps = ask([SystemMessage(content=_SYSTEM), HumanMessage(content="\n\n".join(p for p in parts if p))],
                           FollowUps, providers=cheap_providers(), log_label="lace:follow_ups", max_retries=1)
    options = list(dict.fromkeys(o.strip().strip('"').rstrip(".") for o in found.options))
    options = [o for o in options if o and len(o) <= CHOICE_CHARS]
    return options[:MAX_SUGGESTIONS] if len(options) >= MIN_SUGGESTIONS else []
