"""Opportunities for a startup: places to showcase, buyers to sell to, and
partners. Found by search and kept only when sourced, recent and still open."""

from typing import Literal

from pydantic import Field

from agents.schemas.coercion import LenientModel

OpportunityKind = Literal["showcase", "sell", "partner"]
OPPORTUNITY_KINDS: tuple[str, ...] = OpportunityKind.__args__


class OpportunityQuery(LenientModel):
    kind: OpportunityKind
    query: str = Field(description="A specific web search, e.g. 'agritech conference Nairobi 2026 call for exhibitors'")


class OpportunityPlan(LenientModel):
    queries: list[OpportunityQuery] = Field(default_factory=list)


class Opportunity(LenientModel):
    kind: OpportunityKind
    title: str = Field(description="What it is, e.g. 'Africa Agri Tech 2026: exhibitor applications'")
    organiser: str | None = Field(default=None, description="Who runs it or is buying or partnering")
    url: str = Field(description="The page that describes it, copied exactly from the search results")
    deadline: str | None = Field(default=None, description="Closing date to apply or bid, YYYY-MM-DD, only if stated")
    date: str | None = Field(default=None, description="When it happens (events), YYYY-MM-DD, only if stated")
    location: str | None = Field(default=None, description="Where, if stated")
    why_it_fits: str = Field(description="One sentence: why this suits this startup, from its facts")
    how_to_act: str = Field(description="One sentence: the concrete next step (apply, register, contact whom)")


class OpportunityList(LenientModel):
    opportunities: list[Opportunity] = Field(default_factory=list)


OpportunityStatus = Literal["open", "dismissed"]
OPPORTUNITY_STATUSES: tuple[str, ...] = OpportunityStatus.__args__


class OpportunitySummary(Opportunity):
    id: str
