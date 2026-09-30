"""
Competition Understanding.

The competition stage, as an explicit research pipeline rather than a multi-turn
interview, borrowed from the offer and market pipelines:

    create_tasks_research      -> plan 3-5 competition research objectives
    conduct_research           -> run them, one bundle of evidence per objective
    extract_competition_data   -> the structured competitor set + SWOD (soft-fail)
    note_down_record           -> write the competitive notes + positioning view

Deliberately LINEAR, for the same reason the offer and market stages are: the
pipeline's product is the findings + positioning understanding, a hard cost
bound is worth more here than marginal depth, and every extra round multiplies
Exa calls and distillation. There is no re-planning loop and no sufficiency
gate.

THE DEFININING FEATURE: the competition expert is given the market AND the
domain to reason with. Competition only makes sense with both in hand -- the
rivals are whoever else wins the business this offer is chasing, so "who are
they" is scoped by the domain findings (what the offer IS, technically) and the
market findings (who buys, what they pay, where they are). Every node reads a
`budget_context` assembled as:

    1. the offer's own material (first, so it gets protected)
    2. DOMAIN FINDINGS      -- offer_findings + its understanding, Sources stripped
    3. MARKET FINDINGS      -- market_findings + its understanding, Sources stripped
    4. MARKET CONTEXT       -- the structured MarketExtraction when present
    5. the retrieved competition bundles

The sibling findings' `### Sources` blocks are STRIPPED before embedding. Those
numbered lists belong to the sibling stages' own retrieved sets; keeping them
would (a) collide with THIS stage's numbered citation list and (b) put URLs
into the context that are not this stage's retrieved set, creating a blind spot
in the fabrication scan (a writer could echo a sibling URL and pass a check
that only trusts this run's sources). Sibling blocks are cited by LABEL
(`[domain findings]`, `[market findings]`) -- the same convention as the
existing `[offer material]` citation -- never by number. Every sibling key is
optional: a standalone competition run (or a session that ordered this stage
first) degrades gracefully.

Search is STRICTLY brand-free, the same invariant the offer and market stages
carry. The interview-era stage let the direct-competitor query name the offer
("X competitors"); this pipeline does not, because the planner now has enough
context to scope the competitor set by category + geography, and
"alternatives to X" pages are the least trustworthy surface on the internet.
Name-free category queries surface the same real rivals without the SEO junk.

The graph runs EXTRACT BEFORE WRITER -- deliberately the reverse of the market
stage. In the market stage the structured verdict is a judgment, so the
extractor was anchored to the narrative. Here the structured COMPETITOR SET is
a fact list, the load-bearing output ICP and the report consume, so the writer
is anchored on it: the notes name the same rivals the structured set names,
never additions the research didn't support. The extract node also mirrors the
interview's verify_competitors step in-process: each competitor website is
probed with a light scrape and hard failures are dropped (soft-fail, never
crashes the run).

RECENCY is inherited from the market stage: every search passes
`start_published_date = today - Config().market_recency_days` (default 365) --
the same window the interview-era understand_competition uses. Positioning,
pricing and features decay; a landscape built from stale sources is worse than
a thin one.

The single cosplayed expert is the competition specialist, selected out of
`specialists` by `Specialist.domain == "competition"` (see
`_competition_specialist_for`). The `extract_competition_data` node SOFT-FAILS
like the market stage's extractor: the narrative findings are the pipeline's
product, and losing the structured competitor set must not sink a run whose
notes are already written.
"""

import re
from concurrent.futures import ThreadPoolExecutor
from datetime import date, timedelta
from typing import Optional

from langgraph.graph import START, END, StateGraph
from langchain_core.messages import SystemMessage

from config import Config
from agents.llm.main import invoke_structured_with_fallback
from agents.context_budget import _truncate_to_tokens, budget_context, distill_documents
from agents.states import CompetitionExtraction, CompetitionFindings, TaskResearchBundle
from data_sources.scraping.exa import search_and_scrape, scrape_url

from .schema_states import CompetitionSessionState, ResearchTask, Specialist, TaskList
from .understand_offer import (
    _dedupe_sources,
    _known_facts,
    _offer_material,
    _offer_noun,
    _offer_nouns,
    _render_bundle,
    _render_task_plan,
    _sources_section,
    _specialist_lens,
)


