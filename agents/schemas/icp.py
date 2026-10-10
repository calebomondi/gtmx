"""The ideal customer profile and its building blocks."""

from typing import Literal

from pydantic import BaseModel, create_model, Field, field_validator, model_validator

from agents.schemas.coercion import coerce_json


class IcpFindings(BaseModel):
    """ICP notes + concise go-to-market understanding, from the gtm specialist.

    Unlike the research stages' findings, these notes carry NO `### Sources` block
    by design: the ICP stage is a synthesis and nothing new is retrieved, so every
    claim is citable only by label (`[market findings]`, `[competition findings]`,
    `[offer material]`, ...)."""

    findings: str = Field(description="Detailed markdown notes laying out the offer's ideal customer profile and how it will be reached — the buyer-bearing firmographics (industries, sizes, titles) or consumer personas, the channels/communities/events where they congregate, the beachhead, messaging angles, exclusions and competitor-lead surfaces the report section has to be built from")
    icp_understanding: str = Field(
        description="Brief understanding of who the ideal customer is and where to reach them; target 40 words, maximum 50"
    )


class CompetitorLead(BaseModel):
    """A competitor the ICP should hunt comparative/pain-angle accounts against,
    derived from the understand_competition output."""

    competitor_name: str = Field(description="Name of the competitor")
    search_queries: list[str] = Field(
        default_factory=list,
        description="Web queries for finding accounts evaluating/reviewing this competitor",
    )
    pain_angles: list[str] = Field(
        default_factory=list,
        description="Pain points customers of this competitor report, usable as outreach angles",
    )


class BuyerPersona(BaseModel):
    """A named consumer/professional persona the ICP should target — the human
    buying unit, especially relevant when the offer sells directly to consumers."""

    name: str = Field(description="Short persona name, e.g. 'Meeting-heavy professional'")
    who: str = Field(description="Who they are + the job-to-be-done this offer helps with")
    where_they_congregate: list[str] = Field(
        default_factory=list,
        description="Platforms/communities/event types where these people gather",
    )
    intent_signals: list[str] = Field(
        default_factory=list,
        description="Behaviors/problem statements that indicate this persona is in market",
    )

    @field_validator("where_they_congregate", "intent_signals", mode="before")
    @classmethod
    def _coerce_nested_json_fields(cls, v):
        return coerce_json(v)


class TargetChannel(BaseModel):
    """A discoverable venue where ideal customers/audiences congregate — the unit
    of reach for consumer offers (and a useful secondary axis for B2B)."""

    channel_type: Literal[
        "social_platform",
        "community",
        "event",
        "creator",
        "newsletter",
        "marketplace",
        "forum",
    ] = Field(description="What kind of venue this is")
    name: str = Field(description="Concrete channel/community/event/creator name, or a typed placeholder like 'LinkedIn groups for X'")
    audience_fit: str = Field(description="Why the right audience is there and how well they match the ICP (evidence-grounded)")
    first_angle: str = Field(description="How to engage this channel first — post format, sponsor slot, booth, creator outreach")


class ICP(BaseModel):
    """Ideal Customer Profile for the product, synthesised by the GTM specialist
    from the market + competition understanding. Guides which targets to discover."""

    product_name: str | None = Field(default=None, description="The product being profiled")
    buyer_type: str | None = Field(default=None, description="B2B, B2C, or both")
    industries: list[str] = Field(
        default_factory=list,
        description="2-3 industries whose companies are the best fit (B2B emphasis)",
    )
    company_sizes: list[str] = Field(
        default_factory=list,
        description="Target company size bands (headcount/revenue), e.g. ['50-200', '201-1000'] (B2B emphasis)",
    )
    geo: list[str] = Field(
        default_factory=list,
        description="Target geographies by name (as produced by the market phase)",
    )
    buyer_titles: list[str] = Field(
        default_factory=list,
        description="Job titles/personas to reach out to at target accounts (B2B emphasis)",
    )
    buyer_personas: list[BuyerPersona] = Field(
        default_factory=list,
        description="Named personas defined in detail — fill for B2C; secondary depth for B2B",
    )
    target_channels: list[TargetChannel] = Field(
        default_factory=list,
        description="Discoverable venues where the ICP congregates — social platforms, communities, events, creators, newsletters (essential for B2C)",
    )
    event_focus: str | None = Field(
        default=None,
        description="Events/summits/conferences/meetups whose attendees match the ICP — attendance profile, not a specific event list",
    )
    messaging_angles: list[str] = Field(
        default_factory=list,
        description="Opening angles/hooks per channel — how to first engage the audience there",
    )
    beachhead: str | None = Field(
        default=None,
        description="One-line 'attack this segment/channel first' — the initial beachhead to validate before scaling",
    )
    exclusions: list[str] = Field(
        default_factory=list,
        description="Explicit segments to exclude (e.g. 'agencies', 'hobbyists', '<100 employees')",
    )
    pain_signals: list[str] = Field(
        default_factory=list,
        description="Problems/intents that indicate an audience/account is actively evaluating a solution",
    )
    intent_keywords: list[str] = Field(
        default_factory=list,
        description="Keywords that appear in outreach/review contexts when audiences/accounts are in-market",
    )
    competitor_leads: list[CompetitorLead] = Field(
        default_factory=list,
        description="Competitors whose customers/audiences are prime targets, with pain angles (for B2C these may be competitor communities/creators)",
    )

    @field_validator(
        "industries", "company_sizes", "geo", "buyer_titles", "buyer_personas",
        "target_channels", "messaging_angles", "exclusions", "pain_signals",
        "intent_keywords", "competitor_leads",
        mode="before",
    )
    @classmethod
    def _coerce_nested_json_fields(cls, v):
        return coerce_json(v)


class _RevisionBase(BaseModel):
    @model_validator(mode="before")
    @classmethod
    def _coerce_json_fields(cls, data):
        # Same double-serialisation repair ICP applies to its list fields.
        if isinstance(data, dict):
            return {k: coerce_json(v) for k, v in data.items()}
        return data

    def changed_fields(self) -> dict:
        return {name: value for name, value in self.model_dump().items() if value is not None}


# A patch to an ICP: every ICP field, optional, defaulting to "unchanged" (null).
# Generated from ICP's own fields so the two can never drift apart. The refine
# pass returns only what it corrects -- a full ICP is ~3.6k output tokens, the
# corrections a few hundred, and output length is what an LLM call's latency
# scales with.
ICPRevision = create_model(
    "ICPRevision",
    __base__=_RevisionBase,
    __doc__="Corrections to a draft ICP. Null = keep the draft's value; a list is replaced whole.",
    **{
        name: (field.annotation | None, Field(default=None, description=field.description))
        for name, field in ICP.model_fields.items()
    },
)
