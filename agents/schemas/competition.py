"""Competition-stage extraction, the ideal competitor profile, and the standalone competitor hunt."""

from typing import Literal, Optional

from pydantic import Field, field_validator

from agents.schemas.coercion import coerce_json, LenientModel, none_str_to_null


class PainSignal(LenientModel):
    pain: str = Field(description="The pain point or complaint competitor customers have")
    evidence: str = Field(description="What was actually said/found — quote or close paraphrase from the source")
    source_url: str | None = Field(default=None, description="URL where this pain signal was observed")


class Competitor(LenientModel):
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


class ArchetypeSketch(LenientModel):
    """The identity of one archetype: what kind of company it is. Drafted and
    reviewed for the whole profile at once, before any details are written,
    because overlap, gaps and a named real company are structural problems."""

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

    @field_validator("geography_scope", mode="before")
    @classmethod
    def _coerce_scope(cls, v):
        if isinstance(v, str):
            return none_str_to_null(v.strip().lower())
        return v


class ArchetypeDetail(LenientModel):
    """The working detail of one archetype -- written per archetype, in
    parallel, once the set of archetypes is settled."""

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

    @field_validator("confidence", mode="before")
    @classmethod
    def _coerce_confidence(cls, v):
        if isinstance(v, str):
            return none_str_to_null(v.strip().lower())
        return v

    @field_validator(
        "likely_advantages", "likely_weaknesses", "where_to_find_them", mode="before"
    )
    @classmethod
    def _coerce_nested_json_fields(cls, v):
        return coerce_json(v)


class CompetitorArchetype(ArchetypeDetail, ArchetypeSketch):
    """One archetype inside an IdealCompetitorProfile: its identity (sketch)
    plus its working detail.

    A CONSTRUCT, not a claim about a named company. "Regional incumbent
    undercutting on price" is a design artifact we invented to describe the
    shape of a rival; it makes no assertion that any specific firm exists. That
    is what licenses the profile to be aggressive — coverage over caution.

    It is the exact inverse of `Competitor`, which IS a set of factual claims
    about a real, verified company. Do not let the two drift together: the
    get_competitors agent must source every one of its fields or say it found
    nothing, and the archetype carries no such obligation.
    """