# The planner is asked for 3-5; this is the hard stop. A schema hint is a
# suggestion, so the clamp is what actually bounds the fan-out cost of a run.
MAX_RESEARCH_TASKS = 5

# Matches the offer/market search budget. Competition research is additionally
# recency-gated below -- current rivals, current pricing, current positioning.
SEARCH_RESULTS_PER_QUERY = 3

# Tasks fan out here, and each task's own distillation fans out again inside
# distill_documents (4 workers). Four keeps every task in one wave while
# staying under the provider's token-per-minute window. Same rationale as the
# offer and market stages.
TASK_RESEARCH_MAX_WORKERS = 4

# How much of each scraped page is fed to the distiller. Same rationale as the
# offer/market stages: truncating the INPUT (not the note) keeps distillation in
# the few-second cheap-tier regime.
DISTILL_INPUT_TOKEN_CAP = 4_000

# Competition findings feed the report's competitive-positioning section.
# CompetitionSessionState carries no section_word_count, so this is the local
# target, matching how the offer and market stages set their own. The notes are
# deliberately brief -- a distillation of the distilled bundles -- so the target
# is 150 words with a hard harness cap at 300 words, 2x the target.
COMPETITION_FINDINGS_WORD_COUNT = 150
COMPETITION_FINDINGS_WORD_CAP = 300

# How much of each bundle's distilled notes the extractor and writer read.
# Same policy as the sibling pipelines' WRITER_NOTES_TOKEN_CAP.
WRITER_NOTES_TOKEN_CAP = 800

# How much of each sibling stage's findings the planner/extractor/writer read.
# The findings are ~150 words each; capping keeps the cross-stage context
# bounded without losing the substance the competition expert needs.
SIBLING_FINDINGS_TOKEN_CAP = 800


def _recency_cutoff(days: int) -> str:
    """ISO date (YYYY-MM-DD) for the oldest source the competition research may use."""
    return (date.today() - timedelta(days=days)).isoformat()


# Matches the report-writer convention: the harness-appended Sources block is
# always `\n\n### Sources\n...` preceded by the findings body.
_SOURCES_SPLIT = re.compile(r"\n###\s*Sources\b", re.IGNORECASE)


def _strip_sources_block(text: str) -> str:
    """Remove a sibling stage's harness-appended `### Sources` block.

    The numbered list belongs to that stage's own retrieved set, and (per the
    module docstring) keeping it would collide with this stage's citation list
    and open a fabrication-scan blind spot. Stripped here; the sibling findings
    are cited by label, never by number.
    """
    if not text:
        return ""
    return _SOURCES_SPLIT.split(text, maxsplit=1)[0].strip()


def _sibling_block(label: str, findings: str | None, understanding: str | None) -> str:
    """Render one sibling stage's findings as a labelled, capped context block."""
    body = _strip_sources_block(findings or "")
    if not body:
        return f"### {label}\n(not available -- the {label.lower().replace('_', ' ')} stage has not run)"
    body = _truncate_to_tokens(body, SIBLING_FINDINGS_TOKEN_CAP)
    if understanding and understanding.strip():
        body = f"{body}\n\nSynthesis: {understanding.strip()}"
    return f"### {label}\n{body}"


def _market_context_block(state: CompetitionSessionState) -> str:
    """The structured market context -- interview-faithful.

    The interview-era _market_context_block rendered MarketExtraction JSON to
    scope the competitor set (category, buyer, geos, pricing). The pipeline
    carries the same block so a session that ran the market stage first scopes
    identically.
    """
    market = state.get("market_data")
    if market is None:
        return (
            "No structured market data available -- scope the competitor set to "
            "the offer/category and its target geographies alone."
        )
    return market.model_dump_json(indent=2, exclude_none=True)


def _competition_specialist_for(state: CompetitionSessionState) -> Optional[Specialist]:
    """Pick the competition specialist out of the team.

    `Specialist.domain == "competition"` exists precisely so this is a lookup
    rather than a guess at list position. The fallbacks are for a hand-built
    team that skipped the field; they degrade rather than raising, because a
    persona is presentation, not correctness. Deliberately does NOT select by
    offer_type the way understand_offer's _specialist_for does.
    """
    specialists = [s for s in (state.get("specialists") or []) if s]
    if not specialists:
        return None
    for s in specialists:
        if getattr(s, "domain", None) == "competition":
            return s
    for s in specialists:
        if getattr(s, "domain", None) in ("product", "service"):
            return s
    return specialists[0]


