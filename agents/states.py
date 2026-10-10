from enum import Enum
from typing import Annotated, Literal, Optional, TypedDict
import operator
import json
from pydantic import BaseModel, Field, field_validator
from langgraph.graph.message import add_messages
from langgraph.graph import MessagesState


def _coerce_json(value):
    """When weaker models double-serialize a list/dict field as a JSON string
    (e.g. `buyer_personas: '[{"name": ...}]'`), parse it back into an object so
    pydantic can validate the nested schema. Uses a raw decoder to tolerate
    markdown fences, leading prose, and trailing junk/truncation after the first
    complete JSON value. Leaves non-JSON values untouched."""
    if isinstance(value, str):
        text = value.strip()
        if text.startswith("```"):
            text = text.strip("`").strip()
            if text[:4].lower() == "json":
                text = text[4:].lstrip()
        decoder = json.JSONDecoder()
        for opener in ("[", "{"):
            idx = text.find(opener)
            while idx != -1:
                try:
                    parsed, _ = decoder.raw_decode(text[idx:])
                    if isinstance(parsed, (list, dict)):
                        return parsed
                except json.JSONDecodeError:
                    idx = text.find(opener, idx + 1)
    return value


class ProductCategory(str, Enum):
    SAAS = "saas"
    PAAS = "paas"
    IAAS = "iaas"
    MARKETPLACE = "marketplace"
    HARDWARE = "hardware"
    SERVICE = "service"
    AGENCY = "agency"
    CONSULTING = "consulting"
    OTHER = "other"


class BuyerType(str, Enum):
    B2B = "b2b"
    B2C = "b2c"
    BOTH = "both"


class Feature(BaseModel):
    name: str = Field(description="Short feature name")
    description: str = Field(description="What this feature does")
    differentiator: str = Field(description="How this specific feature differentiates from competitors")


class FollowUp(BaseModel):
    # -------
    follow_up_question: Optional[str] = Field(
        default=None,
        description="Question to ask the user for any still-missing field; None once company_name, product_name, and product_desc are all provided",
    )
    user_replies: Annotated[list[str], operator.add] = Field(
        default_factory=list,
        description="Accumulated answers to follow_up_question from the user",
    )


class Pricing(BaseModel):
    tier: str = Field(description="")
    monthly_sub: str = Field(default=None ,description="")
    yearly_sub: str = Field(default=None ,description="")
    features: list[str] = Field(default_factory=list, description="")

class PainSignal(BaseModel):
    pain: str = Field(description="The pain point or complaint competitor customers have")
    evidence: str = Field(description="What was actually said/found — quote or close paraphrase from the source")
    source_url: str | None = Field(default=None, description="URL where this pain signal was observed")


class Competitor(BaseModel):
    name: str = Field(description="Competitor company or product name")
    description: str = Field(description="What this competitor does and how they position themselves")
    website: str | None = Field(default=None, description="Competitor website URL, or null if not found")
    # These are often not present on the FIRST extraction pass (the LLM may only
    # return a name+description for a newly-mentioned competitor). They are kept
    # optional so a partial extraction never aborts the whole capture turn;
    # _merge_competitors drops empty values and fills them in over time.
    offering: str | None = Field(default=None, description="Key features/services they offer")
    positioning: str | None = Field(default=None, description="How they position themselves in the market")
    comparison: str | None = Field(default=None, description="How the user's product compares to this competitor — advantages and gaps")
    feature_flags: dict[str, bool] = Field(
        default_factory=dict,
        description="Maps each of the product's feature names to whether this competitor also offers it",
    )
    # Deep-dive intel — filled on demand in analyst mode and merged into the
    # stored record over time. All optional so baseline extraction is unaffected.
    business_model: str | None = Field(default=None, description="How the competitor makes money")
    pricing: str | None = Field(default=None, description="Pricing model and price points, if found")
    target_customers: str | None = Field(default=None, description="Who the competitor sells to (their ICP)")
    notable_customers: list[str] = Field(default_factory=list, description="Known customers of the competitor")
    strengths: list[str] = Field(default_factory=list, description="Competitor strengths found in research/reviews")
    weaknesses: list[str] = Field(default_factory=list, description="Competitor weaknesses found in research/reviews")
    whats_unique: str | None = Field(default=None, description="What is genuinely unique about the competitor")
    pain_signals: list[PainSignal] = Field(
        default_factory=list,
        description="Pain points reported by the competitor's customers, with sources",
    )
    deep_researched_at: str | None = Field(default=None, description="ISO timestamp of the last deep-dive on this competitor")


class CompetitorList(BaseModel):
    competitors: list[Competitor] = Field(description="List of competitors identified for the product")


class SnapshotFeature(BaseModel):
    """A feature as mentioned so far in the conversation. All fields optional
    because this is a PARTIAL, evolving capture — never a finalized profile."""

    name: str | None = None
    description: str | None = None
    differentiator: str | None = None


class IntakeStep(BaseModel):
    """Single combined reasoning step for the intake subgraph: extract the minimal
    product brief AND decide the next follow-up question in one model call, so each
    user-answer round costs exactly one LLM round-trip."""

    offer_name: str | None = Field(default=None, description="The official product/service name, if present in the user's reply")
    website_url: str | None = Field(default=None, description="The official product/service website url, if present in the user's reply")
    offer_description: str | None = Field(default=None, description="A neutral one-line description of what the product/service does, if derivable from the reply")
    intent: str | None = Field(default=None, description="What someone is trying to accomplish by using the product")
    problem_solved: str | None = Field(default=None, description="The core problem the product solves")
    features: list[SnapshotFeature] = Field(default_factory=list, description="Main features of the product")
    service_uniqueness: list[SnapshotFeature] = Field(default_factory=list, description="For a service: the distinctive elements that make this service different from alternatives")
    how_it_works: str | None = Field(default=None, description="How the product works end-to-end, in plain terms")
    target_geo: list[str] = Field(
        default_factory=list,
        description="Geographies the product serves, prioritised by evidence from the site/scraped content, else market research",
    )
    follow_up_question: str | None = Field(
        default=None,
        description="A short follow-up question for any still-missing field; None once company_name, product_name, and product_description are all provided",
    )


