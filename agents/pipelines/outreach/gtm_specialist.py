"""The GTM specialist writes first-touch outreach for one target account.

Pure: the backend supplies the offer, the team's research and the account as
text; this returns a draft the user edits and approves -- it never sends.

Four steps, each its own LLM call so each can be checked:
1. research  -- read the account's site and the source of its trigger event,
                and pull out specific, current facts (cheap model);
2. plan      -- the GTM specialist picks the angle (hook fact -> problem ->
                outcome -> ask) and decides whether to consult the product,
                market or competition specialist;
3. consult   -- each consulted specialist answers one question from their
                own research, in character (cheap model, at most two);
4. write + review -- draft in the sender's voice, then check it against a
                rubric; one rewrite with the reviewer's notes if it fails.
"""

import re
from dataclasses import dataclass, field

from langchain_core.messages import HumanMessage, SystemMessage

from agents.llm.main import cheap_providers, invoke_structured_with_fallback
from agents.pipelines import team
from agents.pipelines.outreach import grounding
from agents.pipelines.web_utils import call_with_timeout
from agents.schemas.outreach import AccountResearch, DraftReview, OutreachDraft, OutreachPlan
from config import get_settings
from data_sources.scraping.exa import scrape_url
from utils.log import logger

_PAGE_CHARS = 6_000
MAX_REWRITES = 2
_WORD_LIMITS = {"email": (50, 140), "linkedin": (25, 90)}
_SCRAPE_TIMEOUT_S = 25

CHANNEL_RULES = {
    "email": "A cold email: a subject under 8 words built on the hook (their name, event or number, not a generic benefit), and a body of 60-120 words in 3 short paragraphs after the greeting.",
    "linkedin": "A LinkedIn connection note or message: no subject, 40-80 words, conversational, one paragraph or two.",
}

@dataclass
class OutreachBrief:
    """Everything the specialist knows when writing to one account."""

    channel: str
    sender_name: str
    offer: str
    account: str
    contact_name: str | None = None
    contact_title: str | None = None
    website: str | None = None
    trigger_source: str | None = None
    # company | community | event | creator | platform: a company is a buyer;
    # the others are audiences, reached through a partnership.
    account_type: str = "company"
    # The workspace's specialist team, by domain ("gtm", "product"/"service",
    # "market", "competition"): {name, role, description}.
    team: dict[str, dict] = field(default_factory=dict)
    # Each specialist's own research, by domain, as text.
    research: dict[str, str] = field(default_factory=dict)


def _sources(brief: OutreachBrief) -> str:
    """The account's own homepage and the page its trigger was seen on."""
    cfg = get_settings()
    urls = [u for u in dict.fromkeys([brief.website, brief.trigger_source]) if u]
    pages = []
    for url in urls:
        text = call_with_timeout(lambda u=url: scrape_url(u, cfg), _SCRAPE_TIMEOUT_S, default="",
                                 label=f"outreach_source[{url}]") or ""
        if text.strip():
            pages.append(f"[{url}]\n{text[:_PAGE_CHARS]}")
    return "\n\n".join(pages) or "(the account's pages could not be read)"


_RESEARCH_PROMPT = """You research a target account before outreach. From the ACCOUNT RECORD and
SOURCES, extract what the account does and 3-6 SPECIFIC, CURRENT facts a
sharp seller would open with: launches, hires, expansions, funding, events,
numbers, quotes, new markets. Each fact must be stated in the sources or the
record; cite its URL. Never write generic statements ("they value
innovation"). If the sources are thin, return fewer facts.

ACCOUNT RECORD
{account}

SOURCES
{sources}"""

_PLAN_PROMPT = """You are {persona}. You own go-to-market for {offer_name}, and you write the
team's outreach. Plan ONE message to the account below before writing it.

{mode}

Pick the angle a senior seller would: the single most relevant account fact
as the hook, the problem it implies for them, the concrete outcome {offer_name}
gives (numbers or a before/after only when the research supports them), a
proof point if one exists, and one low-friction ask. The ask is about THEM
(their workload, their timeline, a short call) -- never "how we're helping
others" or "how other companies are doing X": that claims customers and
results the research does not show.

If the angle depends on another specialist's expertise -- how the offer
compares to a competitor the account uses, a product capability, a market or
pricing norm -- add up to 2 consultations with a precise question each.
Otherwise leave consult empty.

OFFER AND TEAM RESEARCH
{offer}

ACCOUNT RESEARCH
{research}

ACCOUNT RECORD
{account}

CONTACT: {contact}"""