class _ProfileFields(LenientModel):
    """Profile-level fields shared by the skeleton and the finished profile."""

    category_definition: str = Field(
        default="",
        description="What counts as a competitor in this category, and what the boundary is",
    )
    boundary_of_category: list[str] = Field(
        default_factory=list,
        description="Adjacent things that are NOT competitors — substitutes, complements, upstream suppliers",
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

    @field_validator("confidence", mode="before")
    @classmethod
    def _coerce_confidence(cls, v):
        if isinstance(v, str):
            return none_str_to_null(v.strip().lower())
        return v

    @field_validator("category_definition", mode="before")
    @classmethod
    def _coerce_definition(cls, v):
        # Only null-like strings are coerced; the definition itself keeps its case.
        return (none_str_to_null(v.strip()) or "") if isinstance(v, str) else v


class ProfileSkeleton(_ProfileFields):
    """The profile with archetypes as sketches only: small enough to draft and
    review quickly before the details are written in parallel."""

    archetypes: list[ArchetypeSketch] = Field(
        default_factory=list,
        description="4-6 archetypes spanning local incumbents, regional players and global entrants",
    )

    @field_validator("archetypes", mode="before")
    @classmethod
    def _coerce_nested_json_fields(cls, v):
        return coerce_json(v)


class IdealCompetitorProfile(_ProfileFields):
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

    archetypes: list[CompetitorArchetype] = Field(
        default_factory=list,
        description="4-6 archetypes spanning local incumbents, regional players and global entrants",
    )

    @field_validator("archetypes", mode="before")
    @classmethod
    def _coerce_nested_json_fields(cls, v):
        return coerce_json(v)


class CompetitionExtraction(LenientModel):
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




class CompetitionFindings(LenientModel):
    """Competitive-landscape research notes + concise positioning understanding, from the competition specialist."""

    findings: str = Field(description="Detailed markdown research notes laying out the product's competitive landscape and how it stacks up — the named competitors, their positioning, the comparison and the honest gaps the report section has to be built from")
    competitive_positioning_understanding: str = Field(
        description="Brief understanding of how the product is positioned vs. its real competitors; target 40 words, maximum 50"
    )


class CompetitorHuntTask(LenientModel):
	"""One search assignment: hunt for firms matching one archetype."""

	archetype_label: str = Field(description="The archetype from the ideal profile being hunted")
	geography_scope: str = Field(
		description="local | regional | global | any -- carried through so the "
		"verdict survives to the profile"
	)
	objective: str = Field(description="What this task is trying to find")
	queries: list[str] = Field(
		default_factory=list,
		description="Search queries. Must never name the offer itself -- a query "
		"like 'alternatives to us' returns listicles, not the rivals",
	)


class CompetitorHuntPlan(LenientModel):
	tasks: list[CompetitorHuntTask] = Field(default_factory=list)


class CandidateFinding(LenientModel):
	"""A firm the hunt turned up, with the evidence that it exists."""

	name: str = Field(description="The company's own name as it brands itself")
	website: Optional[str] = Field(
		default=None,
		description="The company's public website, as it appeared in a retrieved "
		"source. NULL MEANS DROP: the brief tracks only firms with a findable "
		"public site, and a candidate whose site could not be read is a "
		"candidate we cannot verify.",
	)
	evidence_urls: list[str] = Field(
		default_factory=list,
		description="Retrieved pages that named this company and showed its site. "
		"Empty is permitted -- a site read off a directory listing still counts -- "
		"but a name with no traceable origin is a hallucination risk and the "
		"planner prompt says so.",
	)
	why_it_might_match: Optional[str] = Field(
		default=None,
		description="One line on why this firm looks like the archetype. A guess "
		"flagged as a guess, so the screening stage can drop it if it cannot hold up",
	)
	geography_hint: Optional[str] = Field(
		default=None, description="Where the source suggests the firm is based"
	)


class CompetitorHuntBundle(LenientModel):
	"""What one hunt task found, with the sources behind it."""

	archetype_label: str = ""
	geography_scope: str = "any"
	candidates: list[CandidateFinding] = Field(default_factory=list)
	search_failed: bool = Field(default=False)
	queries: list[str] = Field(default_factory=list)
	sources: list[dict] = Field(default_factory=list)


class SourcedFinding(LenientModel):
	"""One claim about a real company, with the proof attached.

	`evidence` is required, not optional. A weakness or a complaint attributed to
	a named business is a factual assertion about an identifiable company, and an
	unsourced one is simply a fabrication with extra steps.
	"""

	text: str = Field(description="The claim, in one line")
	evidence: str = Field(
		description="A quote or close paraphrase from a retrieved source showing "
		"the claim is real. Never a paraphrase of a paraphrase",
	)
	source_url: Optional[str] = Field(
		default=None, description="The page the evidence came from"
	)


class CompetitorSocial(LenientModel):
	kind: Literal["website", "instagram", "tiktok", "x", "linkedin", "github", "other"] = Field(
		description="The network. The brief asks for Instagram, TikTok, X and "
		"LinkedIn; website and github are included because they turn up alongside "
		"them and a competitor's repo is often its most honest page",
	)
	value: str = Field(description="The full profile URL, or the handle if that is all that was found")
	confidence: Literal["high", "medium", "low"] = Field(
		default="medium",
		description="How sure we are the link belongs to THIS company. A handle "
		"found next to the company name is medium; one read off the company's own "
		"site is high",
	)


class CompetitorProfile(LenientModel):
	"""A verified real company, profiled with per-field provenance.

	The inverse of `CompetitorArchetype`. Every field is a claim about a real
	firm, so the model carries the evidence for each one and names the fields
	research could not establish.
	"""

	name: str
	website: str = Field(description="Required. A firm with no public site is not tracked")
	relevance: Optional[Literal["direct", "indirect", "not_a_competitor"]] = Field(
		default=None,
		description="direct: sells a substitute to the same buyer. indirect: solves "
		"the same problem a different way. not_a_competitor: a customer, partner, "
		"investor, media outlet, or unrelated firm that merely appeared in the search",
	)
	relevance_reason: Optional[str] = Field(default=None, description="One sentence on why")
	description: Optional[str] = Field(default=None, description="What the company does, in its own framing")
	offering: Optional[str] = Field(default=None, description="The product or service actually sold")
	positioning: Optional[str] = Field(default=None, description="How it claims to differ")
	business_model: Optional[str] = Field(default=None)
	pricing: Optional[str] = Field(
		default=None,
		description="Published pricing or its absence. 'No public pricing' is a "
		"finding; leave null only if pricing was not researched at all",
	)

	target_customers: Optional[str] = Field(default=None, description="Whom they serve")
	headquarters: Optional[str] = Field(default=None)
	geography_scope: Optional[str] = Field(
		default=None,
		description="local | regional | global | any -- the local-vs-foreign "
		"verdict, carried from the archetype that found them and corrected "
		"against their own site",
	)

	comparison: Optional[str] = Field(
		default=None,
		description="How the user's own offer compares to this firm, on the axes "
		"the competitor profile establishes",
	)
	matched_archetype: Optional[str] = Field(
		default=None, description="Which archetype of the ideal profile this firm turned out to be"
	)

	strengths: list[SourcedFinding] = Field(default_factory=list)
	weaknesses: list[SourcedFinding] = Field(default_factory=list)
	# Opportunities are a DIFFERENT kind of claim from weaknesses above, and the
	# brief is explicit that they must exist even with no pain signals at all --
	# better quality, faster, cheaper. So they are not sourced facts ABOUT the
	# competitor; they are openings derived from cited facts about them plus the
	# user's offer. Keeping them in their own field stops a derived opening from
	# being read as a sourced observation.
	opportunities: list[str] = Field(default_factory=list)
	notable_customers: list[str] = Field(default_factory=list)

	pain_signals: list[SourcedFinding] = Field(
		default_factory=list,
		description="Specific, evidenced complaints. Empty is a legitimate and "
		"common outcome -- it is not the same as 'they have no problems'",
	)
	customer_sentiment: list[SourcedFinding] = Field(
		default_factory=list,
		description="What customers say about them overall. Separate from pain "
		"signals because a well-loved firm can still beat us on price",
	)

	tracking_sources: list[CompetitorSocial] = Field(default_factory=list)

	evidence: dict[str, list[str]] = Field(
		default_factory=dict,
		description="{field_name: [source_url, ...]} -- which retrieved page backs "
		"which claim. This is the audit trail for every other field",
	)
	unsourced_fields: list[str] = Field(
		default_factory=list,
		description="Field names research could NOT establish. The UI renders "
		"these as 'not found' rather than as empty space",
	)


class CompetitorProfileBatch(LenientModel):
	profiles: list[CompetitorProfile] = Field(default_factory=list)


class CompetitorRunOutcome(LenientModel):
	"""What one run did, in the shape the API records on the run row."""

	candidates_seen: int = 0
	found: int = 0
	dropped: int = 0
	dropped_reasons: dict[str, int] = Field(
		default_factory=dict,
		description="{reason: count}. 'no_public_website' is expected to dominate: "
		"that is the brief's filter working, not a lossy run",
	)


class CompetitorRelevance(LenientModel):
	"""The competitor gate: same job for the same buyer, or not a competitor."""

	offer_job: str = Field(description="The one job the user's offer does for its buyer, in under 15 words")
	their_job: str = Field(description="The one job this company's main offering does for its buyer, in under 15 words")
	same_buyer: bool = Field(description="Would the same person or team buy both?")
	substitute: bool = Field(
		description="Would that buyer choose this company's offering INSTEAD of the user's offer, to get the same "
		"job done -- even with different technology, or for a substantial part of the job? False for tools that integrate with it, sit beside it, run "
		"underneath it, govern or advise on it, or do a different job for the same buyer.",
	)