def _competitor_names(state: CompetitionSessionState) -> str:
    """The structured competitor set the writer must stay grounded on."""
    data = state.get("competition_data")
    names = [c.name for c in (data.competitors or []) if c.name] if data else []
    if names:
        return ", ".join(names)
    return "(the extractor produced no competitor set -- ground the notes in the research alone)"


create_tasks_instructions = """
You are {specialist_name}, a {specialist_role} working in {specialist_affiliation}.

YOUR LENS
{specialist_description}

You are the competition specialist. You understand this {offer_noun}'s category,
its buyers and its target geographies -- you have that context in front of you
-- and you know the {offer_noun} itself from its own material. Before you can
say who its REAL rivals are, how they position, and where the {offer_noun} wins
and loses against them, you need evidence you do not have yet.

OFFER
- name          : {offer_name}
- type          : {offer_type}
- description   : {offer_description}
- target market : {target_market}

KNOWN FACTS (what the {offer_noun}'s own material already establishes. Treat it as
ground truth. Do not re-litigate it and do not research it as if it were open.)
{known_facts}

SIBLING STAGE CONTEXT (what the domain and market stages already established for
this session. Authoritative background: the domain block says what the
{offer_noun} IS, the market block says who buys it, where, and what they pay.
Use them to scope your research -- and do NOT plan tasks that re-research them.)
{sibling_context}

GOAL
Plan the research that identifies the {offer_noun}'s real competitive landscape
in the target geographies -- the rivals that actually compete for this buyer in
this category, how they position, what they charge, where their customers hurt,
and where the landscape leaves room for the {offer_noun}. You are planning, not
answering. Nothing has been searched yet, and the results come back to you
afterwards for you to read.

Each task is ONE objective that a set of public web sources could genuinely
settle, in an area such as:
- who the real rivals are in this category within the target geographies -- the
  direct competitors and substitutes that would actually take this business
- how each rival positions and what they offer: their messaging, their product
  or service scope, and their publicly stated pricing, funding and traction
- where rival customers hurt: complaints, churn reasons, gaps the rivals leave
  open (pain signals)
- how the {offer_noun} compares to those rivals on the things the market context
  says buyers actually weigh
- the gaps and opportunities in the landscape the {offer_noun} could exploit

The research MUST be current: competitive positioning, pricing and features
decay. Favour recent sources; a landscape built on stale conditions is worse
than a thin one.

SCOPE: what this research is NOT
- The {offer_noun}'s technical domain and how it works are researched separately
  (the domain findings above cover them). Do not plan tasks for them.
- The market's size, demand and category pricing NORMS are researched separately
  (the market findings above cover them). Your pricing interest is which RIVALS
  charge what, not the category norm.
- How the {offer_noun} stacks up -- its positioning verdict -- is YOUR judgment
  at the end, after the evidence is in. It is not something a web search
  settles, so do not plan a task for it.

RULES
1. Plan between 3 and 5 tasks. Fewer leaves the picture too thin to write from;
   more cannot be researched well in a single round.
2. Give each task exactly 2 independent queries, ordered most specific first. The
   second is the broad fallback, used only if the specific one returns nothing, so
   it should be broad enough to always return something.
3. NEVER put the {offer_noun}'s name or its brand in a query. Research the
   CATEGORY and the GEOGRAPHY, so the sources describe the rivals rather than
   this {offer_noun} or its own marketing claims. "Who competes in <category> in
   <geo>" finds the same rivals that "X competitors" would -- without the
   comparison-list SEO junk.
4. Scope queries to the target geographies where they are known, because the
   competitive landscape differs by geography.
5. Every objective is a research goal, not a search string. It must be specific
   enough that "this task came back with nothing" is itself a meaningful finding.
6. Do not assert what you will find, and do not invent competitors or facts. You
   are choosing what to look up.

Return only the structured task list. No commentary.
"""


