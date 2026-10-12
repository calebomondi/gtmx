"""The GTM specialist answers replies to outreach.

Pure: the backend supplies the thread, the team's research and (when the user
has Google Calendar connected) free meeting slots; this returns a reply draft
the user approves -- it never sends, and never books a meeting by itself.

Steps: read the reply (intent, questions, an agreed time) -> consult the
product, market or competition specialist on what they asked -> write the
answer in the sender's voice -> mechanical checks, one rewrite on failure.
"""

from dataclasses import dataclass, field

from langchain_core.messages import HumanMessage, SystemMessage

from agents.llm.main import cheap_providers, invoke_structured_with_fallback
from agents.pipelines import team
from agents.pipelines.outreach.gtm_specialist import BANNED
from agents.schemas.outreach import ReplyAnalysis, ReplyDraft
from utils.log import logger

_MAX_WORDS = 150


@dataclass
class ReplyBrief:
    sender_name: str
    contact_name: str | None
    offer: str
    account: str
    # The conversation, oldest first: [(who, text)], who = "us" | "them".
    thread: list[tuple[str, str]]
    team: dict[str, dict] = field(default_factory=dict)
    research: dict[str, str] = field(default_factory=dict)
    # Free 30-minute slots in the sender's calendar, human-readable, with timezone.
    free_slots: list[str] = field(default_factory=list)
    timezone: str = ""


@dataclass
class ReplyResult:
    analysis: ReplyAnalysis
    draft: ReplyDraft | None


_ANALYZE_PROMPT = """You are {persona}, handling replies to {sender}'s outreach. Read the
conversation and classify the LAST message from them.

intent: interested | question | objection | meeting_request | not_now |
unsubscribe | out_of_office | referral | other.
List each question they asked. If answering well needs another specialist
(product capability, pricing or market norms, how we compare to a competitor),
add up to 2 precise consultations. If they proposed or accepted ONE specific
meeting time, give it as agreed_time in ISO 8601 ({timezone}). reply_needed is
false for out-of-office notes.

ACCOUNT
{account}

CONVERSATION (oldest first)
{thread}"""

_REPLY_PROMPT = """You are {persona}. Write the reply {sender} will send, as {sender}, in the
first person, plain text, under {max_words} words, signed "{sender}".

Their intent: {intent}. {summary}

How to answer:
- Answer every question directly and specifically, using the specialists'
  notes and the offer. If something is not known, say you'll confirm -- never
  invent prices, numbers, customers or features.
- interested / meeting_request: move to a meeting. {slots}
- objection: acknowledge it in their words, answer with one fact, keep the door open.
- not_now: thank them, ask when to follow up.
- unsubscribe: confirm in one or two sentences that you won't contact them again. No pitch.
- referral: thank them and ask for the right person's name or an intro.
No greeting beyond "Hi <first name>," (or "Hi," if unknown). No buzzwords, no
exclamation marks, no repeating the original pitch.
{feedback}
SPECIALIST NOTES
{notes}

OFFER
{offer}

CONVERSATION (oldest first)
{thread}"""


def _thread_text(brief: ReplyBrief) -> str:
    return "\n\n".join(f"[{'us' if who == 'us' else 'them'}] {text.strip()[:3000]}" for who, text in brief.thread)


def analyze(brief: ReplyBrief) -> ReplyAnalysis:
    return invoke_structured_with_fallback(
        [SystemMessage(content=_ANALYZE_PROMPT.format(
            persona=team.persona(team.member(brief.team, "gtm")), sender=brief.sender_name, account=brief.account,
            thread=_thread_text(brief), timezone=brief.timezone or "the timezone they state",
        )), HumanMessage(content="Classify the reply now.")],
        ReplyAnalysis, providers=cheap_providers(), log_label="reply_analyze",
    )


def _slots_line(brief: ReplyBrief, analysis: ReplyAnalysis) -> str:
    if analysis.agreed_time:
        return "They named a time: confirm it and say a calendar invite is on its way."
    if brief.free_slots:
        return "Offer these times (pick 2-3, keep them as written): " + "; ".join(brief.free_slots)
    return "Ask which day and time suits them this week or next."


def lint(brief: ReplyBrief, draft: ReplyDraft) -> list[str]:
    body = draft.body.strip()
    problems = [f'Remove "{m}"' for m in dict.fromkeys(m.group(0) for m in BANNED.finditer(body))]
    if "!" in body:
        problems.append("Remove exclamation marks")
    if brief.sender_name and not body.rstrip().endswith(brief.sender_name):
        problems.append(f'Sign off with just "{brief.sender_name}"')
    if len(body.split()) > _MAX_WORDS:
        problems.append(f"Keep it under {_MAX_WORDS} words")
    return problems


def _write(brief: ReplyBrief, analysis: ReplyAnalysis, notes: str, feedback: str = "") -> ReplyDraft:
    return invoke_structured_with_fallback(
        [SystemMessage(content=_REPLY_PROMPT.format(
            persona=team.persona(team.member(brief.team, "gtm")), sender=brief.sender_name, max_words=_MAX_WORDS,
            intent=analysis.intent, summary=analysis.summary, slots=_slots_line(brief, analysis),
            notes=notes, offer=brief.offer, thread=_thread_text(brief),
            feedback=f"\nA reviewer rejected your last version. Fix: {feedback}\n" if feedback else "",
        )), HumanMessage(content="Write the reply now.")],
        ReplyDraft, log_label=f"reply_write:{analysis.intent}",
    )


def draft_reply(brief: ReplyBrief) -> ReplyResult:
    """Read the latest reply and draft the answer (None when none is needed)."""
    analysis = analyze(brief)
    if not analysis.reply_needed or analysis.intent == "out_of_office":
        return ReplyResult(analysis, None)
    notes = team.consult_all(brief.team, brief.research, analysis.consult, "gtm",
                             "The GTM specialist, answering a reply,",
                             "outreach_consult")
    draft = _write(brief, analysis, notes)
    problems = lint(brief, draft)
    if problems:
        logger.info("Reply draft rewritten: %s", "; ".join(problems))
        draft = _write(brief, analysis, notes, feedback="; ".join(problems))
    return ReplyResult(analysis, draft)