def _none_str_to_null(value):
    """LLMs often emit the literal strings 'None'/'N/A'/'null'/'nil'/'' for
    optional fields instead of a genuine null. Coerce those to None so enum or
    scalar validation doesn't reject them."""
    if isinstance(value, str):
        cleaned = value.strip()
        if cleaned.lower() in {"none", "n/a", "null", "nil", ""}:
            return None
    return value


class IndepthIntakeStep(BaseModel):
    """Single combined reasoning step for the indepth intake subgraph: extract the minimal
    product brief AND decide the next follow-up question in one model call, so each
    user-answer round costs exactly one LLM round-trip."""

    buyer_type: BuyerType | None = None
    category: ProductCategory | None = None
    intent: str | None = None
    target_audience: str | None = Field(default=None, description="...")
    problem_solved: str | None = Field(default=None, description="...")
    pricing: str | None = Field(default=None, description="...")
    target_geo: list[str] = Field(default_factory=list, description="...")
    features: list[SnapshotFeature] = Field(default_factory=list)
    how_it_works: str | None = Field(default=None, description="How the product works end-to-end, in plain terms")
    category_standard: str | None = Field(default=None, description="What the industry-standard offering in this category includes")
    strengths: list[str] = Field(default_factory=list, description="Where the product meets or beats the industry standard")
    weaknesses: list[str] = Field(default_factory=list, description="Where the product falls short of the industry standard")
    opportunities: list[str] = Field(default_factory=list, description="Market/category gaps the product could exploit")
    differentiators: list[str] = Field(default_factory=list)
    follow_up_question: str | None = Field(
        default=None,
        description="A short follow-up question for any still-missing field; None once company_name, product_name, and product_description are all provided",
    )

    @field_validator("buyer_type", "category", mode="before")
    @classmethod
    def _coerce_enum_none(cls, v):
        return _none_str_to_null(v)


class MarketExtraction(BaseModel):
    """Structured market definition + product-market fit output produced by the
    understand_market subgraph from the market interview (current web research +
    the product's own scraped material)."""

    buyer_type: BuyerType | None = Field(
        default=None, description="B2B, B2C, or both — who the buyer is"
    )
    category: ProductCategory | None = Field(
        default=None, description="The market/category the product operates in"
    )
    target_audience: str | None = Field(
        default=None, description="Who the product is for and the segments it serves"
    )
    pricing: list[Pricing] = Field(
        default_factory=list,
        description="Price tiers — from the product's own site/scraped content when present, otherwise suggested from current market rates",
    )
    pricing_source: Literal["site", "market_suggestion"] | None = Field(
        default=None,
        description="Where the pricing came from: the product's own site content or the agent's suggestion based on current market rates",
    )
    target_geo: list[str] = Field(
        default_factory=list,
        description="Geographies the product serves, prioritised by evidence from the site/scraped content, else market research",
    )
    category_conventions: str | None = Field(
        default=None,
        description="The conventions, norms, and expectations an offering in this category must meet to be credible (what 'good' looks like to buyers)",
    )
    market_demand: str | None = Field(
        default=None,
        description="Current demand level and readiness signals for the category — how much the market wants this, and evidence of that demand",
    )
    willingness_to_pay: str | None = Field(
        default=None,
        description="What buyers in the category are willing to pay / the budget norms that govern purchase decisions",
    )
    distribution_channels: list[str] = Field(
        default_factory=list,
        description="How the product is bought and sold in the category — direct sales, marketplace/platform, partnerships, retail, etc.",
    )
    adoption_barriers: list[str] = Field(
        default_factory=list,
        description="Obstacles standing between the target audience and adoption — cost, trust, switching, regulatory, awareness, etc.",
    )
    growth_outlook: Literal["growing", "stable", "declining", "unclear"] | None = Field(
        default=None,
        description="The category's current trajectory — is demand expanding, flat, shrinking, or unknown?",
    )
    market_fit: Literal["strong", "moderate", "weak", "unclear"] | None = Field(
        default=None, description="Product-market fit verdict for the product"
    )
    market_fit_reasoning: str | None = Field(
        default=None, description="Why that fit verdict was reached — evidence-based"
    )

    @field_validator("buyer_type", "category", "growth_outlook", mode="before")
    @classmethod
    def _coerce_enum_none(cls, v):
        if isinstance(v, str):
            v = _none_str_to_null(v.strip().lower())
        return v


