import json
import operator
from typing import TypedDict, List, Optional, Literal, Annotated
from pydantic import BaseModel, Field, field_validator

from langgraph.graph.message import add_messages

# TaskResearchBundle is deliberately imported from the canonical module rather
# than redefined here. Every model that reaches a LangGraph checkpoint has to be
# allowlisted by module. backend/app/agents_runtime.py derives that allowlist by
# reflecting over BOTH `agents.states` and this module, keeping a class only when
# its `__module__` equals the module it was found in -- so a model DEFINED here is
# allowlisted under `agents.sub_agents.schema_states`, and one merely IMPORTED
# here is not (which is why this import list must not be mistaken for the
# allowlist). Defining a duplicate here instead of importing it would work, but
# would give the same class two identities and two checkpoint representations.
from agents.states import (
    CompetitionExtraction,
    FollowUp,
    ICP,
    IdealCompetitorProfile,
    IcpFindings,
    MarketExtraction,
    TaskResearchBundle,
)

# SCHEMAS AND STATES

# -- SPECIAlISTS --

class Specialist(BaseModel):
    domain: Literal["product", "service", "market", "competition", "gtm"] = Field(
        description="Which of the five research domains this specialist covers. 'product' or 'service' is the offer's own domain expert; the other three are market, competition and go-to-market. Required rather than inferred so a consumer can select the right specialist from a team without relying on list position -- without it, picking the product specialist out of OfferSessionState.specialists is guesswork.",
    )
    affiliation: str = Field(
        description="Primary affiliation of the specialist.",
    )
    name: str = Field(
        description="Name of the specialist."
    )
    role: str = Field(
        description="Role of the specialist in the context of the topic.",
    )
    description: str = Field(
        description="Description of the specialist focus, concerns, and motives.",
    )
    @property
    def persona(self) -> str:
        return (
            f"Name: {self.name}\n"
            f"Role: {self.role}\n"
            f"Domain: {self.domain}\n"
            f"Affiliation: {self.affiliation}\n"
            f"Description: {self.description}\n"
        )

class Perspectives(BaseModel):
    specialists: List[Specialist] = Field(
        description="Comprehensive list of the product/service specialist with their roles and affiliations.",
    )

# -- TASKS --

def _extract_json_value(text: str):
    """Tolerant JSON extraction, mirroring llm/main._json_from_text but taking
    the EARLIEST opening bracket, so a bare top-level array beats the object
    brace inside it.

    If a whole-string parse fails, pull the first valid JSON value out of the
    text: models habitually append a stray brace after the closing bracket of a
    list field ('...] }') or wrap the answer in prose/fences, and raw_decode
    stops after the first complete value, ignoring the trailing garbage.
    """
    decoder = json.JSONDecoder()

    def _positions(offset: int) -> list[int]:
        found = [text.find(k, offset) for k in ("{", "[")]
        return [p for p in found if p != -1]

    positions = _positions(0)
    idx = min(positions) if positions else -1
    while idx != -1:
        try:
            obj, _ = decoder.raw_decode(text[idx:])
            return obj
        except json.JSONDecodeError:
            positions = _positions(idx + 1)
            idx = min(positions) if positions else -1
    return text


def _coerce_json(value):
    """Accept a JSON string where a list is expected.

    Qwen models habitually serialise a list field as a JSON *string* even when
    the schema declares `list[...]` -- and frequently with trailing stale
    characters, so the string does not even parse whole. Without this,
    `TaskList.tasks` arrives as an unclean string, pydantic rejects it, and the
    planner falls into llm.main's `_try_repair_structured`, which re-asks the
    model: a full second flagship round-trip every time the habit fires. Same
    pattern `agents.states` applies to its Interview plans; this local mirror
    keeps sub_agents' models self-contained.
    """
    if isinstance(value, str):
        try:
            return json.loads(value)
        except (json.JSONDecodeError, TypeError):
            return _extract_json_value(value)
    return value


