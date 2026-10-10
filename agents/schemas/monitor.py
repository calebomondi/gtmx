"""Competitor monitoring: the GTM-relevant changes a rival made, found by
comparing its raw site text and news between checks."""

from typing import Literal

from pydantic import Field

from agents.schemas.coercion import LenientModel


class CompetitorChange(LenientModel):
    kind: Literal["pricing", "product", "positioning", "funding", "leadership", "partnership", "news"]
    title: str = Field(description="Under 10 words, e.g. 'Cut Pro plan price to $8/seat'")
    summary: str = Field(description="What changed and why it matters to us, two sentences max")
    source_url: str = ""
    importance: Literal["high", "medium", "low"]


class ChangeReport(LenientModel):
    changes: list[CompetitorChange] = Field(default_factory=list)