class CompetitorArchetype(BaseModel):
    """One archetype inside an IdealCompetitorProfile.

    A CONSTRUCT, not a claim about a named company. "Regional incumbent
    undercutting on price" is a design artifact we invented to describe the
    shape of a rival; it makes no assertion that any specific firm exists. That
    is what licenses the profile to be aggressive — coverage over caution.

    It is the exact inverse of `Competitor`, which IS a set of factual claims
    about a real, verified company. Do not let the two drift together: the
    get_competitors agent must source every one of its fields or say it found
    nothing, and the archetype carries no such obligation.
    """

    label: str = Field(
        description="Short archetype name, e.g. 'Regional incumbent', 'Global entrant', 'DIY substitute'"
    )
    archetype_description: str = Field(
        description="Concretely what this kind of competitor is and how it operates"
    )
    geography_scope: Literal["local", "regional", "global", "any"] = Field(
        default="any",
        description="Where this archetype operates. 'local' incumbents defend a specific market; 'global' entrants operate locally without being headquartered there",
    )
    business_model: str | None = Field(default=None, description="How this kind of competitor makes money")
    typical_offering: str | None = Field(default=None, description="What it typically sells or does")
    pricing_model: str | None = Field(default=None, description="How it typically charges")
    customer_profile: str | None = Field(default=None, description="Whom it serves")
    likely_advantages: list[str] = Field(
        default_factory=list,
        description="Where this kind of competitor would beat the offer",
    )
    likely_weaknesses: list[str] = Field(
        default_factory=list,
        description="Where this kind of competitor would be vulnerable to the offer",
    )
    where_to_find_them: list[str] = Field(
        default_factory=list,
        description="Search surfaces, directories or query shapes where real instances of this archetype would be found — the hunting ground for the get_competitors agent",
    )
    confidence: Literal["high", "medium", "low"] = Field(
        default="low",
        description="How well the evidence supports this archetype",
    )

    @field_validator("confidence", "geography_scope", mode="before")
    @classmethod
    def _coerce_enum_none(cls, v):
        if isinstance(v, str):
            return _none_str_to_null(v.strip().lower())
        return v

    @field_validator(
        "likely_advantages", "likely_weaknesses", "where_to_find_them", mode="before"
    )
    @classmethod
    def _coerce_nested_json_fields(cls, v):
        return _coerce_json(v)


class IdealCompetitorProfile(BaseModel):
    """The competition stage's primary structured output: a description of what
    a perfect competitor to this offer looks like, derived from the stage's
    research but NOT constrained to the offer's target geographies.

    Two deliberate properties:

    1. IT NAMES NOBODY. The stage researches the landscape but emits archetypes,
       not companies. Finding real rivals is `get_competitors.py`'s job, which
       runs separately and accumulates them over time.
    2. IT IS NOT GEO-BOUND. A global player shipping into the offer's market is
       a live competitor regardless of where it is headquartered, so the profile
       deliberately spans local incumbents and international entrants.

    Everything here is a construct, so the usual "only state what the sources
    support" discipline applies to the SWOD record beside it, not to this model.
    """

    category_definition: str = Field(
        default="",
        description="What counts as a competitor in this category, and what the boundary is",
    )
    boundary_of_category: list[str] = Field(
        default_factory=list,
        description="Adjacent things that are NOT competitors — substitutes, complements, upstream suppliers",
    )
    archetypes: list[CompetitorArchetype] = Field(
        default_factory=list,
        description="4-6 archetypes spanning local incumbents, regional players and global entrants",
    )
    global_entry_signals: list[str] = Field(
        default_factory=list,
        description="What a foreign entrant would attack this market with, and why it could win",
    )
    local_defence_signals: list[str] = Field(
        default_factory=list,
        description="What local incumbents defend with, and why entrants struggle against them",
    )
    substitution_risks: list[str] = Field(
        default_factory=list,
        description="Non-company alternatives buyers may choose instead — DIY, spreadsheets, an in-house build, doing nothing",
    )
    price_anchor_range: str | None = Field(
        default=None, description="Observed price band across the landscape, when the research supports one"
    )
    channels: list[str] = Field(
        default_factory=list,
        description="How competitors in this category reach buyers — the routes a rival already owns",
    )
    confidence: Literal["high", "medium", "low"] = Field(
        default="low",
        description="How well the research supports this profile overall",
    )

    @field_validator("confidence", "category_definition", mode="before")
    @classmethod
    def _coerce_enum_none(cls, v):
        if isinstance(v, str):
            return _none_str_to_null(v.strip().lower())
        return v

    @field_validator("archetypes", mode="before")
    @classmethod
    def _coerce_nested_json_fields(cls, v):
        return _coerce_json(v)


class CompetitionExtraction(BaseModel):
    """Structured competitive output produced by the understand_competition
    subgraph: how the product stacks up against the competitive standard
    (strengths/weaknesses/opportunities/differentiators).

    It used to carry `competitors: list[Competitor]`, a named list built here.
    That moved to `IdealCompetitorProfile` (as archetypes) and to the standalone
    get_competitors agent (as real, verified rows) — see the module note in
    understand_competition.py. The SWOD fields survived the move unchanged
    because they were always offer-vs-category, never offer-vs-named-rival.
    """

    strengths: list[str] = Field(
        default_factory=list,
        description="Where the product meets or beats the industry standard",
    )
    weaknesses: list[str] = Field(
        default_factory=list,
        description="Where the product falls short of the industry standard",
    )
    opportunities: list[str] = Field(
        default_factory=list,
        description="Market/category gaps the product could exploit",
    )
    differentiators: list[str] = Field(default_factory=list)


class CompetitionRecord(BaseModel):
    """Wrapper for the competition extractor's single classification pass.

    The extractor reads one evidence set and emits two different kinds of thing
    from it: the archetype profile (a construct, refined by the next node) and
    the offer-vs-standard SWOD (a judgment, shipped as-is). They are bundled
    here purely so one `invoke_structured_with_fallback` call can return both;
    the node unpacks them into their own state channels immediately.
    """

    profile: IdealCompetitorProfile = Field(
        default_factory=IdealCompetitorProfile,
        description="The draft Ideal Competitor Profile, refined by the following node",
    )
    swod: CompetitionExtraction = Field(
        default_factory=CompetitionExtraction,
        description="Where the offer meets or beats the competitive standard, and where it does not",
    )

    @field_validator("profile", "swod", mode="before")
    @classmethod
    def _coerce_nested_models(cls, v):
        # A model asked for a nested object sometimes returns the inner object
        # as a JSON string. Unwrap it rather than failing the whole record.
        if isinstance(v, str):
            try:
                return json.loads(v)
            except (ValueError, TypeError):
                return v
        return v


