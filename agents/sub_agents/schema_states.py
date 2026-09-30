import json
import operator
from typing import TypedDict, List, Optional, Literal, Annotated
from pydantic import BaseModel, Field, field_validator

from langgraph.graph.message import add_messages

# TaskResearchBundle is deliberately imported from the canonical module rather
# than redefined here. Every model that reaches a LangGraph checkpoint has to be
# allowlisted by module, and backend/app/agents_runtime.py:38-43 derives that
# allowlist by reflecting over `agents.states` and filtering on
# `__module__ == "agents.states"`. A bundle defined in this file would carry
# `__module__ == "agents.sub_agents.schema_states"`, land outside the
# allowlist, and log "Blocked deserialization" on every checkpoint read -- the
# same failure the comment there records for BuyerType/ProductCategory.
from agents.states import (
    CompetitionExtraction,
    FollowUp,
    ICP,
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
    offer_type_lean: Optional[str] = None
    offer_type_reasoning: Optional[str] = None
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
    market_data: Optional[MarketExtraction] = Field(default=None, description="The market stage's structured extraction, used to scope the competitor set")

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
    # The competitor set + SWOD the gtmx consumers (ICP, competition briefing)
    # read. Soft-fail with in-node competitor URL verification, exactly like the
    # interview-era extract_competitors/verify_competitors pair.
    competition_data: Optional[CompetitionExtraction] = Field(default=None, description="Structured competitor set + strengths/weaknesses/opportunities/differentiators")

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
    competition_data: Optional[CompetitionExtraction] = Field(default=None, description="The competition stage's structured competitor set + SWOD; competitor_leads derive only from it")

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
    competition_data: Optional[CompetitionExtraction] = Field(default=None, description="Structured competitor set + strengths/weaknesses/opportunities/differentiators")

    # --Completion--
    competition_complete: bool = Field(default=False, description="")

    # -- ICP pipeline (determine_icp) --
    icp_data: Optional[ICP] = Field(default=None, description="The finalized, self-review-passed Ideal Customer Profile (ICP) for the offer")
    icp_findings: Optional[str] = Field(default=None, description="GTM-stage notes laying out the ICP and how it will be reached")
    icp_understanding: Optional[str] = Field(default=None, description="Brief standalone synthesis of who the ICP is and where to reach them; target 40 words, maximum 50")
    icp_complete: bool = Field(default=False, description="")