record_instructions = """
You are an expert competitive analyst.

Write the RESEARCH NOTES that lay out this {offer_noun}'s competitive landscape
and how it stacks up, from the {offer_noun}'s own material, the domain and
market context this session already gathered, and the research that was carried
out for this stage.

These are notes, not a finished report section. A single report is written later
by someone who will also have the domain and market analyses in hand, so:

- Write NOTES, not report prose. No report title, no "# Heading" scaffolding.
- Be specific and evidence-dense. Another writer cannot recover what you leave
  out, but they can trim what you hand them.
- Keep every concrete claim: named competitors, their positioning, pricing,
  funding and traction figures, dates, feature gaps and geographies. Those are
  what get cited downstream.
- Be brief. These notes are conclusions plus the claims that evidence them, not a
  ledger of everything retrieved. Cut reasoning bridges, elaboration, and anything
  the report writer can recover from the sibling stages. When in doubt, leave it
  out.
- Name only rivals the research actually supports. Never infer or invent one.
- Say plainly where the evidence is thin, estimated or may be dated. Do not
  smooth over a gap.

Four kinds of material are in front of you, and they are not interchangeable:

1. The {offer_noun}'s OWN MATERIAL, labelled as such, is AUTHORITATIVE. It is
   the source for what the {offer_noun} is, who it is for, and the problem it
   solves.

2. The DOMAIN and MARKET blocks describe what the {offer_noun} IS and the market
   it sells into (who buys, what they pay, where). These were produced by the
   session's other stages and are background: use them to scope and judge the
   rivals, but cite them by LABEL -- "[domain findings]" or "[market findings]"
   -- never by a bracketed number.

3. The STRUCTURED COMPETITOR SET below is the extracted, verified list of real
   rivals from this same evidence. This is the load-bearing set: ground your
   notes in it. Do not add rivals that are not in it unless a retrieved source
   clearly names one, and do not drop the names it includes.

4. The RESEARCH BUNDLES, one per research objective, describe the rivals
   directly: who competes, how they position, what they charge, where they fall
   short.

SPECIALIST LENS
{specialist_lens}

STRUCTURED COMPETITOR SET
{competitor_set}

CITATIONS
Every inline citation must be a bracketed number from this list:

{auditable_sources}

- Cite with the exact numbers above, e.g. "RivalCo's enterprise tier starts at
  $1,200/year [2]".
- Never cite a URL that is not in this list. The list is the full, deduplicated
  set of pages this run actually retrieved; anything else is fabrication.
- The {offer_noun}'s own material has no URL and may be cited as
  "[offer material]"; the domain and market findings may be cited as
  "[domain findings]" and "[market findings]".
- Do NOT reproduce the list at the end of your notes. The harness appends the
  ### Sources section from it automatically, so a second copy would be
  redundant.

MATERIAL AND RESEARCH

{context}

1. Separate what is fact about the {offer_noun} itself from what describes its
   rivals. Do not blur the two into a single undifferentiated account.

2. Organise the notes with markdown sub-headers of your choosing (###). Cover:
- the competitive landscape: the principal rivals this {offer_noun} actually
  faces in the target geographies, scoped to the market context
- rival by rival: positioning, offering, and publicly stated pricing, funding
  and traction where the research supports it
- a comparison of the {offer_noun} to its real rivals: where it beats them,
  where it falls short, and what is genuinely unique about it
- strengths, weaknesses, opportunities and gaps relative to the named set
- which research areas returned evidence, and which returned little or nothing
- an explicit competitive positioning VERDICT for the {offer_noun}: strongly
  differentiated, moderately differentiated, weakly differentiated, or unclear
  -- and the evidence for it, including the counter-evidence it must survive
- open questions, contested claims and weak points

Keep the {offer_noun} as the subject and the competitive landscape as the
framing.

3. Also return `competitive_positioning_understanding`: a brief standalone
   synthesis of how the {offer_noun} is positioned vs. its real competitors.
   Target 40 words, never exceed 50.

4. Aim for roughly {word_count} words -- a brief, evidence-dense summary. Plain
   short sentences: state the findings and the understanding directly. Keep every
   concrete claim (numbers, names, citations), but cut reasoning bridges and
   anything a reader could recover from the other stages' findings.
"""


