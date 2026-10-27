"""Competitor monitoring: the GTM-relevant changes a rival made, found by
comparing its raw site text, news, events and social posts between checks."""

from typing import Literal

from pydantic import Field

from agents.schemas.coercion import LenientModel


MoveKind = Literal[
    "pricing", "product", "positioning", "funding", "leadership", "partnership", "event", "social", "news", "client",
]
MOVE_KINDS: tuple[str, ...] = MoveKind.__args__
MoveImportance = Literal["high", "medium", "low"]
MOVE_IMPORTANCES: tuple[str, ...] = MoveImportance.__args__


class CompetitorChange(LenientModel):
    kind: MoveKind
    title: str = Field(description="Under 10 words, e.g. 'Cut Pro plan price to $8/seat'")
    summary: str = Field(description="What changed and why it matters to us, two sentences max")
    implication: str = Field(
        default="",
        description="What it means for us, concretely: the deals, buyers or positioning it threatens or opens up",
    )
    counter_move: str = Field(
        default="",
        description="The one move we should make in response, e.g. 'Email the three accounts we share with them "
                    "about our flat pricing before their renewal'",
    )
    client_name: str = Field(
        default="",
        description="kind=client only: the named organization the change is about, exactly as the source writes it",
    )
    client_country: str = Field(default="", description="kind=client only: where that client operates, if stated")
    source_url: str = ""
    # Models leave it out now and then; a missing grade is a middling one,
    # not a reason to ask again.
    importance: MoveImportance = "medium"


class ChangeReport(LenientModel):
    changes: list[CompetitorChange] = Field(default_factory=list)
