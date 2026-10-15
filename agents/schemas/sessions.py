"""LangGraph state schemas (TypedDicts) for each pipeline and the top-level discovery session."""

import operator
from typing import Annotated, List, Literal, Optional, TypedDict

from pydantic import Field
from langgraph.graph.message import add_messages

from agents.schemas.accounts import AccountList
from agents.schemas.competition import (
    CompetitionExtraction,
    CompetitorHuntBundle,
    CompetitorHuntTask,
    CompetitorProfile,
    CompetitorRunOutcome,
    IdealCompetitorProfile,
)
from agents.schemas.icp import ICP
from agents.schemas.market import MarketExtraction
from agents.schemas.offer import FollowUp
from agents.schemas.research import Specialist, TaskList


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
    """Interactive offer-intake stage of the offer session.

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
    # The organization behind the offer ("Shanga Labs"), read off its site.
    company_name: Optional[str] = None
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

    # -- Scraped site understanding --
    scraped_content: Optional[str] = None
    page_understanding: Optional[str] = None
    scrape_failed: bool = False
    # The site couldn't be read and the reply wasn't a description: ask for one.
    asked_to_describe: bool = False
    name_mismatch: bool = False
    product_candidates: List[str] = Field(description="")
    confirmed: bool = False

    # -- Conversation / intake machinery --
    messages: Annotated[list, add_messages]
    follow_up: Optional[FollowUp] = None


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

    # -- Account discovery outputs --
    account_discovery_queries: Optional[list[str]] = Field(default=None, description="Queries generated for account discovery")
    exclude_domains: list[str] = Field(default_factory=list, description="Domains that are never targets: the offer's own company and its tracked competitors")
    account_discovery_docs: Optional[list[dict]] = Field(default=None, description="Documents retrieved for account discovery")
    accounts: Optional[AccountList] = Field(default=None, description="AccountDiscovery account candidates")


class DiscoverySessionState(DiscoverOfferState):
    """Top-level session state of the discovery agent — the union of the offer
    intake stage, the specialist team, and every research pipeline's channels.

    One state bag the whole workflow reads and writes, with each compiled
    subgraph consuming its own slice of it and writing its results back into
    its own channels. Inherits all of `DiscoverOfferState` (loose snapshot keys
    + the interactive intake machinery) so `interrupt()`/`Command(resume=...)`
    thread through the top-level driver exactly like gtmx_agent.
    """

    # -- Intake source: which discover_offer path ran --
    # "website" (scrape flow) or "manual" (no-website description flow).
    source: Optional[Literal["website", "manual"]] = None

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
	target_market: list[str] = Field(default_factory=list, description="The workspace's target geographies, used to prioritise local competitor searches")
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