class OfferDataSnapshot(BaseModel):
    """Running, partial understanding of the product gathered progressively
    during the conversation. Everything is optional: unknown fields may be null
    or empty. Merged into state.product_data_snapshot on every capture turn
    (known values are never clobbered by thinner later captures)."""
    # Offer (Product/Service)
    company_name: str | None = None
    offer_name: str | None = None
    offer_description: str | None = None
    website_url: str | None = None
    intent: str | None = None
    target_geo: list[str] = Field(default_factory=list)
    problem_solved: str | None = Field(default=None, description="...")
    features: list[SnapshotFeature] = Field(default_factory=list)
    service_uniqueness: list[SnapshotFeature] = Field(default_factory=list, description="For a service: the distinctive elements that make this service different from alternatives")
    how_it_works: str | None = Field(default=None, description="How the product works end-to-end, in plain terms")


class ProductFindings(BaseModel):
    """Domain research notes + concise product-domain understanding, from the product specialist.

    Deliberately notes rather than the finished report section. A specialist that
    writes its own section in isolation cannot know what the market and
    competition specialists go on to find, so independently-written sections
    routinely restate each other or quietly contradict each other. The prose is
    composed once at the end by a single writer that can see all three sets of
    notes at once.
    """

    findings: str = Field(description="Detailed markdown research notes grounding the product in its domain/category — the evidence, terminology, named systems, limits and numbers the report section has to be built from")
    product_domain_understanding: str = Field(
        description="Brief understanding of how the product fits into its domain/category; target 40 words, maximum 50"
    )


class MarketFindings(BaseModel):
    """Market research notes + concise product-market-fit understanding, from the market specialist."""

    findings: str = Field(description="Detailed markdown research notes defining the product's market and its product-market fit — the segment sizing, demand evidence, buyer types and current conditions the report section has to be built from")
    product_market_fit_understanding: str = Field(
        description="Brief understanding of how well the product fits its market; target 40 words, maximum 50"
    )


class CompetitionFindings(BaseModel):
    """Competitive-landscape research notes + concise positioning understanding, from the competition specialist."""

    findings: str = Field(description="Detailed markdown research notes laying out the product's competitive landscape and how it stacks up — the named competitors, their positioning, the comparison and the honest gaps the report section has to be built from")
    competitive_positioning_understanding: str = Field(
        description="Brief understanding of how the product is positioned vs. its real competitors; target 40 words, maximum 50"
    )


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


class OfferSections(BaseModel):
    """The finished report sections, composed in one pass once every specialist has reported.

    Writing all three together is the point: the market section can reflect what
    the competition specialist found, and the domain section can frame the
    category in the terms the market evidence actually supports.
    """

    domain_section: str = Field(description="Markdown report section grounding the product in its domain/category")
    market_section: str = Field(description="Markdown report section defining the product's market and product-market fit")
    competition_section: str = Field(description="Markdown report section laying out the product's competitive landscape and how it stacks up")


class OfferGtmSection(BaseModel):
    """Report section and concise go-to-market understanding produced by the account-discovery subgraph."""

    section: str = Field(description="Markdown report section laying out the ICP and target accounts found for outreach")
    go_to_market_understanding: str = Field(
        description="Brief understanding of the go-to-market narrative — who to target, why now, and the opening angle; target 40 words, maximum 50"
    )


class DomainSpecialist(BaseModel):
    domain: Literal["product", "service", "market", "competition", "gtm"]
    name: str = Field(description="Specialist's name")
    role_title: str = Field(description="Specialist's role/title")
    background: str = Field(description=" About 2-3 sentences of background on the specialist's expertise")
    focus: str = Field(description="What the specialist is focused on in this session")
    # Hardening fields — optional so baseline construction is unaffected. Set by
    # the create-specialists subgraph and surfaced through `persona` so every
    # downstream interview inherits the specialist's geo-anchored identity.
    region: str | None = Field(default=None, description="Market/geography the specialist's lens is anchored to")
    language: str | None = Field(default=None, description="Language(s)/cultural idiom the specialist works in")
    operating_context: str | None = Field(default=None, description="Fictional track record — markets/contexts they've operated in")
    distinct_lens: str | None = Field(default=None, description="The specific angle/prism they bring to this session")

    @property
    def persona(self) -> str:
        return (
            f"Name: {self.name}\n"
            f"Role: {self.role_title}\n"
            f"Background: {self.background}\n"
            f"Focus: {self.focus}\n"
            f"Region: {self.region or '—'}\n"
            f"Language: {self.language or '—'}\n"
            f"Operating context: {self.operating_context or '—'}\n"
            f"Lens: {self.distinct_lens or '—'}\n"
        )

class SpecialistTeam(BaseModel):
    product_or_service_specialist: DomainSpecialist = Field(description="Domain specialist for the offer itself (domain: \"product\" or \"service\")")
    market_specialist: DomainSpecialist = Field(description="Market & customer segments specialist (domain: \"market\")")
    competition_specialist: DomainSpecialist = Field(description="Competitive landscape specialist (domain: \"competition\")")
    gtm_specialist: DomainSpecialist = Field(description="Go-to-market strategy specialist (domain: \"gtm\")")

