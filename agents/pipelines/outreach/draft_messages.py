"""Draft one personalized first-touch message to a target account.

Pure: the backend supplies the offer/ICP context and the account as text. The
draft is a starting point the user edits and approves -- the agent never sends.
"""

from langchain_core.messages import HumanMessage, SystemMessage

from agents.llm.main import invoke_structured_with_fallback
from agents.schemas.outreach import OutreachDraft

_CHANNEL_RULES = {
    "email": "A cold email: a subject under 8 words, a body under 120 words.",
    "linkedin": "A LinkedIn message: no subject, under 80 words, conversational.",
}

_PROMPT = """You write first-touch B2B outreach for {sender}'s offer. Write ONE message to
the account below.

{channel_rule}

RULES
- Open with something specific to THIS account, taken from its signals below
  (a trigger event, a pain signal, why it was selected). Never invent facts,
  names, numbers, mutual connections or compliments the data does not support.
- One clear problem -> outcome link to the offer, in plain words. No feature lists.
- One low-friction ask (a short call, a question, a resource). No pressure.
- No buzzwords, no exclamation marks, no "I hope this finds you well".
- Address the contact by first name if one is given; otherwise no name.
- Plain text only. Sign off as {sender}.

OFFER AND IDEAL CUSTOMER
{offer_context}

ACCOUNT
{account}"""


def draft(channel: str, offer_context: str, account: str, sender: str) -> OutreachDraft:
    result = invoke_structured_with_fallback(
        messages=[
            SystemMessage(content=_PROMPT.format(
                sender=sender or "the sender", channel_rule=_CHANNEL_RULES[channel],
                offer_context=offer_context, account=account,
            )),
            HumanMessage(content="Write the message now."),
        ],
        schema=OutreachDraft,
        log_label=f"outreach_draft:{channel}",
        thinking=False,
    )
    if channel == "linkedin":
        result = result.model_copy(update={"subject": ""})
    return result