class ResearchTask(BaseModel):
    area: str = Field(description="The knowledge-gap area this task closes")
    objective: str = Field(description="What this task must establish — a research goal, not a search string")
    queries: list[str] = Field(
        default_factory=list,
        description="2 independent web-search queries, ordered most specific first; the second is the broad fallback. NEVER include the offer's or brand's name — research the DOMAIN/CATEGORY the offer sits in, so the sources describe the category rather than the offer",
    )

    @field_validator("queries", mode="before")
    @classmethod
    def _coerce_queries(cls, v):
        v = _coerce_json(v)
        if isinstance(v, list):
            return [q for q in v if isinstance(q, str)]
        return v  # not a list: let pydantic raise its own type error


class TaskList(BaseModel):
    tasks: list[ResearchTask] = Field(default_factory=list, description="The research tasks to execute this round")

    @field_validator("tasks", mode="before")
    @classmethod
    def _coerce_tasks(cls, v):
        return _coerce_json(v)


# -- SESSION STATE --

class OfferSessionState(TypedDict):
    # Offer Snapshot
    offer_type: Optional[Literal["product", "service"]] = None
    offer_name: str = Field(description="")
    offer_description: str = Field(description="")
    target_market: List[str] = Field(description="")
    problem: str | None = Field(default=None, description="The problem the offer addresses, as the offer's own material states it")
    solution: str | None = Field(default=None, description="How the offer solves it, in neutral terms")
    target_users: list[str] = Field(default_factory=list, description="Who the offer is for, as stated in its own material")
    features: list[str] = Field(default_factory=list)
    service_uniqueness: list[str] = Field(default_factory=list, description="For a service: the distinctive elements that make this service different from alternatives")
    how_it_works: str | None = Field(default=None, description="How the product works end-to-end, in plain terms")

    # --Phases completion--
    specialist_generation_complete: bool = Field(default=False, description="")
    offer_under_complete: bool = Field(default=False, description="")

    # --Findings--
    offer_findings: Optional[str] = Field(default=None, description="Domain research notes from the product/service specialist")

    # --Understanding--
    offer_domain_fit_understanding: Optional[str] = Field(default=None, description="")

    # --
    scraped_content: Optional[str] = None

    # --
    specialists: List[Specialist] = Field(description="")

    # --Research plan and its results--
    # `task_research` is the pipeline's only accumulator. One TaskResearchBundle
    # is appended per research task, so `note_down_record` can see which
    # objective produced which evidence -- and, just as importantly, which
    # objective produced none. An empty area is a finding in its own right and
    # would vanish if the bundles were merged into one pile of notes.
    tasks: Optional[TaskList] = None
    task_research: Annotated[list, operator.add]

    # --
    messages: Annotated[list, add_messages]


class DiscoverOfferState(TypedDict):
    """Interactive offer-intake stage of the offer session, in the sub_agents
    family idiom — the loose-key twin of the interview-era
    discover_product_service flow (agents/sub_graphs/discover_product_service.py).

    It writes the SAME loose snapshot keys the downstream research pipelines
    read (`offer_type`, `offer_name`, `offer_description`, `target_market`,
    `problem`, `features`/`service_uniqueness` as plain names, `how_it_works`)
    instead of the interview-era `offer_snapshot`/`OfferDataSnapshot`. The
    interaction machinery (messages, follow_up, scraped_content, and the flow
    flags that route the Command-based interrupts) is carried here so a
    threaded top-level driver can prompt and resume exactly like gtmx_agent's
    flood of `discover_product_service` interrupts.
    """

    # -- Offer Snapshot (the loose keys the downstream pipelines read) --
    website_url: Optional[str] = None
    offer_type: Optional[Literal["product", "service"]] = None
    offer_name: str = Field(description="")
    offer_description: str = Field(description="")
    target_market: List[str] = Field(description="")
    problem: str | None = Field(default=None, description="The problem the offer addresses, as the offer's own material states it")
    solution: str | None = Field(default=None, description="How the offer solves it, in neutral terms")
    target_users: list[str] = Field(default_factory=list, description="Who the offer is for, as stated in its own material")
    features: list[str] = Field(default_factory=list)
    service_uniqueness: list[str] = Field(default_factory=list, description="For a service: the distinctive elements that make this service different from alternatives")
    how_it_works: str | None = Field(default=None, description="How the offer works end-to-end, in plain terms")

    # -- Conversation / intake machinery --
    messages: Annotated[list, add_messages]
    follow_up: Optional[FollowUp] = None
    scraped_content: Optional[str] = None
    scrape_failed: bool = False
    name_mismatch: bool = False
    product_candidates: List[str] = Field(description="")
    confirmed: bool = False