class InterviewState(MessagesState):
    max_num_turns: int # Number turns of conversation
    context: Annotated[list, operator.add] # Source docs
    specialist: DomainSpecialist # Analyst asking questions
    interview: str # Interview transcript
    offer_snapshot: OfferDataSnapshot
    offer_type: Optional[Literal["product", "service"]] = Field(default=None, description="Offer kind captured by the session (product or service), used to adapt the interview prompts")
    sections: list # Final key we duplicate in outer state for Send() API
    section_word_count: int # Per-section word limit (auto-distributed)
    product_domain_understanding: Optional[str] = Field(default=None, description="")
    product_market_fit_understanding: Optional[str] = Field(default=None, description="")
    competitive_positioning_understanding: Optional[str] = Field(default=None, description="")
    scraped_content: Optional[str] = Field(default=None, description="Raw content gathered from the product's own URL/document during discovery, seeded into the interview context so the expert and section writer can ground answers on the product itself")
    product_findings: Optional[str] = Field(default=None, description="Domain research notes from the product specialist, composed into the report's domain section at the end of the run")
    market_findings: Optional[str] = Field(default=None, description="Market research notes from the market specialist, composed into the report's market section at the end of the run")
    competition_findings: Optional[str] = Field(default=None, description="Competitive-landscape research notes from the competition specialist, composed into the report's competition section at the end of the run")
    market_data: Optional[MarketExtraction] = Field(default=None, description="Structured market definition + product-market fit produced by the understand_market interview")
    competition_data: Optional[CompetitionExtraction] = Field(default=None, description="Structured offer-vs-standard SWOD produced by the understand_competition interview. The named competitor list it used to carry now lives in ideal_competitor_profile (as archetypes) and, for real verified rivals, in the standalone get_competitors agent")
    product_complete: Optional[bool] = Field(default=None, description="Set True by the understand-product subgraph's terminal node as it completes")
    market_complete: Optional[bool] = Field(default=None, description="Set True by the understand-market subgraph's terminal node as it completes")
    competition_complete: Optional[bool] = Field(default=None, description="Set True by the understand-competition subgraph's terminal node as it completes")

class SearchQuery(BaseModel):
    search_query: str = Field(None, description="Search query about the technology/domain the product uses — NEVER include the product's or brand's name")
    broader_query: str | None = Field(default=None, description="A broader, simpler fallback of the same technology/domain query, used when the primary query returns no results")


class CompetitionSearchQuery(BaseModel):
    direct_query: str = Field(
        default=None,
        description="Search query hunting for the product's DIRECT competitors — MAY include the product/brand name (e.g. '<product> competitors', 'alternatives to <product>')",
    )
    landscape_query: str = Field(
        default=None,
        description="Search query painting the competitive LANDSCAPE for the category in the target geographies (e.g. 'top <category> platforms in <geo>') — NEVER include the product's or brand's name",
    )
    broader_query: str | None = Field(
        default=None,
        description="A broader, simpler fallback of the same market/category query, used when the direct/landscape queries return nothing",
    )


# --- Account discovery (GTM phase) ---

# Signal types that qualify an account/channel/event for outreach during account discovery.
TRIGGER_SIGNAL_TYPES = [
    "hiring_post",
    "competitor_review_mention",
    "payment_integration",
    "social_growth_spike",
    "community_growth_spike",
    "product_listing",
    "funding_round",
    "event_upcoming",
]


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
        return _coerce_json(v)


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
        return _coerce_json(v)


class ContactRecord(BaseModel):
    """A person to reach out to at a target account. Never fabricate contact
    details — only fill in what appears in the sources."""

    name: str | None = Field(default=None, description="Full name, if found")
    title: str | None = Field(default=None, description="Job title, if found")
    linkedin: str | None = Field(default=None, description="LinkedIn URL, if found")
    email: str | None = Field(default=None, description="Email address, if found")


class SourceRecord(BaseModel):
    title: str = Field(description="Title of the source")
    url: str = Field(description="URL of the source")
    snippet: str | None = Field(default=None, description="Relevant snippet from the source")


class TriggerEvent(BaseModel):
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
    ] = Field(description="Which trigger signal type this event matches")
    source: str = Field(description="URL/where the trigger was observed")


class AccountRecord(BaseModel):
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
        return _coerce_json(v)

    @field_validator("socials", mode="before")
    @classmethod
    def _coerce_socials_field(cls, v):
        if v is None:
            return {}
        parsed = _coerce_json(v)
        return parsed if isinstance(parsed, dict) else {}


class AccountList(BaseModel):
    accounts: list[AccountRecord] = Field(
        description="4-8 target accounts found for outreach, each with a current trigger event",
    )


class AccountDiscoveryQueries(BaseModel):
    queries: list[str] = Field(
        default_factory=list,
        description="4-8 web queries to surface target accounts: ICP keyword × geo × industry, competitor-sentiment/pain, and hiring/trigger-signal searches",
    )

class AccountDiscoveryState(TypedDict):
    """State for the account-discovery subgraph (GTM phase): given the ICP already
    determined by the determine_icp subgraph, it searches for target accounts /
    consumer-reach channels + events, extracts them, validates, and writes the
    GTM section."""

    specialist: DomainSpecialist
    offer_snapshot: Optional[OfferDataSnapshot]
    offer_type: Optional[Literal["product", "service"]] = Field(default=None, description="Offer kind captured by the session (product or service), used to adapt the pipeline prompts")
    scraped_content: Optional[str]
    market_data: Optional[MarketExtraction]
    competition_data: Optional[CompetitionExtraction]
    icp: Optional[ICP]
    context: Annotated[list, operator.add]
    accounts: Optional[AccountList]
    sections: Annotated[list, operator.add]
    section_word_count: int
    go_to_market_understanding: Optional[str] = Field(default=None, description="")
    gtm_complete: Optional[bool] = Field(default=None, description="Set True by the account-discovery subgraph's terminal node as it completes")


