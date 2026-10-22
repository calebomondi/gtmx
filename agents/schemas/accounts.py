"""Target accounts found by account discovery."""

import re
from typing import Literal
from urllib.parse import urlparse

from pydantic import Field, field_validator

from agents.schemas.coercion import coerce_json, LenientModel

# A person's own accounts beyond email and LinkedIn, in the order a first
# message tries them.
PERSON_SOCIALS = ("x", "instagram", "facebook", "tiktok")
_SOCIAL_HOSTS = {"x": ("x.com", "twitter.com"), "instagram": ("instagram.com",), "facebook": ("facebook.com",),
                 "tiktok": ("tiktok.com",)}
_SOCIAL_PROFILE = {"x": "https://x.com/{}", "instagram": "https://www.instagram.com/{}",
                   "facebook": "https://www.facebook.com/{}", "tiktok": "https://www.tiktok.com/@{}"}
_HANDLE = re.compile(r"^@?([A-Za-z0-9_.]{1,50})$")


def social_profile_url(platform: str, value: str | None) -> str | None:
    """A profile URL from a URL or a bare handle ("@acme"); None when it is
    blank or a link to another site."""
    value = (value or "").strip()
    if not value:
        return None
    if "/" not in value:
        handle = _HANDLE.match(value)
        return _SOCIAL_PROFILE[platform].format(handle.group(1)) if handle else None
    url = value if re.match(r"^https?://", value, re.I) else "https://" + value
    host = (urlparse(url).hostname or "").lower()
    return url if any(host == h or host.endswith("." + h) for h in _SOCIAL_HOSTS[platform]) else None


class ContactRecord(LenientModel):
    """A person to reach out to at a target account. Never fabricate contact
    details — only fill in what appears in the sources."""

    name: str | None = Field(default=None, description="Full name, if found")
    title: str | None = Field(default=None, description="Job title, if found")
    linkedin: str | None = Field(default=None, description="LinkedIn URL, if found")
    email: str | None = Field(default=None, description="Email address, if found")
    x: str | None = Field(default=None, description="Their own X (Twitter) profile URL, if found")
    instagram: str | None = Field(default=None, description="Their own Instagram profile URL, if found")
    facebook: str | None = Field(default=None, description="Their own Facebook profile URL, if found")
    tiktok: str | None = Field(default=None, description="Their own TikTok profile URL, if found")

    @field_validator(*PERSON_SOCIALS)
    @classmethod
    def _profile_url(cls, v, info):
        return social_profile_url(info.field_name, v)

    def addresses(self) -> dict[str, str]:
        """Each channel they can be reached on, best first: email, LinkedIn,
        then their own social accounts."""
        found = {"email": self.email, "linkedin": self.linkedin, **{p: getattr(self, p) for p in PERSON_SOCIALS}}
        return {channel: address for channel, address in found.items() if address}


class SourceRecord(LenientModel):
    title: str = Field(description="Title of the source")
    url: str = Field(description="URL of the source")
    snippet: str | None = Field(default=None, description="Relevant snippet from the source")


class TriggerEvent(LenientModel):
    """A current, verifiable event at the account that makes it worth reaching
    out now. Required on every target account."""

    event: str = Field(description="Short description of the signal observed")
    signal_type: Literal[
        "hiring_post",
        "competitor_review_mention",
        "payment_integration",
        "social_growth_spike",
        "community_growth_spike",
        "product_listing",
        "funding_round",
        "event_upcoming",
        "founder_added",
    ] = Field(description="Which trigger signal type this event matches (founder_added is set by the app for "
                          "accounts the founder named, never by a search)")
    source: str = Field(description="URL/where the trigger was observed")