class MarketSessionState(TypedDict):
    """The market-understanding stage of the offer session, as a research pipeline.

    Carries the same loose inputs the offer stage reads (specialist selection by
    `domain`, the offer's own material), but holds its research results in
    dedicated `market_*` channels. That separation is deliberate: offer and
    market are two pipelines that can run inside one session, and sharing the
    offer stage's `tasks`/`task_research` channels would let the second plan
    overwrite the first and mix both stages' bundles into each other's writers.

    Outputs mirror what gtmx_agent.run_market_interview expects to fold back into
    the session (`market_findings`, `product_market_fit_understanding`,
    `market_data`, `market_complete`), so the pipeline can stand in for the
    interview without reworking its consumers.
    """

    # -- Offer Snapshot (the same loose inputs the offer pipeline reads) --
    offer_type: Optional[Literal["product", "service"]] = None
    offer_name: str = Field(description="")
    offer_description: str = Field(description="")
    target_market: List[str] = Field(description="")
    problem: str | None = Field(default=None, description="The problem the offer addresses, as the offer's own material states it")
    solution: str | None = Field(default=None, description="How the offer solves it, in neutral terms")
    target_users: list[str] = Field(default_factory=list, description="Who the offer is for, as stated in its own material")
    features: list[str] = Field(default_factory=list)
    service_uniqueness: list[str] = Field(default_factory=list, description="For a service: the distinctive elements that make this service different from alternatives")
    how_it_works: str | None = Field(default=None, description="How the offer works end-to-end, in plain terms")
    scraped_content: Optional[str] = None
    specialists: List[Specialist] = Field(description="")

    # --Research plan and its results--
    # `market_task_research` is this pipeline's only accumulator, kept apart from
    # the offer stage's `task_research` so the two stages can run in one session
    # without mixing evidence. One TaskResearchBundle is appended per research
    # task, so `note_down_record` can see which objective produced which evidence
    # -- and, just as importantly, which objective produced none.
    market_tasks: Optional[TaskList] = None
    market_task_research: Annotated[list, operator.add]

    # --Findings--
    market_findings: Optional[str] = Field(default=None, description="Market research notes from the market specialist, with the ### Sources block appended")

    # --Understanding--
    product_market_fit_understanding: Optional[str] = Field(default=None, description="Brief standalone synthesis of the offer's fit in its market; target 40 words, maximum 50")

    # --Structured extraction--
    # The classification-side output the gtmx consumers read. Soft-fail by
    # design: the narrative findings are the pipeline's product, and this
    # record is the compatibility layer for consumers built against the
    # interview-era `MarketExtraction`.
    market_data: Optional[MarketExtraction] = Field(default=None, description="Structured market definition + product-market-fit verdict")

    # --Completion--
    market_complete: bool = Field(default=False, description="")

    # --