extract_instructions = """
You are an expert competitive analyst.

Classify the COMPETITIVE EVIDENCE in front of you into the structured
CompetitionExtraction record: the {offer_noun}'s ideal competitor set and how it
stacks up against them. This is a classification task, not a research task:
everything you need is in the material below, and none of it is to be invented.

{context}

Rules:
- competitors: identify the ideal competitor set -- between 3 and 5 real rivals
  (aim for 5, never fewer than 3 unless the research simply does not support
  them). Each must be grounded in the research:
  * name: the real product/company name, as it appears in the sources.
  * description: what they do and how they position, from the sources.
  * website: their official website URL ONLY if it appears in the research;
    otherwise use an empty string -- never invent a URL.
  * offering: key features/services they offer, from the sources.
  * positioning: how they position themselves in the market.
  * comparison: how the {offer_noun} compares to this competitor -- where it
    wins, where it loses.
  * feature_flags: for each of the {offer_noun}'s features (from its OWN
    material block), whether this competitor also offers it -- a real JSON
    object mapping feature name to true/false.
  Do NOT pad the list with generic names -- every competitor must be real and
  defensible from the sources. Scope the set to the market the context
  describes (category, buyer, geographies): rivals from unrelated markets do
  not belong.
- strengths: where the {offer_noun} meets or beats the competitive standard.
- weaknesses: where the {offer_noun} falls short of its rivals / the standard.
- opportunities: gaps in the competitive landscape the {offer_noun} could
  exploit.
- differentiators: things that genuinely set the {offer_noun} apart from the
  competitors named.
- Only state what the sources actually support. If an area is genuinely thin,
  return an empty list rather than inventing claims.

JSON discipline: every list field must be a real JSON array and every object
field (feature_flags) a real JSON object -- no double-serialized strings. For
optional string fields that do not apply, use an empty string ""; never null
and never omit the key. This record is validated against a strict schema.
"""


def _competition_context(state: CompetitionSessionState, bundles: list) -> str:
    """The evidence the planner, extractor and writer read: the offer's own
    material first (budget_context protects the first chunk), then the sibling
    stages' findings (Sources stripped), the structured market context, and the
    retrieved competition bundles.
    """
    return budget_context(
        [
            _offer_material(state),
            _sibling_block(
                "DOMAIN FINDINGS",
                state.get("offer_findings"),
                state.get("offer_domain_fit_understanding"),
            ),
            _sibling_block(
                "MARKET FINDINGS",
                state.get("market_findings"),
                state.get("product_market_fit_understanding"),
            ),
            f"### MARKET CONTEXT (STRUCTURED)\n{_market_context_block(state)}",
            *(_render_bundle(b) for b in bundles),
        ],
        label="competition research",
    )


def create_tasks_research(state: CompetitionSessionState) -> dict:
    """Plan the competition research: read what the session already knows
    (offer, domain, market), name what is missing.

    Fails loudly. A planner failure means there is nothing to research, and
    substituting a default task would produce a report-shaped hole that reads
    as a finished analysis. Same policy as the offer and market stages.
    """
    offer_noun = _offer_noun(state)
    specialist = _competition_specialist_for(state)
    lens = _specialist_lens(specialist, offer_noun)

    system_message = create_tasks_instructions.format(
        specialist_name=specialist.name if specialist else "a competitive analyst",
        specialist_role=specialist.role if specialist else f"{offer_noun} competition analyst",
        specialist_affiliation=specialist.affiliation if specialist else "independent",
        specialist_description=specialist.description if specialist else lens,
        offer_noun=offer_noun,
        offer_name=state.get("offer_name") or f"Unknown {offer_noun}",
        offer_type=state.get("offer_type") or "product",
        offer_description=state.get("offer_description") or "(not captured)",
        target_market=", ".join(state.get("target_market") or []) or "(not captured)",
        known_facts=_known_facts(state),
        sibling_context=_competition_context(state, []),
    )

    plan = invoke_structured_with_fallback(
        messages=[
            SystemMessage(content=system_message),
            SystemMessage(content="Plan the research tasks now."),
        ],
        schema=TaskList,
        log_label="create_tasks_research",
        # Planning on a closed schema, like search-query generation, is not the
        # deliberation that justifies the flagship thinking cost. Same gate the
        # offer and market planners run under.
        thinking=False,
    )

    tasks = list(plan.tasks or [])[:MAX_RESEARCH_TASKS]
    print(f"create_tasks_research: planned {len(tasks)} competition research task(s)")
    for i, task in enumerate(tasks, start=1):
        print(f"  {i}. {task.area} ({len(task.queries or [])} queries)")

    return {"competition_tasks": plan.model_copy(update={"tasks": tasks})}