class DetermineIcpState(TypedDict):
    """State for the determine-ICP subgraph (GTM phase): the GTM specialist
    synthesises a thorough, buyer-type-aware Ideal Customer Profile from the
    market + competition understanding — personas + reach channels for consumer
    offers, firmographics for B2B. The resulting ICP seeds account discovery."""

    specialist: DomainSpecialist
    offer_snapshot: Optional[OfferDataSnapshot]
    offer_type: Optional[Literal["product", "service"]] = Field(default=None, description="Offer kind captured by the session (product or service), used to adapt the pipeline prompts")
    scraped_content: Optional[str]
    market_data: Optional[MarketExtraction]
    competition_data: Optional[CompetitionExtraction]
    icp: Optional[ICP]
    icp_complete: Optional[bool] = Field(default=None, description="Set True by the determine-ICP subgraph's terminal node as it completes")

# --- Conversational routing ---

class RouteDecision(BaseModel):
    specialist: Literal["product", "market", "competition", "gtm"]
    reasoning: str = Field(description="Why the agent decided to route to this specialist")

class SpecialistReply(BaseModel):
    response: str = Field(description="The specialist's reply to the user")

# --- Session state ---


class OfferSessionState(TypedDict):
    """State for the conversational product & competition analyst session."""
    offer: Literal["product", "service"] | None = Field(default=None)
    offer_type_lean: Optional[Literal["product", "service"]] = Field(default=None, description="The classifier's weak lean when uncertain — surfaced to the user by ask_for_offer_clarity")
    offer_type_reasoning: Optional[str] = Field(default=None, description="Evidence behind the classifier's lean — shown with the clarification question")
    specialist_team: SpecialistTeam
    offer_snapshot: OfferDataSnapshot
    messages: Annotated[list, add_messages]
    follow_up: FollowUp

    # --- phase compplete ---

    specilist_generation_complete: bool = Field(default=False, description="")
    product_complete: bool = Field(default=False, description="")
    competition_complete: bool = Field(default=False, description="")
    market_complete: bool = Field(default=False, description="")
    icp_complete: bool = Field(default=False, description="")
    gtm_complete: bool = Field(default=False, description="")

    # --- Interview Sections ---

    sections: Annotated[list, operator.add] # Send() API key
    # Per-specialist research notes and transcripts. The subgraph output the
    # final section writer reads; kept in session state because the writer runs
    # as a top-level node, after all three interviews, with the subgraph state
    # already out of scope.
    product_findings: Optional[str] = Field(default=None, description="Domain research notes from the product specialist")
    market_findings: Optional[str] = Field(default=None, description="Market research notes from the market specialist")
    competition_findings: Optional[str] = Field(default=None, description="Competitive-landscape research notes from the competition specialist")
    product_transcript: Optional[str] = Field(default=None, description="Full transcript of the product-domain interview")
    market_transcript: Optional[str] = Field(default=None, description="Full transcript of the market interview")
    competition_transcript: Optional[str] = Field(default=None, description="Full transcript of the competition interview")
    product_domain_understanding: Optional[str] = Field(default=None, description="")
    product_market_fit_understanding: Optional[str] = Field(default=None, description="")
    competitive_positioning_understanding: Optional[str] = Field(default=None, description="")
    go_to_market_understanding: Optional[str] = Field(default=None, description="")
    market_data: Optional[MarketExtraction] = Field(default=None, description="Structured market definition + product-market fit produced by the understand_market interview")
    competition_data: Optional[CompetitionExtraction] = Field(default=None, description="Structured offer-vs-standard SWOD produced by the understand_competition interview. The named competitor list it used to carry now lives in ideal_competitor_profile (as archetypes) and, for real verified rivals, in the standalone get_competitors agent")
    icp: Optional[ICP] = Field(default=None, description="Ideal Customer Profile produced by the account-discovery (GTM) subgraph")
    accounts: Optional[AccountList] = Field(default=None, description="Target accounts + contacts found by the account-discovery (GTM) subgraph")

    # --- Product discovery phase ---
    
    scraped_content: Optional[str] = Field(default=None, description="Raw content gathered from the user's URL/document, kept for re-draft rounds")
    confirmed: bool = Field(default=False, description="True once the user has approved the current product_description")
    name_mismatch: bool = Field(default=False, description="True when the provided product_name was not found in the scraped content and the user should be told")
    product_candidates: list[str] = Field(default_factory=list, description="Distinct product/brand names found in the scraped content, offered to the user when the provided name isn't found")
    scrape_failed: bool = Field(default=False, description="True once the user has been told that their URL could not be fetched, so re-entry skips re-scraping")


# --- Node-led offer research (pipelines) -----------------------------------
#
# Models for the node-led research pipeline, which replaces the
# specialist-interviews-an-expert loop with explicit intelligence operations:
# analyze -> identify gaps -> plan -> research -> evaluate -> synthesize.
#
# They live HERE, not in pipelines/understand_product.py, because
# backend/app/agents_runtime.py:38-43 derives the LangGraph checkpoint serde
# allowlist by walking this module's members and filtering on
# `__module__ == "agents.states"`. A model defined in the pipeline module would
# be rejected on every checkpoint read ("Blocked deserialization") -- the same
# failure the comment there records for BuyerType/ProductCategory.
#
# Naming is deliberately neutral ("offer", never "product"): this pipeline runs
# for services and products alike, and the prompts swap `{offer_noun}` so every
# node reads correctly for both.