class CompetitionSessionState(TypedDict):
    """The competition-understanding stage of the offer session, as a research
    pipeline.

    Carries the same loose inputs the offer and market stages read, its own
    dedicated `competition_*` research/result channels, and -- the stage's
    defining feature -- the SIBLING STAGE OUTPUTS the competition expert is
    required to reason with. Competition only makes sense with the market and
    the domain in hand: who/what the rivals are, and what buyers in this
    category actually weigh, are scoped by the domain and market findings. All
    sibling keys are Optional passthroughs: a session that runs the stages in
    order supplies them, and a standalone competition run (or a session that
    ordered it first) degrades gracefully.

    Outputs mirror what gtmx_agent.run_competition_interview expects to fold
    back into the session (`competition_findings`,
    `competitive_positioning_understanding`, `competition_data`,
    `competition_complete`), so the pipeline can stand in for the interview
    without reworking its consumers.
    """

    # -- Offer Snapshot (the same loose inputs the offer pipeline reads) --
    offer_type: Optional[Literal["product", "service"]] = None
    offer_name: str = Field(description="")
    offer_description: str = Field(description="")
    target_market: List[str] = Field(description="")
    problem: str | None = Field(default=None, description="The problem the offer addresses, as the offer's own material states it")
    solution: str | None = Field(default=None, description="How the offer solves it, in neutral terms")
    target_users: list[str] = Field(default_factory=list, description="Who the offer is for, as stated in its own material")
    features: list[str] = Field(default_factory=list)
    service_uniqueness: list[str] = Field(default_factory=list, description="For a service: the distinctive elements that make this service different from alternatives")
    how_it_works: str | None = Field(default=None, description="How the offer works end-to-end, in plain terms")
    scraped_content: Optional[str] = None
    specialists: List[Specialist] = Field(description="")

    # -- Sibling stage outputs the competition expert is given to reason with --
    # Read-only passthroughs. Their Sources blocks are stripped before use; the
    # numbered lists belong to those stages' own retrieved sets and would
    # collide with this stage's citation list.
    offer_findings: Optional[str] = Field(default=None, description="The domain stage's research notes (Sources block stripped at use)")
    offer_domain_fit_understanding: Optional[str] = Field(default=None, description="The domain stage's fit understanding")
    market_findings: Optional[str] = Field(default=None, description="The market stage's research notes (Sources block stripped at use)")
    product_market_fit_understanding: Optional[str] = Field(default=None, description="The market stage's fit understanding")
    market_data: Optional[MarketExtraction] = Field(default=None, description="The market stage's structured extraction, used to scope the competitive landscape")

    # --Research plan and its results--
    # `competition_task_research` is this pipeline's only accumulator, kept
    # apart from the offer stage's `task_research` and the market stage's
    # `market_task_research` so all three pipelines can run inside one session
    # without mixing evidence.
    competition_tasks: Optional[TaskList] = None
    competition_task_research: Annotated[list, operator.add]

    # --Findings--
    competition_findings: Optional[str] = Field(default=None, description="Competitive-landscape research notes from the competition specialist, with the ### Sources block appended")

    # --Understanding--
    competitive_positioning_understanding: Optional[str] = Field(default=None, description="Brief standalone synthesis of how the offer is positioned vs. its real competitors; target 40 words, maximum 50")

    # --Structured extraction--
    # The stage's PRIMARY structured output: an archetype profile of what a
    # perfect competitor looks like, deliberately not geo-bounded and naming no
    # one. It replaced a `competitors: list[Competitor]` field on
    # CompetitionExtraction; finding real, verified rivals is the standalone
    # get_competitors agent's job. Soft-fail with in-node handling, exactly
    # where the interview-era extract_competitors/verify_competitors pair used
    # to, so a lost profile cannot sink a run whose notes are already written.
    ideal_competitor_profile: Optional[IdealCompetitorProfile] = Field(default=None, description="The refined Ideal Competitor Profile: category boundary + local/regional/global archetypes, no named companies")

    # The offer-vs-standard SWOD the gtmx consumers (ICP, competition briefing)
    # read, kept as its own record because it is a judgment about the offer
    # rather than a description of the landscape.
    competition_data: Optional[CompetitionExtraction] = Field(default=None, description="Structured strengths/weaknesses/opportunities/differentiators for the offer against the competitive standard")

    # --Completion--
    competition_complete: bool = Field(default=False, description="")


