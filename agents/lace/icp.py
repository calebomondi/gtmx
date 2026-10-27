"""The Lace's ideal customer profile: who the startup should sell to.

A judgment, not a finding, so it is not stored as facts. It is drawn from the
facts (the founder's word above all) and the tracked competitors, and kept as
one structured profile, in v1's ICP schema because v1's account discovery
reads exactly that.
"""

from collections.abc import Callable, Sequence

from langchain_core.messages import HumanMessage, SystemMessage

from agents.lace.prompts import render_brief
from agents.llm.main import invoke_structured_with_fallback
from agents.schemas.icp import ICP
from agents.schemas.lace import CompetitorSummary, Fact, LaceProfile

# The drafting step, injectable so tests can script it: messages -> ICP.
Draft = Callable[[Sequence], ICP]

COMPETITORS_SHOWN = 12

_PROMPT = """You are the go-to-market lead for {startup}. Define who it should
sell to first: its ideal customer profile.

Ground it in the facts below. Facts the founder stated outweigh everything else:
never contradict one. Where the facts are silent, choose what a careful seller
would, and keep the profile narrow: a startup wins one segment before the next.

- buyer_type: b2b, b2c or both.
- B2B: 2-3 industries, company size bands, and the buyer titles who sign.
- B2C: 1-3 personas, and the channels where they gather.
- When it sells different things to different buyers (say, engineering work to
  companies building products, and training to corporates), give one buyer
  persona per offer, each with the signals that show that buyer needs it now
  (for engineering work: a company hiring blockchain or AI engineers after a
  raise; for training: a corporate announcing an AI programme).
- geo: where it sells. Only places the facts support; if they name none, leave
  it empty rather than guessing.
- pain_signals: what an account says or does when it needs this now (a new
  hire, a funding round, a complaint about a competitor, a regulation).
- beachhead: the one segment to win first, in a line.
- exclusions: who it is not for.
- competitor_leads: tracked competitors whose customers are good targets, with
  the pain angle for each. Only competitors from the list below.
{guidance}
Facts about {startup}:
{facts}

Tracked competitors:
{competitors}"""


# A judgment over everything known is worth some thinking, but unbounded it
# took over three minutes before a customer search could even start.
ICP_THINKING_BUDGET = 2048


def _default_draft(messages: Sequence) -> ICP:
    return invoke_structured_with_fallback(messages, ICP, log_label="lace:define_icp", thinking=True,
                                           thinking_budget=ICP_THINKING_BUDGET)


def define_icp(profile: LaceProfile, facts: list[Fact], competitors: list[CompetitorSummary],
               guidance: str | None = None, draft: Draft = _default_draft) -> ICP:
    startup = profile.startup_name or profile.website
    rivals = "\n".join(f"- {c.name} ({c.website}): {c.summary or ''}" for c in competitors[:COMPETITORS_SHOWN])
    prompt = _PROMPT.format(
        startup=startup,
        guidance=f"\nThe founder asked: {guidance}\n" if guidance else "",
        facts=render_brief(facts),
        competitors=rivals or "(none tracked yet)",
    )
    icp = draft([SystemMessage(content=prompt), HumanMessage(content="Define the ICP now.")])
    return icp.model_copy(update={"product_name": startup})