class OfferAnalysis(BaseModel):
    """The specialist's initial mental model of the offer, built from the
    offer's own material BEFORE any web research.

    This is the structural replacement for the old interview's first question.
    The old loop asked "what should I ask the expert?"; this asks "what do I
    currently understand, and what do I not know?" — which is the question that
    actually drives what to research next.
    """

    problem: str | None = Field(default=None, description="The problem the offer addresses, as the offer's own material states it")
    solution: str | None = Field(default=None, description="How the offer solves it, in neutral terms")
    target_users: list[str] = Field(default_factory=list, description="Who the offer is for, as stated in its own material")
    core_features: list[str] = Field(default_factory=list, description="The offer's main features / service elements, as stated in its own material")
    technology: list[str] = Field(default_factory=list, description="Named technologies, mechanisms or approaches the offer is built on or uses")
    business_model: str | None = Field(default=None, description="How the offer appears to make money, if its own material states it")
    target_markets: list[str] = Field(default_factory=list, description="Geographies the offer serves, as stated in its own material")
    domain: str | None = Field(default=None, description="The domain/category space the offer sits in")
    category: str | None = Field(default=None, description="The closest category name — how this domain space is conventionally labelled")
    known_claims: list[str] = Field(
        default_factory=list,
        description="Concrete checkable claims the offer's own material makes — mechanisms, numbers, named systems, dates, limits",
    )
    unknowns: list[str] = Field(
        default_factory=list,
        description="What the offer's own material does NOT establish and a domain expert would be needed for",
    )

    @field_validator(
        "target_users", "core_features", "technology", "target_markets",
        "known_claims", "unknowns", mode="before",
    )
    @classmethod
    def _coerce_list_fields(cls, v):
        if v is None:
            return []
        return _coerce_json(v)


class KnowledgeGap(BaseModel):
    """One thing the analysis cannot answer and research could close."""

    area: str = Field(description="The area of understanding this gap sits in — e.g. 'technology', 'category standards', 'deployment in <geo>'")
    question: str = Field(description="The specific question that would close this gap")
    why_it_matters: str = Field(description="Why answering it changes the picture of the offer — what a reader could not judge without it")
    priority: int = Field(default=3, description="1 = highest priority, 3 = lowest. Drives which gaps become research tasks first")

    @field_validator("area", "question", mode="before")
    @classmethod
    def _coerce_none_str(cls, v):
        return _none_str_to_null(v)


class GapList(BaseModel):
    gaps: list[KnowledgeGap] = Field(default_factory=list, description="The identified knowledge gaps, most important first")

    @field_validator("gaps", mode="before")
    @classmethod
    def _coerce_gaps(cls, v):
        if v is None:
            return []
        return _coerce_json(v)


class ResearchTask(BaseModel):
    """A unit of planned research: one objective, backed by search queries.

    A task is the smallest thing the pipeline can execute and evaluate
    independently, which is what makes the sufficiency loop meaningful — the
    evaluator can say "this task came back empty" without that contaminating the
    other two.
    """

    id: str = Field(description="Short stable identifier for this task, e.g. 'standards' or 'deployment'")
    area: str = Field(description="The knowledge-gap area this task closes")
    objective: str = Field(description="What this task must establish — a research goal, not a search string")
    queries: list[str] = Field(
        default_factory=list,
        description="2-3 independent web-search queries. NEVER include the offer's or brand's name — research the DOMAIN/CATEGORY the offer sits in, so the sources describe the category rather than the offer",
    )

    @field_validator("queries", mode="before")
    @classmethod
    def _coerce_queries(cls, v):
        if v is None:
            return []
        return _coerce_json(v)


class TaskList(BaseModel):
    tasks: list[ResearchTask] = Field(default_factory=list, description="The research tasks to execute this round")

    @field_validator("tasks", mode="before")
    @classmethod
    def _coerce_tasks(cls, v):
        if v is None:
            return []
        return _coerce_json(v)


class EvidenceClaim(BaseModel):
    """One claim extracted from the sources, traceable to a single source.

    Deliberately finer-grained than a pile of condensed documents: the point of
    the research step is to lose the boilerplate, and a claim the synthesizer
    can cite is more useful downstream than an article it has to re-read.
    """

    claim: str = Field(description="The specific, checkable statement the source supports")
    evidence: str = Field(description="The supporting detail — a figure, mechanism, name or quote from the source")
    source: str = Field(description="Full URL of the source this claim came from")
    relevance: float = Field(default=0.5, description="How directly this claim addresses the task's objective, 0-1")


class EvidenceList(BaseModel):
    """All claims extracted for one research task, across all of that task's sources."""

    task_id: str = Field(default="", description="Which research task these claims answer")
    claims: list[EvidenceClaim] = Field(
        default_factory=list,
        description="Claims extracted from this task's sources. Empty is a legitimate and meaningful answer: it means the research found nothing supporting the objective",
    )
    contradictions: list[str] = Field(
        default_factory=list,
        description="Places where the sources disagree with each other, or with the offer's own material",
    )

    @field_validator("claims", "contradictions", mode="before")
    @classmethod
    def _coerce_claim_lists(cls, v):
        if v is None:
            return []
        return _coerce_json(v)