def _research_one(task: ResearchTask) -> TaskResearchBundle:
    """Run a single competition research task end to end: search, dedupe, distil, bundle.

    Runs on a worker thread, so it takes no state and shares nothing mutable.

    RECENCY: every search is passed start_published_date = today -
    market_recency_days, the same window the interview-era understand_competition
    uses. Current rivals, current pricing, current positioning are the point.
    """
    area = task.area or "unnamed area"
    cfg = Config()
    cutoff = _recency_cutoff(cfg.market_recency_days)
    issued: list[str] = []
    docs: list[dict] = []
    seen: set[str] = set()

    for query in task.queries or []:
        query = (query or "").strip()
        if not query:
            continue
        issued.append(query)
        try:
            results = search_and_scrape(
                query,
                cfg,
                num_results=SEARCH_RESULTS_PER_QUERY,
                start_published_date=cutoff,
            )
        except Exception as exc:  # noqa: BLE001 - one dead query must not kill the task
            print(f"conduct_research: query failed ({area}): {query} -> {exc}")
            continue
        for doc in results or []:
            url = doc.get("url") or ""
            if url and url in seen:
                continue
            if url:
                seen.add(url)
            docs.append(doc)
        # The prompt asks the planner to order queries specific-first with a
        # broad fallback last, so stopping here is the fallback working as
        # designed rather than queries being discarded.
        if docs:
            break

    # Distillation is input-bound, so trim each page to the substantive front
    # before condensing. The note output cap inside distill_document is
    # untouched; only the bytes fed to the cheap model shrink.
    docs = [
        {**d, "text": _truncate_to_tokens(d.get("text") or "", DISTILL_INPUT_TOKEN_CAP)}
        for d in docs
    ]

    if not docs:
        return TaskResearchBundle(
            task_id=area,
            area=area,
            objective=task.objective or "",
            round=1,
            queries=issued,
            search_failed=True,
        )

    notes = distill_documents(
        docs,
        focus=(
            f"Condense for the research objective: {task.objective} "
            f"(competition area: {area}). Keep named competitors, positioning, "
            f"pricing, funding, traction, dates and geographies. Report what the "
            f"rivals do, not opinions."
        ),
        log_label=f"conduct_research:{area}",
    )

    return TaskResearchBundle(
        task_id=area,
        area=area,
        objective=task.objective or "",
        round=1,
        queries=issued,
        notes=notes,
        sources=[d.get("url") or "" for d in docs if d.get("url")],
    )


def conduct_research(state: CompetitionSessionState) -> dict:
    """Run every planned task and append one bundle per task to `competition_task_research`.

    The fan-out is an internal thread pool rather than a LangGraph `Send`
    fan-out, for the same reasons as the offer and market stages: pool.map
    preserves plan order, and a per-task try/except gives the same failure
    isolation inside one node.
    """
    plan = state.get("competition_tasks")
    tasks = list(plan.tasks or []) if plan else []
    if not tasks:
        print("conduct_research: no tasks planned, nothing to research")
        return {"competition_task_research": []}

    print(f"conduct_research: plan\n{_render_task_plan(tasks)}")

    workers = min(len(tasks), TASK_RESEARCH_MAX_WORKERS)
    print(f"conduct_research: running {len(tasks)} task(s) over {workers} worker(s)")

    def _guarded(task: ResearchTask) -> TaskResearchBundle:
        try:
            return _research_one(task)
        except Exception as exc:  # noqa: BLE001 - a dead task is a gap, not a crash
            print(f"conduct_research: task failed ({task.area}): {exc}")
            return TaskResearchBundle(
                task_id=task.area or "unnamed area",
                area=task.area or "unnamed area",
                objective=task.objective or "",
                round=1,
                queries=[],
                search_failed=True,
            )

    with ThreadPoolExecutor(max_workers=workers) as pool:
        bundles = list(pool.map(_guarded, tasks))

    for bundle in bundles:
        status = "EMPTY" if bundle.search_failed else f"{len(bundle.sources)} source(s)"
        print(f"  {bundle.area}: {status}")

    return {"competition_task_research": bundles}


