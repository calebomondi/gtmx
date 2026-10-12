"""The outreach agent's structured steps: research an account, plan the
angle (consulting other specialists when needed), write, and review."""

from typing import Literal

from pydantic import Field

from agents.schemas.coercion import LenientModel

ConsultDomain = Literal["product", "market", "competition", "gtm"]


class AccountFact(LenientModel):
    fact: str = Field(description="One specific, current fact about the account, in plain words")
    source: str = Field(default="", description="URL the fact comes from")


class AccountResearch(LenientModel):
    """What the GTM specialist learned about the account before writing."""

    what_they_do: str = Field(description="One sentence: what the account does and for whom")
    facts: list[AccountFact] = Field(
        default_factory=list,
        description="3-6 specific, verifiable facts from the sources: launches, hires, expansions, events, numbers, quotes. Never generic statements",
    )
    likely_priorities: list[str] = Field(
        default_factory=list, description="2-3 things this account is probably working on now, each tied to a fact",
    )


class Consultation(LenientModel):
    domain: ConsultDomain
    question: str = Field(description="One precise question for that specialist")


class OutreachPlan(LenientModel):
    """The angle, decided before any copy is written."""

    hook_fact: str = Field(description="The single account fact the opening line is built on (copied from the research)")
    problem: str = Field(description="The specific problem this account likely has, in their words")
    outcome: str = Field(description="The concrete outcome the offer gives them (a number or a before/after when the research supports one)")
    proof: str = Field(default="", description="A credible proof point from the offer research; empty if none exists")
    ask: str = Field(description="One low-friction next step")
    consult: list[Consultation] = Field(
        default_factory=list,
        description="At most 2 questions for the product, market or competition specialist when the angle depends on their expertise (e.g. how the offer beats the competitor this account uses). Empty when the GTM view is enough",
    )


class OutreachDraft(LenientModel):
    subject: str = Field(default="", description="Email subject line, under 8 words, specific to the account; empty for LinkedIn")
    body: str = Field(description="The message body, plain text, signed off with the sender's name")


class DraftReview(LenientModel):
    passes: bool = Field(description="True only if every check passes")
    problems: list[str] = Field(default_factory=list, description="Each failed check, stated as what to fix")


ReplyIntent = Literal[
    "interested", "question", "objection", "meeting_request", "not_now",
    "unsubscribe", "out_of_office", "referral", "other",
]


class ReplyAnalysis(LenientModel):
    """How the GTM specialist reads a contact's reply."""

    intent: ReplyIntent
    summary: str = Field(description="One sentence: what they said and want")
    questions: list[str] = Field(default_factory=list, description="Each question they asked, verbatim or close to it")
    consult: list[Consultation] = Field(
        default_factory=list,
        description="At most 2 questions for the product, market or competition specialist needed to answer them well",
    )
    agreed_time: str = Field(
        default="",
        description="If they proposed or accepted ONE specific meeting time, it in ISO 8601 (YYYY-MM-DDTHH:MM:SS) in the timezone stated; else empty",
    )
    reply_needed: bool = Field(description="False for out-of-office notes and anything that needs no answer")


class ReplyDraft(LenientModel):
    body: str = Field(description="The reply, plain text, signed off with the sender's name")