class IcpSessionState(TypedDict):
    """The ICP-understanding stage of the offer session, as a SYNTHESIS pipeline.

    The GTM stage sits between the competition stage and account discovery: it
    consumes every sibling stage's outputs (offer/domain, market, competition)
    and produces the Ideal Customer Profile that account discovery searches for.

    Unlike offer/market/competition it does NO web research. The ICP is the GTM
    specialist's buyer-type-aware judgment derived from the session's gathered
    understanding, and the stage immediately downstream (account discovery) does
    the reach research. The absence of `icp_tasks`/`icp_task_research` channels
    is therefore structural, not an oversight: there is nothing to research and
    nothing to recency-gate in this stage.

    It branches on offer_type (product/service) x buyer_type (b2b/b2c/both, from
    the market stage's structured extraction): firmographics carry for B2B,
    personas + reach channels carry for B2C, and product vs service shapes how
    the profile is acquired (adoption vs trust/local reach).

    Outputs mirror what gtmx_agent.run_determine_icp expects to fold back into
    the session (`icp`/`icp_complete` -- held here as `icp_data`), plus the
    family-consistent narrative `icp_findings` and 40/50-word understanding, so
    the pipeline can stand in for the interview without reworking its consumers.
    """

    # -- Offer Snapshot (the same loose inputs the other pipelines read) --
    offer_type: Optional[Literal["product", "service"]] = None
    offer_name: str = Field(description="")
    offer_description: str = Field(description="")
    target_market: List[str] = Field(description="")
    problem: str | None = Field(default=None, description="The problem the offer addresses, as the offer's own material states it")
    solution: str | None = Field(default=None, description="How the offer solves it, in neutral terms")
    target_users: list[str] = Field(default_factory=list, description="Who the offer is for, as stated in its own material")
    features: list[str] = Field(default_factory=list)
    service_uniqueness: list[str] = Field(default_factory=list, description="For a service: the distinctive elements that make this service different from alternatives")
    how_it_works: str | None = Field(default=None, description="How the offer works end-to-end, in plain terms")
    scraped_content: Optional[str] = None
    specialists: List[Specialist] = Field(description="")

    # -- Sibling stage outputs the gtm specialist is given to reason with --
    # Read-only passthroughs. Their Sources blocks are stripped before use; the
    # numbered lists belong to those stages' own retrieved sets, and this stage
    # retrieves nothing of its own.
    offer_findings: Optional[str] = Field(default=None, description="The domain stage's research notes (Sources block stripped at use)")
    offer_domain_fit_understanding: Optional[str] = Field(default=None, description="The domain stage's fit understanding")
    market_findings: Optional[str] = Field(default=None, description="The market stage's research notes (Sources block stripped at use)")
    product_market_fit_understanding: Optional[str] = Field(default=None, description="The market stage's fit understanding")
    market_data: Optional[MarketExtraction] = Field(default=None, description="The market stage's structured extraction; its buyer_type branches the whole profile")
    competition_findings: Optional[str] = Field(default=None, description="The competition stage's research notes (Sources block stripped at use)")
    competitive_positioning_understanding: Optional[str] = Field(default=None, description="The competition stage's positioning understanding")
    ideal_competitor_profile: Optional[IdealCompetitorProfile] = Field(default=None, description="The competition stage's archetype profile — names no one, so it cannot seed a named competitor_lead on its own")
    competition_data: Optional[CompetitionExtraction] = Field(default=None, description="The competition stage's offer-vs-standard SWOD. competitor_leads derive from the research PROSE plus the archetype profile's where_to_find_them, never from a name list this stage no longer emits")

    # --Structured synthesis--
    # The load-bearing output account discovery reads. Drafted (create_icp),
    # then pruned + coherence-checked (refine_icp) before the writer is anchored
    # on it.
    icp_data: Optional[ICP] = Field(default=None, description="The finalized, self-review-passed Ideal Customer Profile (ICP) for the offer")

    # --Findings--
    icp_findings: Optional[str] = Field(default=None, description="GTM-stage notes laying out the ICP and how it will be reached; synthesis prose cited by label, with no Sources block by design")

    # --Understanding--
    icp_understanding: Optional[str] = Field(default=None, description="Brief standalone synthesis of who the ICP is and where to reach them; target 40 words, maximum 50")

    # --Completion--
    icp_complete: bool = Field(default=False, description="")