class EvidenceEvaluation(BaseModel):
    """The sufficiency verdict for one round of research.

    `sufficient` is the loop's routing signal, so it is deliberately separate
    from `remaining_gaps`: a round can be sufficient overall while still
    recording specific things nobody answered.
    """

    sufficient: bool = Field(default=False, description="True when this round's evidence is enough to write the offer's domain grounding")
    confidence: Literal["high", "moderate", "low"] = Field(default="low", description="How much the evidence supports that verdict")
    rationale: str | None = Field(default=None, description="Why that verdict — which tasks were answered and which were not")
    remaining_gaps: list[KnowledgeGap] = Field(
        default_factory=list,
        description="Specific gaps this round did NOT close, in the same shape as the original gaps so the planner can re-select from them",
    )

    @field_validator("remaining_gaps", mode="before")
    @classmethod
    def _coerce_remaining(cls, v):
        if v is None:
            return []
        return _coerce_json(v)


class EvaluationList(BaseModel):
    evaluations: list[EvidenceEvaluation] = Field(default_factory=list, description="One evaluation per research round so far")

    @field_validator("evaluations", mode="before")
    @classmethod
    def _coerce_evaluations(cls, v):
        if v is None:
            return []
        return _coerce_json(v)


class OfferUnderstanding(BaseModel):
    """The research pipeline's synthesis of the offer, before it becomes prose.

    Sits between the evidence and `ProductFindings`. Keeping the two apart means
    the structured understanding can be inspected and reused (the GTM stage
    reads it) without re-parsing markdown, and the findings writer stays a pure
    text-shaping step.
    """

    offer_understanding: str = Field(description="What the offer IS and how it works, end to end")
    domain_understanding: str = Field(description="How the offer fits its domain/category space — the framing the report section leads with")
    technology_understanding: str = Field(description="The technology/architecture the offer uses and how it works mechanically")
    differentiation: str = Field(description="What is novel, interesting or surprising about the offer relative to its domain")
    evidence: list[str] = Field(default_factory=list, description="The concrete evidence the synthesis rests on, each traceable to a source")
    uncertainties: list[str] = Field(default_factory=list, description="Claims that remain thin, contested or unsupported — these must stay visible in the notes")
    open_questions: list[str] = Field(default_factory=list, description="What this research could not answer at all")

    @field_validator(
        "evidence", "uncertainties", "open_questions", mode="before",
    )
    @classmethod
    def _coerce_string_lists(cls, v):
        if v is None:
            return []
        return _coerce_json(v)


class TaskResearchBundle(BaseModel):
    """What one research task actually retrieved.

    Held per task rather than as a single undifferentiated pile of documents,
    because `extract_evidence` evaluates one objective at a time: a task that
    came back empty is a real, reportable finding about that objective, and it
    would be invisible if its notes were merged with a task that succeeded.

    This is also why it replaces the old `context: list` accumulator rather than
    sitting alongside it — one copy of the research, associated with the task
    that produced it.
    """

    task_id: str = Field(default="", description="Which research task this bundle belongs to")
    area: str = Field(default="", description="The knowledge-gap area the task closed")
    objective: str = Field(default="", description="What the task set out to establish")
    round: int = Field(default=0, description="Which research round produced this bundle. Lets `extract_evidence` pick out the current round's bundles without relying on list position")
    queries: list[str] = Field(default_factory=list, description="The queries actually issued for this task")
    notes: str = Field(default="", description="The condensed source notes, in the <Document> shape the prompts already parse. Empty when the search failed")
    sources: list[str] = Field(default_factory=list, description="URLs actually retrieved for this task")
    search_failed: bool = Field(default=False, description="True when every query returned nothing usable")

    @field_validator("queries", "sources", mode="before")
    @classmethod
    def _coerce_bundle_lists(cls, v):
        if v is None:
            return []
        return _coerce_json(v)


class OfferResearchState(TypedDict):
    """State for the node-led offer-research subgraph.

    A deliberate replacement for InterviewState, not an extension of it. The
    old state was MessagesState-based because the interview WAS the
    conversation; here there is no conversation at all, so `messages` is gone
    and intelligence accumulates as structured analysis, gaps, tasks and
    evidence instead.

    That absence is load-bearing upstream: gtmx_agent.py runs this subgraph
    concurrently with understand_market, and the comment at gtmx_agent.py:364
    argues the two are safe to overlap because they write disjoint keys. With
    no `messages` channel, they share nothing whatsoever, so the invariant stops
    being an argument and becomes structural.
    """

    # --- Inputs (same shape the parent passes to the interview subgraphs) ---
    specialist: DomainSpecialist
    offer_snapshot: OfferDataSnapshot
    offer_type: Optional[Literal["product", "service"]] = None
    scraped_content: Optional[str] = None
    section_word_count: int = 500

    # --- Accumulated intelligence ---
    context: Annotated[list, operator.add]  # seeded with the offer's own material only
    analysis: Optional[OfferAnalysis] = None
    gaps: Optional[GapList] = None
    tasks: Optional[TaskList] = None
    task_research: Annotated[list, operator.add]  # one TaskResearchBundle per task, per round
    evidence: Annotated[list, operator.add]  # one EvidenceList per task, per round
    evaluations: Annotated[list, operator.add]  # one EvidenceEvaluation per round
    understanding: Optional[OfferUnderstanding] = None
    research_log: str = ""

    # --- Loop bounds ---
    # An LLM sufficiency verdict is not a bound. Without these, a model that
    # never says "sufficient" re-plans until LangGraph's recursion limit stops
    # the run, which surfaces as an opaque GraphRecursionError rather than a
    # report.
    round: int = 0
    max_rounds: int = 2

    # --- Outbound contract ---
    # Names are preserved verbatim: gtmx_agent.run_interview and
    # backend/app/api/v1/endpoints/discovery.py both read these three keys, and
    # write_sections reads the notes. Renaming them is a coordinated change
    # across all three files, not something to smuggle into a rewrite.
    product_findings: Optional[str] = None
    product_domain_understanding: Optional[str] = None
    product_complete: Optional[bool] = None