class AccountRecord(LenientModel):
    """A target account for GTM outreach: a company, OR — for consumer offers —
    a discoverable channel/community/event/creator/platform where the ICP
    congregates, with the named people to reach out to and the current trigger."""

    name: str = Field(description="Company / community / event / creator / platform name")
    account_type: Literal["company", "community", "event", "creator", "platform"] = Field(
        default="company",
        description="What kind of target this is — company, or a consumer-reach venue (community/event/creator/platform)",
    )
    website: str | None = Field(default=None, description="Company website URL, if found")
    domain: str | None = Field(default=None, description="Website domain, if found")
    platform: str | None = Field(default=None, description="For non-company targets: the platform it lives on (LinkedIn group, Substack, YouTube, Discord, subreddit name, etc.)")
    venue: str | None = Field(default=None, description="For events: city/venue where it happens")
    event_date: str | None = Field(default=None, description="For events: date/period, if stated")
    member_size: str | None = Field(default=None, description="For communities/creators: audience/member size, if stated")
    summary: str | None = Field(
        default=None,
        description="One or two plain sentences on what this target does and who it serves, from the sources (e.g. 'Nairobi lender offering asset-financed loans to SMEs and gig drivers'). Not why it fits the ICP -- that is why_selected.",
    )
    industry: str | None = Field(default=None, description="Industry the company operates in")
    size: str | None = Field(default=None, description="Company size (headcount/revenue band), if found")
    geo: str | None = Field(default=None, description="Country/region the target is based in")
    tech_stack: list[str] = Field(default_factory=list, description="Relevant technologies/tools the company uses, if found")
    recent_news: list[str] = Field(default_factory=list, description="Notable recent developments at the target")
    key_contacts: list[ContactRecord] = Field(
        default_factory=list,
        description="People to reach out to — for companies the decision makers, for events/communities the organisers/hosts/admin. Name/title/LinkedIn/email ONLY when present in the sources",
    )
    socials: dict[str, str] = Field(
        default_factory=dict,
        description="Company / org social page URLs keyed by platform (e.g. linkedin, instagram, tiktok, x), discovered via Bright Data. Never fabricate; only fill from verified sources.",
    )
    pain_signals: list[str] = Field(default_factory=list, description="Observed pain signals matching the ICP")
    hiring_signals: list[str] = Field(default_factory=list, description="Observed hiring signals matching the ICP")
    source_queries: list[str] = Field(default_factory=list, description="Search queries that surfaced this account")
    sources: list[SourceRecord] = Field(
        default_factory=list,
        description="Sources proving the account exists and the trigger is current",
    )
    score: float | None = Field(default=None, description="Fit score 0-1 (industry/size/geo/pain/hiring rubric)")
    score_breakdown: str | None = Field(default=None, description="Why the score was assigned")
    why_selected: list[str] = Field(
        default_factory=list,
        description="Exactly 5 reasons this account matches the ICP",
    )
    why_reach_out: list[str] = Field(
        default_factory=list,
        description="Exactly 5 angles for the outreach message opening",
    )
    trigger_event: TriggerEvent = Field(description="The current trigger making this account worth contacting now")

    @field_validator(
        "tech_stack", "recent_news", "key_contacts", "pain_signals",
        "hiring_signals", "source_queries", "sources", "why_selected",
        "why_reach_out",
        mode="before",
    )
    @classmethod
    def _coerce_list_fields(cls, v):
        # Models frequently emit null for optional list fields; a list field with
        # default_factory only defaults on *missing*, not explicit null. Also
        # tolerate double-serialized JSON strings.
        if v is None:
            return []
        return coerce_json(v)

    @field_validator("socials", mode="before")
    @classmethod
    def _coerce_socials_field(cls, v):
        if v is None:
            return {}
        parsed = coerce_json(v)
        return parsed if isinstance(parsed, dict) else {}


class AccountList(LenientModel):
    accounts: list[AccountRecord] = Field(
        description="4-8 target accounts found for outreach, each with a current trigger event",
    )


class AccountFit(LenientModel):
    """Why THIS offer suits THIS account now: the case a seller would make,
    written before any message. Every field comes from the offer and the
    account record; an empty field means the record doesn't support it."""

    need: str = Field(description="What the account needs right now, read off its trigger and record, in their terms")
    capability: str = Field(
        description="The one capability of the offer that answers that need, named as the offer describes it",
    )
    payoff: str = Field(
        description="What that is worth to their business: what they save, earn, speed up or stop risking. "
                    "Concrete to them; a number only when the record or offer states one",
    )
    benefit: str = Field(default="", description="The kind of payoff: lower cost, more revenue, time saved, or less risk")
    angle: str = Field(description="How to open the conversation: the trigger tied to the payoff, one sentence")
    strength: Literal["strong", "moderate", "weak"] = Field(
        default="moderate",
        description="strong = the trigger creates a need the offer directly answers; weak = only a loose link",
    )

    @field_validator("need", "payoff", "angle")
    @classmethod
    def _stated(cls, value: str) -> str:
        # The card is empty without these, so a blank one is sent back.
        if not (value or "").strip():
            raise ValueError("must be stated, in a sentence")
        return value.strip()


class CompetitorClient(LenientModel):
    """An organization a competitor names as its customer: someone already
    buying what the offer sells, so a switching prospect."""

    name: str = Field(description="The client organization's name, exactly as the source writes it")
    website: str | None = Field(default=None, description="The client's own website, only if a source gives it")
    country: str | None = Field(default=None, description="Where the client operates, only if a source states it")
    relationship: Literal["case_study", "testimonial", "customer_logo", "announced_deal", "profile"] = Field(
        default="profile", description="How the competitor shows them as a customer",
    )
    evidence: str = Field(description="A short quote from the source naming them as the competitor's customer")
    source_url: str = Field(description="The URL the evidence comes from")


class CompetitorClients(LenientModel):
    clients: list[CompetitorClient] = Field(default_factory=list)