class DiscoverySessionState(DiscoverOfferState):
    """Top-level session state of the discovery agent — the union of the offer
    intake stage, the specialist team, and every research pipeline's channels.

    One state bag the whole workflow reads and writes, with each compiled
    subgraph consuming its own slice of it and writing its results back into
    its own channels. Inherits all of `DiscoverOfferState` (loose snapshot keys
    + the interactive intake machinery) so `interrupt()`/`Command(resume=...)`
    thread through the top-level driver exactly like gtmx_agent.
    """

    # -- Specialist team (created right after intake) --
    specialists: List[Specialist] = Field(description="")
    specialist_generation_complete: bool = Field(default=False, description="")

    # -- Offer pipeline (understand_offer) --
    # `task_research` is the offer stage's only accumulator, kept apart from the
    # market stage's `market_task_research` and the competition stage's
    # `competition_task_research` because offer and market run in parallel —
    # two of the accumulators are mid-flight at the same time and must not share
    # a channel.
    tasks: Optional[TaskList] = None
    task_research: Annotated[list, operator.add]

    # --Findings--
    offer_findings: Optional[str] = Field(default=None, description="Domain research notes from the product/service specialist")

    # --Understanding--
    offer_domain_fit_understanding: Optional[str] = Field(default=None, description="")

    # --Completion--
    offer_under_complete: bool = Field(default=False, description="")

    # -- Market pipeline (understand_market) --
    market_tasks: Optional[TaskList] = None
    market_task_research: Annotated[list, operator.add]

    # --Findings--
    market_findings: Optional[str] = Field(default=None, description="Market research notes from the market specialist, with the ### Sources block appended")

    # --Understanding--
    product_market_fit_understanding: Optional[str] = Field(default=None, description="Brief standalone synthesis of the offer's fit in its market; target 40 words, maximum 50")

    # --Structured extraction--
    market_data: Optional[MarketExtraction] = Field(default=None, description="Structured market definition + product-market-fit verdict")

    # --Completion--
    market_complete: bool = Field(default=False, description="")

    # -- Competition pipeline (understand_competition) --
    competition_tasks: Optional[TaskList] = None
    competition_task_research: Annotated[list, operator.add]

    # --Findings--
    competition_findings: Optional[str] = Field(default=None, description="Competitive-landscape research notes from the competition specialist, with the ### Sources block appended")

    # --Understanding--
    competitive_positioning_understanding: Optional[str] = Field(default=None, description="Brief standalone synthesis of how the offer is positioned vs. its real competitors; target 40 words, maximum 50")

    # --Structured extraction--
    ideal_competitor_profile: Optional[IdealCompetitorProfile] = Field(default=None, description="The refined Ideal Competitor Profile: category boundary + local/regional/global archetypes, no named companies")
    competition_data: Optional[CompetitionExtraction] = Field(default=None, description="Structured strengths/weaknesses/opportunities/differentiators for the offer against the competitive standard")

    # --Completion--
    competition_complete: bool = Field(default=False, description="")

    # -- ICP pipeline (determine_icp) --
    icp_data: Optional[ICP] = Field(default=None, description="The finalized, self-review-passed Ideal Customer Profile (ICP) for the offer")
    icp_findings: Optional[str] = Field(default=None, description="GTM-stage notes laying out the ICP and how it will be reached")
    icp_understanding: Optional[str] = Field(default=None, description="Brief standalone synthesis of who the ICP is and where to reach them; target 40 words, maximum 50")
    icp_complete: bool = Field(default=False, description="")



# ============================================================================
# COMPETITOR AGENT (get_competitors) -- the epistemic inverse of the competition
# stage.
#
# `IdealCompetitorProfile` above is a CONSTRUCT: "the regional incumbent
# undercutting on price" makes no claim that any firm exists, which is exactly
# why it may be aggressive and needs no sourcing. Everything in this section is
# the opposite -- a claim that a NAMED, REAL company exists and does these
# things. So the models here are shaped around provenance rather than coverage:
#
#   - `CandidateFinding.website` is nullable and a null means the candidate is
#     DROPPED, because a firm with no findable public site cannot be verified.
#   - `SourcedFinding` requires `evidence`, so an unsourced assertion about a
#     real company is unrepresentable rather than merely discouraged.
#   - `CompetitorProfile.unsourced_fields` names what research could not
#     establish, so the UI says "not found" instead of rendering a blank that
#     reads as a finding.
#
# The two standards must not blur. In particular the competition stage's "be
# aggressive, construct freely" instruction has NO place in this agent: an
# invented weakness attributed to a real named company is a factual error about
# an identifiable business, not a hypothesis.
# ============================================================================


class CompetitorHuntTask(BaseModel):
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


class CompetitorHuntPlan(BaseModel):
	tasks: list[CompetitorHuntTask] = Field(default_factory=list)


class CandidateFinding(BaseModel):
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


