"""Competitor monitoring: the GTM-relevant changes a rival made, found by
comparing its raw site text, news, events and social posts between checks."""

from typing import Literal

from pydantic import Field

from agents.schemas.coercion import LenientModel


class CompetitorChange(LenientModel):
    kind: Literal["pricing", "product", "positioning", "funding", "leadership", "partnership", "event", "social", "news"]
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
    source_url: str = ""
    importance: Literal["high", "medium", "low"]


class ChangeReport(LenientModel):
    changes: list[CompetitorChange] = Field(default_factory=list)