_WRITE_PROMPT = """You are {persona}. Write the message {sender} will send. {mode}

Write as {sender},
in the first person, plain text, signed "{sender}".

{channel_rule}

Structure:
- Greeting: "Hi <first name>," when the contact is known, else "Hi <account> team,".
- Line 1: the hook fact, tied to why it matters to them now (e.g. what it
  makes harder or more urgent). About THEM, not us.
- Then the problem -> outcome link in plain words, one proof point at most.
  Their problem is a hypothesis: frame it as what teams in their position
  usually hit, or ask -- never claim to know their internal situation.
- One ask, as a question.
- Sign-off: just the sender's name.

Use the specialists' notes where they sharpen the angle.

Never: invent facts, names, numbers, customers or compliments; claim to know
their internal problems ("we're aware that your..."); list features; use
buzzwords ("synergy", "leverage", "revolutionize", "cutting-edge",
"enhance", "drive impact"); open with "I hope", "I came across", "I saw
that", "Quick intro"; use exclamation marks.
{feedback}
CONTACT: {contact}

PLAN
{plan}

SPECIALIST NOTES
{notes}

OFFER
{offer}"""

_REVIEW_PROMPT = """Review this outreach {channel} against the checks. It FAILS if any is false:
1. It greets the contact (or the account's team), then opens on a specific fact about the account that appears in the RESEARCH.
2. No claim, number, customer or name appears that is not in the RESEARCH, PLAN or OFFER.
3. It states one concrete outcome for the account, not a feature list.
4. It has exactly one clear, low-friction ask.
5. No generic filler ("I hope this finds you well", "quick intro", "I came across", buzzwords), and it never asserts the account's internal problems as known fact.
6. Length fits: {channel_rule}
7. It is signed with "{sender}".
8. (email) The subject is about THEM -- their name, event or number -- not a generic benefit.

RESEARCH
{research}

PLAN
{plan}

OFFER
{offer}

MESSAGE
Subject: {subject}
{body}"""


def _contact(brief: OutreachBrief) -> str:
    if not brief.contact_name:
        return "unknown (address the team, no name)"
    return f"{brief.contact_name}" + (f", {brief.contact_title}" if brief.contact_title else "")


def research_account(brief: OutreachBrief, pages: str) -> AccountResearch:
    return invoke_structured_with_fallback(
        [SystemMessage(content=_RESEARCH_PROMPT.format(account=brief.account, sources=pages)),
         HumanMessage(content="Extract the research now.")],
        AccountResearch, providers=cheap_providers(), log_label="outreach_research",
    )


_SALES = "This is a SALES message: the account could buy the offer."
_PARTNERSHIP = (
    "This account is a {kind} -- an audience, not a buyer. Write a PARTNERSHIP pitch to its organiser "
    "or creator: propose one concrete collaboration that serves THEIR audience (a co-hosted session or "
    "workshop, a sponsored post or episode, a member discount, an affiliate or referral arrangement, a "
    "giveaway). The outcome is for their members or followers; the ask is a yes to that collaboration "
    "or a short call about it. Never pitch them as a customer."
)


def outreach_mode(brief: OutreachBrief) -> str:
    kind = (brief.account_type or "company").lower()
    return _SALES if kind == "company" else _PARTNERSHIP.format(kind=kind)


def plan_message(brief: OutreachBrief, research: AccountResearch, offer_name: str) -> OutreachPlan:
    return invoke_structured_with_fallback(
        [SystemMessage(content=_PLAN_PROMPT.format(
            persona=team.persona(team.member(brief.team, "gtm")), offer_name=offer_name, offer=brief.offer,
            research=research.model_dump_json(indent=1), account=brief.account, contact=_contact(brief),
            mode=outreach_mode(brief),
        )), HumanMessage(content="Plan the message now.")],
        OutreachPlan, log_label="outreach_plan",
    )