class CompetitorHuntBundle(BaseModel):
	"""What one hunt task found, with the sources behind it."""

	archetype_label: str = ""
	geography_scope: str = "any"
	candidates: list[CandidateFinding] = Field(default_factory=list)
	search_failed: bool = Field(default=False)
	queries: list[str] = Field(default_factory=list)
	sources: list[dict] = Field(default_factory=list)


class SourcedFinding(BaseModel):
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


class CompetitorSocial(BaseModel):
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


class CompetitorProfile(BaseModel):
	"""A verified real company, profiled with per-field provenance.

	The inverse of `CompetitorArchetype`. Every field is a claim about a real
	firm, so the model carries the evidence for each one and names the fields
	research could not establish.
	"""

	name: str
	website: str = Field(description="Required. A firm with no public site is not tracked")
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


class CompetitorProfileBatch(BaseModel):
	profiles: list[CompetitorProfile] = Field(default_factory=list)


class CompetitorRunOutcome(BaseModel):
	"""What one run did, in the shape the API records on the run row."""

	candidates_seen: int = 0
	found: int = 0
	dropped: int = 0
	dropped_reasons: dict[str, int] = Field(
		default_factory=dict,
		description="{reason: count}. 'no_public_website' is expected to dominate: "
		"that is the brief's filter working, not a lossy run",
	)


class CompetitorSessionState(TypedDict):
	"""The standalone competitor hunt, as a hunt -> screen -> profile pipeline.

	Deliberately not part of the discovery spine's state. This agent runs on its
	own, from a workspace, after discovery has already finished, and re-runs as
	often as the user likes. Two consequences shape the state:

	1. It reads its offer and its archetype profile OUT OF THE DATABASE rather
	   than inheriting them on the session. The discovery checkpoint cannot help
	   it: that thread id is minted per WebSocket connection, so nothing maps a
	   finished run to the workspace a later request comes in on.

	2. There is no Sources-bearing findings channel, unlike every research stage
	   in the spine. Nothing here is written for a human to read as prose; the
	   sources are kept structured (per-candidate `sources`, per-field `evidence`)
	   because every claim in this stage has to be auditable, which prose notes
	   are not.
	"""

	# -- Inputs, hydrated from the workspace's product profile --
	# offer_type decides the noun the prompts use ("product" vs "service"), the
	# same switch the rest of the codebase reads, so a service workspace is
	# hunted in service language without a second toggle.
	offer_type: Optional[Literal["product", "service"]] = None
	offer_name: str = Field(description="")
	offer_description: str = Field(description="")
	problem: str | None = Field(default=None, description="The problem the offer addresses")
	solution: str | None = Field(default=None, description="How the offer solves it")
	features: list[str] = Field(default_factory=list, description="Differentiators, used to judge how the offer compares to a rival")
	# The offer's own site, so a run can recognise the user and refuse to file
	# them as their own competitor.
	own_website: str | None = Field(default=None, description="The offer's own website, for self-exclusion")

	# -- The shape being hunted for --
	# A dict as persisted, not a validated IdealCompetitorProfile: it arrives
	# from the insights JSON blob. _archetype_rows() tolerates both shapes.
	ideal_competitor_profile: Optional[dict] = Field(
		default=None,
		description="The competition stage's archetype profile. Archetypes only -- "
		"it names no company, so it can only say what to look FOR",
	)

	# -- Pipeline channels --
	competitor_hunt_tasks: List[CompetitorHuntTask] = Field(
		default_factory=list, description="One search assignment per archetype"
	)
	competitor_hunt_bundles: List[CompetitorHuntBundle] = Field(
		default_factory=list, description="Per-task candidates plus the sources they came from"
	)
	# Screening output. A plain dict rather than a model because the screen also
	# carries the retrieved sources forward, and the dataclasses.asdict call a
	# model dump would give is not worth the schema surface.
	competitor_survivors: List[dict] = Field(
		default_factory=list, description="Candidates that survived the website filter, deduplicated"
	)
	competitor_profiles: List[CompetitorProfile] = Field(
		default_factory=list, description="Sourced profiles, built only for survivors"
	)
	competitor_outcome: Optional[CompetitorRunOutcome] = Field(
		default=None,
		description="What the run screened and kept. Carries the DROP reasons, "
		"because a run keeping 3 of 40 is the filter working and has to be "
		"reportable as such",
	)