def extract_competition_data(state: CompetitionSessionState) -> dict:
    """Classify the competitive evidence into the structured CompetitionExtraction
    record: the 3-5 competitor set plus the offer's SWOD.

    A cheap-tier classification pass (thinking off) over the same evidence the
    writer reasons from, with two interview-faithful hardening behaviours
    in-node:

    - the competitor set is clamped to 5 (the schema hint is a suggestion; this
      is the hard stop), with a warning -- never padding -- when the evidence
      supports fewer than 3;
    - each competitor's stated website is probed with a light scrape (the
      interview's verify_competitors step): hard failures are dropped, and
      name-grounded competitors without a URL are kept.

    SOFT-FAILS on purpose, like the market stage's extractor: the narrative
    findings are the pipeline's product, and losing the structured competitor
    set must not sink a run whose notes are already written.
    """
    bundles = list(state.get("competition_task_research") or [])
    context = _competition_context(state, bundles)

    system_message = extract_instructions.format(
        offer_noun=_offer_noun(state), context=context
    )

    try:
        extraction = invoke_structured_with_fallback(
            messages=[
                SystemMessage(content=system_message),
                SystemMessage(content="Extract the structured competitive record now."),
            ],
            schema=CompetitionExtraction,
            log_label="extract_competition_data",
            # Closed-schema classification of evidence already in hand --
            # exactly the cheap-tier workload llm/main.py's thinking gate
            # reserves for thinking-off calls.
            thinking=False,
        )
    except Exception as exc:  # noqa: BLE001 - soft-fail by design, see docstring
        print(f"extract_competition_data: failed ({exc}); competition_data left unset")
        return {}

    # Hard ceiling on the set the schema suggests. Same philosophy as
    # MAX_RESEARCH_TASKS: a schema hint is a suggestion, the clamp is the bound.
    competitors = list(extraction.competitors or [])[:5]
    if len(competitors) < 3:
        print(
            f"extract_competition_data: only {len(competitors)} competitor(s) "
            f"extracted -- keeping the defensible set, not inventing more"
        )

    # The interview's verify_competitors step, kept in-node: a competitor whose
    # stated website hard-fails to scrape is dropped (its URL would propagate
    # into ICP-facing data as a dead link). Name-grounded competitors without a
    # URL are kept -- they were grounded in the sources, not the link.
    cfg = Config()
    kept = []
    for comp in competitors:
        if comp.website:
            try:
                scrape_url(comp.website, cfg)
                kept.append(comp)
            except Exception as exc:  # noqa: BLE001 - per-competitor, soft
                print(f"extract_competition_data: dropping {comp.name!r} -- website failed to resolve: {exc}")
        else:
            kept.append(comp)

    extraction = extraction.model_copy(update={"competitors": kept})
    print(
        f"extract_competition_data: {len(kept)} verified competitor(s) "
        f"({len(competitors) - len(kept)} dropped for dead URLs)"
    )
    return {"competition_data": extraction}