def _write(brief: OutreachBrief, plan: OutreachPlan, notes: str, feedback: str = "") -> OutreachDraft:
    draft = invoke_structured_with_fallback(
        [SystemMessage(content=_WRITE_PROMPT.format(
            persona=team.persona(team.member(brief.team, "gtm")), sender=brief.sender_name,
            channel_rule=CHANNEL_RULES[brief.channel], contact=_contact(brief), mode=outreach_mode(brief),
            plan=plan.model_dump_json(indent=1, exclude={"consult"}), notes=notes, offer=brief.offer,
            feedback=f"\nA reviewer rejected your last version. Fix: {feedback}\n" if feedback else "",
        )), HumanMessage(content="Write the message now.")],
        OutreachDraft, log_label=f"outreach_write:{brief.channel}",
    )
    return draft.model_copy(update={"subject": ""}) if brief.channel == "linkedin" else draft


def lint(brief: OutreachBrief, draft: OutreachDraft, sources: str | None = None) -> list[str]:
    """Mechanical checks the reviewer model can miss. `sources` is everything
    the writer was given; every quantity in the draft must appear in it."""
    body = draft.body.strip()
    problems = grounding.problems(f"{draft.subject}\n{body}", sources if sources is not None else _brief_sources(brief))
    if not re.match(r"^(hi|hello|dear)\b", body, re.I):
        problems.append("Open with a greeting (Hi <first name>, or Hi <account> team,)")
    if re.match(r"^hi team\b", body, re.I):
        problems.append("Name the account in the greeting: Hi <account> team,")
    if body.count("?") != 1:
        problems.append("End with exactly one ask, phrased as a question")
    if "!" in body:
        problems.append("Remove exclamation marks")
    if brief.sender_name and not body.rstrip().endswith(brief.sender_name):
        problems.append(f'Sign off with just "{brief.sender_name}"')
    low, high = _WORD_LIMITS[brief.channel]
    words = len(body.split())
    if not low <= words <= high:
        problems.append(f"Keep it between {low} and {high} words (it has {words})")
    return problems


def _brief_sources(brief: OutreachBrief, *extra: str) -> str:
    return "\n".join([brief.offer, brief.account, *brief.research.values(), *extra])


def review(brief: OutreachBrief, research: AccountResearch, plan: OutreachPlan, draft: OutreachDraft) -> DraftReview:
    return invoke_structured_with_fallback(
        [SystemMessage(content=_REVIEW_PROMPT.format(
            channel=brief.channel, channel_rule=CHANNEL_RULES[brief.channel], sender=brief.sender_name,
            research=research.model_dump_json(indent=1), plan=plan.model_dump_json(indent=1, exclude={"consult"}),
            offer=brief.offer, subject=draft.subject or "(none)", body=draft.body,
        )), HumanMessage(content="Review it now.")],
        DraftReview, providers=cheap_providers(), log_label="outreach_review",
    )


def write_first_touch(brief: OutreachBrief, offer_name: str) -> OutreachDraft:
    """Research, plan, consult, write and review one first-touch message."""
    pages = _sources(brief)
    research = research_account(brief, pages)
    plan = plan_message(brief, research, offer_name)
    notes = team.consult_all(brief.team, brief.research, plan.consult, "gtm", "The GTM specialist, writing outreach,",
                             "outreach_consult")
    draft = _write(brief, plan, notes)
    verdict = review(brief, research, plan, draft)
    # Numbers must trace to evidence: the offer, the account, the saved research
    # and the pages read here. The research notes and the specialists' advice
    # are model-written, so a figure they invent can't vouch for itself.
    sources = _brief_sources(brief, pages)
    problems = lint(brief, draft, sources) + ([] if verdict.passes else verdict.problems)
    # The review's verdict counts once; the mechanical checks are re-run after
    # each rewrite, because a rewrite can keep (or add) the same mistake.
    for _ in range(MAX_REWRITES):
        if not problems:
            break
        logger.info("Outreach draft rewritten after review: %s", "; ".join(problems))
        draft = _write(brief, plan, notes, feedback="; ".join(problems))
        problems = lint(brief, draft, sources)
    if problems:
        logger.warning("Outreach draft still has problems after %d rewrites: %s", MAX_REWRITES, "; ".join(problems))
    return draft
