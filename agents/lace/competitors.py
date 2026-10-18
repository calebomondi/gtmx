"""The competitor hunt, for a Lace: v1's proven pipeline, briefed from facts.

v1's hunt (plan -> hunt -> screen -> profile, in pipelines/competitors) is
shaped by competitor archetypes that v1 discovery produced. A Lace has facts
instead, so one structured call first sketches the archetypes and the offer
from them; the hunt then runs unchanged, with its brand-free queries, website
screening, substitute gate and sourced profiles.

Synchronous and long (minutes): the backend runs it as a background job.
Monitoring reuses v1's change detector (pipelines/monitor/check_competitor)
per firm; the helpers here describe the Lace's offer to it and turn what it
finds into facts.
"""

from collections.abc import Callable, Sequence

from langchain_core.messages import HumanMessage, SystemMessage

from agents.pipelines.competitors.get_competitors import build_competitors_graph, state_from_workspace
from agents.lace.prompts import render_brief
from agents.llm.main import invoke_structured_with_fallback
from agents.schemas.competition import CompetitorProfile
from agents.schemas.lace import CompetitorHuntBrief, Fact, LaceProfile, NewFact
from agents.schemas.monitor import CompetitorChange

# The brief step, injectable so tests can script it: messages -> brief.
Brief = Callable[[Sequence], CompetitorHuntBrief]
# The hunt itself, injectable likewise: v1 state -> v1 final state.
Hunt = Callable[[dict], dict]

_BRIEF_PROMPT = """You prepare a competitor search for a startup. A competitor
is a company a buyer would pay INSTEAD of this startup, for the same main job.
From the facts below, write:
- offer_summary: two or three sentences naming the main job buyers hire the
  startup for (its primary category, e.g. "issue tracking for software
  teams"), and who those buyers are. Leave out secondary features: a startup
  with a docs feature does not compete with every wiki.
- target_geographies: the countries or regions it sells in, only if the facts
  say so;
- profile: 4-6 archetypes of company that do that main job for those buyers:
  direct substitutes first, then local incumbents, global entrants and
  do-it-yourself alternatives, as they apply. Not tools it integrates with,
  and not products that overlap on one side feature. Each has a short label,
  what it is, and where it operates. Name no real company: these are shapes to
  search for, not answers.
{focus}
Facts about the startup:
{facts}"""


def _default_brief(messages: Sequence) -> CompetitorHuntBrief:
    return invoke_structured_with_fallback(messages, CompetitorHuntBrief, log_label="lace:competitor_brief")


def _default_hunt(state: dict) -> dict:
    return build_competitors_graph().invoke(state)


def hunt_brief(facts: list[Fact], focus: str | None, brief: Brief = _default_brief) -> CompetitorHuntBrief:
    focus_line = f"\nThe founder asked to focus on: {focus}\n" if focus else ""
    prompt = _BRIEF_PROMPT.format(focus=focus_line, facts=render_brief(facts))
    return brief([SystemMessage(content=prompt), HumanMessage(content="Write the brief.")])


def find_competitors(profile: LaceProfile, facts: list[Fact], focus: str | None = None,
                     brief: Brief = _default_brief, hunt: Hunt = _default_hunt) -> list[CompetitorProfile]:
    """Real, sourced competitor profiles for the Lace's startup. Raises
    ValueError when the facts are too thin to say what competes."""
    plan = hunt_brief(facts, focus, brief)
    if not plan.profile.archetypes:
        raise ValueError("Not enough is known about what the startup sells to say what competes with it.")
    state = state_from_workspace(
        offer_name=profile.startup_name or profile.website,
        offer_description=plan.offer_summary,
        own_website=profile.website,
        ideal_competitor_profile=plan.profile.model_dump(),
        target_market=plan.target_geographies,
    )
    return list(hunt(state).get("competitor_profiles") or [])


# Changes worth telling the founder about; low-importance ones are only kept
# in the monitor's baseline.
MATERIAL = ("high", "medium")
# The offer as the change detector sees it: enough to judge what a rival's
# move means for the startup.
OFFER_DETAIL_TOKENS = 600


def offer_for_monitor(profile: LaceProfile, facts: list[Fact]) -> tuple[str, str]:
    """(our offer's name, what it is) for v1's change detector."""
    offer_facts = [f for f in facts if f.topic in ("offer", "pricing", "positioning", "icp")]
    return profile.startup_name or profile.website, render_brief(offer_facts, cap=OFFER_DETAIL_TOKENS)


def material(changes: list[CompetitorChange]) -> list[CompetitorChange]:
    return [c for c in changes if c.importance in MATERIAL]


def change_fact(competitor: str, change: CompetitorChange) -> NewFact | None:
    """A sourced change as a fact on the Lace's timeline; None without a source,
    because only the founder's word stands without one."""
    if not change.source_url:
        return None
    return NewFact(topic="competition", claim=f"{competitor}: {change.title}. {change.summary}",
                   source_url=change.source_url, confidence="high", origin="monitor")