def note_down_record(state: CompetitionSessionState) -> dict:
    """Read the offer's own material, the sibling context, the structured
    competitor set and every competition bundle; write the notes.

    Runs AFTER the extractor -- deliberately the reverse of the market stage --
    so the writer is anchored on the verified competitor set: the notes name
    the same rivals, and the positioning verdict can be judged against them.

    Fails loudly. These fields are the pipeline's core product, and a
    half-written synthesis that still sets `competition_complete` would let the
    section writer build on nothing.
    """
    offer_noun = _offer_noun(state)
    lens = _specialist_lens(_competition_specialist_for(state), offer_noun)
    bundles = list(state.get("competition_task_research") or [])
    context = _competition_context(state, bundles)

    # The canonical source list: everything this run actually retrieved, once.
    # Fed to the writer as the only things it may cite, and appended verbatim
    # after its notes, so the ### Sources contract holds even when the model
    # drops the trailing instruction, and fabricated citations become
    # structurally impossible.
    source_urls = _dedupe_sources(bundles)
    auditable_sources = "\n".join(
        f"[{i}] {url}" for i, url in enumerate(source_urls, start=1)
    ) or "(no source was retrieved for any research area)"

    system_message = record_instructions.format(
        offer_noun=offer_noun,
        offer_nouns=_offer_nouns(state),
        specialist_lens=lens,
        competitor_set=_competitor_names(state),
        auditable_sources=auditable_sources,
        context=context,
        word_count=COMPETITION_FINDINGS_WORD_COUNT,
    )

    notes = invoke_structured_with_fallback(
        messages=[
            SystemMessage(content=system_message),
            SystemMessage(content="Write the competitive notes now."),
        ],
        schema=CompetitionFindings,
        log_label="note_down_record",
        # The findings writer summarises already-distilled notes -- the
        # "summarisation of already-distilled notes" workload llm/main.py's
        # thinking gate explicitly classifies as NOT the reasoning that
        # justifies the measured 3.9x thinking cost. Same gate all four
        # pipelines run their findings writers under.
        thinking=False,
    )

    findings = (notes.findings or "").strip()
    positioning = (notes.competitive_positioning_understanding or "").strip()

    # The schema asks for 40 words, never more than 50; an LLM cannot be relied
    # on to hit that on its own (the market twin once returned 53), and the
    # bound is load-bearing for the report section writer. So it is clamped
    # here, the same way the task count is clamped -- a hard stop in the
    # harness rather than another prompt instruction.
    positioning_words = positioning.split()
    if len(positioning_words) > 50:
        positioning = " ".join(positioning_words[:50])
        print(
            f"note_down_record: positioning understanding clamped from "
            f"{len(positioning_words)} to 50 words"
        )

    # Same hard-stop philosophy for the notes body: the prompt targets
    # COMPETITION_FINDINGS_WORD_COUNT, but an LLM cannot be relied on to hold to
    # it (the pre-brevity writer once returned ~780 words against a 400 target).
    # Clamped BEFORE the harness-built Sources block is appended, so the
    # citation contract is never truncated.
    findings_words = findings.split()
    if len(findings_words) > COMPETITION_FINDINGS_WORD_CAP:
        findings = " ".join(findings_words[:COMPETITION_FINDINGS_WORD_CAP])
        print(
            f"note_down_record: findings clamped from {len(findings_words)} "
            f"to {COMPETITION_FINDINGS_WORD_CAP} words"
        )

    # Append the harness-built Sources block. The writer was told not to
    # reproduce it (the same list was in its prompt to cite against), so the
    # findings ship with exactly one, verifiable block.
    sources_block = _sources_section(source_urls)
    if findings and sources_block:
        findings = f"{findings}\n\n{sources_block}"

    print(
        f"note_down_record: {len(bundles)} bundle(s) read, "
        f"{len(findings.split())} words of notes, "
        f"positioning understanding in {len(positioning.split())} words"
    )

    return {
        "competition_findings": findings,
        "competitive_positioning_understanding": positioning,
        "competition_complete": True,
    }


def build_competition_graph(checkpointer: bool = True):
    """create_tasks_research -> conduct_research -> extract_competition_data -> note_down_record.

    Extract runs BEFORE the writer (deliberately the reverse of the market
    graph): the structured competitor set is the load-bearing fact list, and
    the writer is anchored on it rather than the other way round. No
    conditional edges and no cycles, on purpose. See the module docstring.
    """
    builder = StateGraph(CompetitionSessionState)

    # -- Nodes --
    builder.add_node("create_tasks_research", create_tasks_research)
    builder.add_node("conduct_research", conduct_research)
    builder.add_node("extract_competition_data", extract_competition_data)
    builder.add_node("note_down_record", note_down_record)

    # -- Edges --
    builder.add_edge(START, "create_tasks_research")
    builder.add_edge("create_tasks_research", "conduct_research")
    builder.add_edge("conduct_research", "extract_competition_data")
    builder.add_edge("extract_competition_data", "note_down_record")
    builder.add_edge("note_down_record", END)

    return builder.compile()