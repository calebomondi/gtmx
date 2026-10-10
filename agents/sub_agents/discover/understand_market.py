"""
Market Understanding.

The market stage, as an explicit research pipeline rather than a multi-turn
interview, borrowed from the offer-domain pipeline in `understand_offer`:

    create_tasks_research  -> plan 3-5 market research objectives
    conduct_research       -> run them, one bundle of evidence per objective
    note_down_record       -> write the market notes + the fit-understanding
    extract_market_data    -> classify the evidence into the structured record

Deliberately LINEAR, for the same reason the offer stage is: the pipeline's
product is the findings + fit-understanding, a hard cost bound is worth more
here than marginal depth, and every extra round multiplies Exa calls and
distillation. There is no re-planning loop and no sufficiency gate; a future
change that adds one needs a round counter on the state and a back edge, and its
absence here is a decision, not an oversight.

The one deliberate departure from the offer stage is RECENCY. Domain conventions
are stable and the offer stage does not recency-gate its searches; markets
decay. Demand, pricing norms, channels and adoption barriers change on a
year-ish horizon, so every market search passes
`start_published_date = today - Config().market_recency_days` (default 365),
the same window the interview-era understand_market and understand_competition
use. A market verdict built from stale sources is worse than a thin one.

The single cosplayed expert is the market specialist, selected out of
`specialists` by `Specialist.domain == "market"`. The field exists precisely so
this is a lookup rather than list-position guesswork, and reusing the offer
stage's `_specialist_for` would cosplay the WRONG persona (it selects by
offer_type, product/service).

Search is brand-free by design, for the same reason as the offer stage. The
offer's own material is authoritative for what the offer IS; the research
supplies the MARKET to judge it against. Letting the planner put the brand in a
query would turn the market stage into a study of the company's own marketing
copy.

The `extract_market_data` node is the compatibility layer with the gtmx
consumers built against the interview-era `MarketExtraction`: buyer_type,
pricing, channels, a structured market-fit verdict. It is a cheap-tier
classification pass over the same evidence and SOFT-FAILS on purpose -- the
narrative findings are the pipeline's product, and losing the structured record
must not sink a run whose notes are already written.
"""

from concurrent.futures import ThreadPoolExecutor
from datetime import date, timedelta
from typing import Optional

from langgraph.graph import START, END, StateGraph
from langchain_core.messages import SystemMessage

from config import Config
from agents.llm.main import invoke_structured_with_fallback
from agents.context_budget import _truncate_to_tokens, budget_context, distill_documents
from agents.states import MarketExtraction, MarketFindings, TaskResearchBundle
from data_sources.scraping.exa import search_and_scrape

from ..schema_states import MarketSessionState, ResearchTask, Specialist, TaskList
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

# Matches the offer pipeline's search budget. Market research is additionally
# recency-gated below -- current conditions are the point of this stage.
SEARCH_RESULTS_PER_QUERY = 3

# Tasks fan out here, and each task's own distillation fans out again inside
# distill_documents (4 workers). Left unthrottled that is up to 20 concurrent
# cheap-model calls against a single provider account -- the burst
# context_budget.py warns causes mid-run throttling. Four keeps every task in
# one wave while staying under the provider's token-per-minute window; the Exa
# round-trips ride the same pool, and research wall clock is the slowest task
# rather than the sum of two waves. See understand_offer for the full rationale.
TASK_RESEARCH_MAX_WORKERS = 4

# How much of each scraped page is fed to the distiller. Same rationale as the
# offer stage: a typical page is ~11k tokens of mostly boilerplate, and
# truncating the INPUT (not the note) is what keeps distillation in the
# few-second cheap-tier regime.
DISTILL_INPUT_TOKEN_CAP = 4_000

# Market findings feed the report's market section. MarketSessionState carries
# no section_word_count, so this is the local target rather than a value
# inherited from the parent, matching how understand_offer sets its own. The
# notes are deliberately brief -- a distillation of the distilled bundles -- so
# the target is 150 words with a hard harness cap at 300 words, 2x the target.
MARKET_FINDINGS_WORD_COUNT = 150
MARKET_FINDINGS_WORD_CAP = 300

# How much of each bundle's distilled notes the writer and the extractor read.
# Same policy as understand_offer's WRITER_NOTES_TOKEN_CAP: the notes are
# already condensed once, and truncating at render time keeps every area's voice
# while bounding the input-proportional cost of the two LLM calls that consume
# them.
WRITER_NOTES_TOKEN_CAP = 800


def _recency_cutoff(days: int) -> str:
    """ISO date (YYYY-MM-DD) for the oldest source the market research may use."""
    return (date.today() - timedelta(days=days)).isoformat()


def _market_specialist_for(state: MarketSessionState) -> Optional[Specialist]:
    """Pick the market specialist out of the team.

    `Specialist.domain == "market"` exists precisely so this is a lookup rather
    than a guess at list position. The fallbacks are for a hand-built team that
    skipped the field; they degrade rather than raising, because a persona is
    presentation, not correctness, and losing the whole market stage over a
    missing name would be the wrong trade. Note this deliberately does NOT
    select by offer_type the way understand_offer's _specialist_for does: the
    market stage is about the market, not the offer's own domain.
    """
    specialists = [s for s in (state.get("specialists") or []) if s]
    if not specialists:
        return None
    for s in specialists:
        if getattr(s, "domain", None) == "market":
            return s
    for s in specialists:
        if getattr(s, "domain", None) in ("product", "service"):
            return s
    return specialists[0]


create_tasks_instructions = """
You are {specialist_name}, a {specialist_role} working in {specialist_affiliation}.

YOUR LENS
{specialist_description}

You are the market specialist. You know how this {offer_noun}'s category behaves
in the markets it targets, and you have the {offer_noun}'s own material in front
of you. Before you can judge how well it fits its market -- who actually buys,
what they pay, and why adoption happens -- you need evidence you do not have yet.

OFFER
- name          : {offer_name}
- type          : {offer_type}
- description   : {offer_description}
- target market : {target_market}

KNOWN FACTS (what the {offer_noun}'s own material already establishes. Treat it as
ground truth. Do not re-litigate it and do not research it as if it were open.)
{known_facts}

GOAL
Plan the research that closes the gap between what you already know about this
{offer_noun} and what you need to know about the MARKET it sells into -- the
buyers, the demand, what they pay, how the category is bought, and what stands
between the target audience and adoption. You are planning, not answering.
Nothing has been searched yet, and the results come back to you afterwards for
you to read.

Each task is ONE objective that a set of public web sources could genuinely
settle, in an area such as:
- who buys: the buyer segments for this category in the target markets, the
  B2B/B2C split, and the buyer roles that actually make the purchase
- current demand and market readiness for the category, and whether demand is
  growing, flat or declining -- with the honest near-term outlook
- pricing norms in the category: the price points and tiers buyers expect in the
  target markets, and what buyers are willing to pay
- how the category is bought and sold: the channels, marketplaces, platforms and
  procurement paths that decide purchases
- category conventions and adoption barriers: what "good" looks like to buyers
  in this category, and what blocks adoption (trust, switching cost, cost,
  regulatory, awareness)
- how all of the above differs across the target geographies

The research MUST be current: markets change. Favour recent sources, because a
verdict built on stale conditions is worse than a thin one.

SCOPE: what this research is NOT
- The {offer_noun}'s technical domain and how it works are researched separately.
  Do not plan tasks for them.
- Competitors, their positioning, their pricing and their customer complaints
  are researched separately. Do not plan tasks for them.
- Product/service-market fit is YOUR judgment at the end, after the evidence is
  in. It is not something a web search settles, so do not plan a task for it.

RULES
1. Plan between 3 and 5 tasks. Fewer leaves the picture too thin to write from;
   more cannot be researched well in a single round.
2. Give each task exactly 2 independent queries, ordered most specific first. The
   second is the broad fallback, used only if the specific one returns nothing, so
   it should be broad enough to always return something.
3. NEVER put the {offer_noun}'s name or its brand in a query. Research the
   MARKET/CATEGORY, so the sources describe the category rather than this
   {offer_noun} or its own marketing claims.
4. Scope queries to the target markets where they are known, because how a
   market actually behaves differs by geography.
5. Every objective is a research goal, not a search string. It must be specific
   enough that "this task came back with nothing" is itself a meaningful finding.
6. Do not assert what you will find, and do not invent facts about the
   {offer_noun} or the market. You are choosing what to look up.

Return only the structured task list. No commentary.
"""


record_instructions = """
You are an expert market analyst.

Write the RESEARCH NOTES that ground this {offer_noun} in the MARKET it sells
into, from the {offer_noun}'s own material plus the research that was carried
out for it.

These are notes, not a finished report section. A single report is written later
by someone who will also have the domain and competitive analyses in hand, so:

- Write NOTES, not report prose. No report title, no "# Heading" scaffolding.
- Be specific and evidence-dense. Another writer cannot recover what you leave
  out, but they can trim what you hand them.
- Keep every concrete claim: named segments, price points, marketplaces,
  channels, growth figures, dates, organisations and geographies. Those are what
  get cited downstream.
- Be brief. These notes are conclusions plus the claims that evidence them, not a
  ledger of everything retrieved. Cut reasoning bridges, elaboration, and anything
  the report writer can recover from the sibling stages. When in doubt, leave it
  out.
- Say plainly where the evidence is thin or contested. Do not smooth over a gap.
- If a research area returned nothing, name it and state that the area is
  therefore still open. A visible gap is worth more than a papered-over one.

Two kinds of material are in front of you, and they are not interchangeable:

1. The {offer_noun}'s OWN MATERIAL, labelled as such, is AUTHORITATIVE. It is the
   source for what the {offer_noun} is, who it is for, and the problem it solves.
   Where the research contradicts it, the {offer_noun}'s own material wins and
   the contradiction is worth noting.

2. The RESEARCH BUNDLES, one per research objective, describe the MARKET the
   {offer_noun} sells into: who buys, demand and readiness, pricing norms,
   channels, conventions and adoption barriers. These are independent of the
   {offer_noun} and frequently do not mention it at all. That is expected and
   correct.

SPECIALIST LENS
{specialist_lens}

CITATIONS
Every inline citation must be a bracketed number from this list:

{auditable_sources}

- Cite with the exact numbers above, e.g. "on-demand buyers in the Gulf expect
  delivery within days [2]".
- Never cite a URL that is not in this list. The list is the full, deduplicated
  set of pages this run actually retrieved; anything else is fabrication.
- The {offer_noun}'s own material has no URL and may be cited as
  "[offer material]".
- Do NOT reproduce the list at the end of your notes. The harness appends the
  ### Sources section from it automatically, so a second copy would be
  redundant.

MATERIAL AND RESEARCH

{context}

1. Separate what is fact about the {offer_noun} itself from what describes the
   market it sells into. Do not blur the two into a single undifferentiated
   account.

2. Organise the notes with markdown sub-headers of your choosing (###). Cover:
- the market definition: the category, who buys it (buyer type and segments),
  and the target audience across the target geographies
- current demand and market readiness: how much the category is wanted in the
  target markets, the demand evidence (numbers, dates), and the
  growth/decline trajectory
- pricing norms and willingness to pay: the price points and tiers buyers
  expect, and the budget norms that govern purchase decisions
- channels and distribution: how the category is bought and sold in the target
  markets
- category conventions and adoption barriers: what "good" looks like to buyers,
  and what stands between the target audience and adoption
- an explicit product-market fit VERDICT for the {offer_noun}: strong,
  moderate, weak, or unclear -- and the evidence for it, including the
  counter-evidence it must survive. Fit is a judgment; say what the evidence
  supports and what it does not
- which research areas returned evidence, and which returned little or nothing
- open questions and weak points

Keep the {offer_noun}'s market as the subject and the fit as the framing.

3. Also return `product_market_fit_understanding`: a brief standalone synthesis
   of how well the {offer_noun} fits the market its evidence describes. Target
   40 words, never exceed 50.

4. Aim for roughly {word_count} words -- a brief, evidence-dense summary. Plain
   short sentences: state the findings and the understanding directly. Keep every
   concrete claim (numbers, names, citations), but cut reasoning bridges and
   anything a reader could recover from the other stages' findings.
"""


extract_instructions = """
You are an expert market analyst.

Classify the MARKET EVIDENCE in front of you into the structured MarketExtraction
record. This is a classification task, not a research task: everything you need
is in the material below, and none of it is to be invented.

{context}

FINDINGS WRITER'S VERDICT
{fit_verdict}

The findings writer above reasoned over this same evidence. Treat that verdict as
your default: keep market_fit and market_fit_reasoning consistent with it unless
the evidence in front of you contradicts it -- and if it does, say exactly why in
market_fit_reasoning.

Rules:
- buyer_type, category, growth_outlook and market_fit come from closed lists.
  Pick one; when the evidence is mixed, pick the best-supported value. If there
  is no evidence, leave the field empty rather than guessing.
- pricing: list the price tiers the evidence supports, one entry per tier. `tier`
  names the tier. If the offer's own material states prices, set pricing_source to
  "site"; otherwise give the market rates the research supports
  ("market_suggestion"). For any `monthly_sub`/`yearly_sub` that does not apply to
  a tier (e.g. a one-time purchase), use an empty string "" -- never null, never
  omit the key. `features` is a list; use [] when a tier has no feature list. A
  partial tier is better than a dropped one.
- target_geo and distribution_channels come from the evidence; leave them empty
  when the evidence does not support an entry.
- market_fit is the fit verdict and market_fit_reasoning the evidence-based why;
  they must be consistent with what the material actually shows, including any
  counter-evidence.
"""


# Loose snapshot fields the planner is shown verbatim, alongside the offer's own
# material -- same set as the offer pipeline, so discovery signal is preserved.
# (The offer's `_known_facts` helper renders these; it is imported above.)


def _writer_context(state: MarketSessionState, bundles: list) -> str:
    """The evidence both the writer and the extractor read.

    budget_context, not a bare join. _render_bundle already caps each bundle's
    notes at WRITER_NOTES_TOKEN_CAP, so the per-bundle cost here is fixed, but
    the offer material and the header/source lines still vary, and a run that
    doubled the task count would otherwise overflow at this last call, having
    already paid for all of it. The offer's own material goes first because
    budget_context protects the first chunk, which is exactly the right chunk
    to protect.
    """
    return budget_context(
        [_offer_material(state), *(_render_bundle(b) for b in bundles)],
        label="market research",
    )


def create_tasks_research(state: MarketSessionState) -> dict:
    """Plan the market research: read what is known, name what is missing.

    Fails loudly. A planner failure means there is nothing to research, and
    substituting a default task would produce a report-shaped hole that reads as
    a finished analysis. That is the same policy create_specialists and the
    offer stage take.
    """
    offer_noun = _offer_noun(state)
    specialist = _market_specialist_for(state)
    lens = _specialist_lens(specialist, offer_noun)

    system_message = create_tasks_instructions.format(
        specialist_name=specialist.name if specialist else "a market analyst",
        specialist_role=specialist.role if specialist else f"{offer_noun} market analyst",
        specialist_affiliation=specialist.affiliation if specialist else "independent",
        specialist_description=specialist.description if specialist else lens,
        offer_noun=offer_noun,
        offer_name=state.get("offer_name") or f"Unknown {offer_noun}",
        offer_type=state.get("offer_type") or "product",
        offer_description=state.get("offer_description") or "(not captured)",
        target_market=", ".join(state.get("target_market") or []) or "(not captured)",
        known_facts=_known_facts(state),
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
        # offer planner runs under.
        thinking=False,
    )

    tasks = list(plan.tasks or [])[:MAX_RESEARCH_TASKS]
    print(f"create_tasks_research: planned {len(tasks)} market research task(s)")
    for i, task in enumerate(tasks, start=1):
        print(f"  {i}. {task.area} ({len(task.queries or [])} queries)")

    return {"market_tasks": plan.model_copy(update={"tasks": tasks})}


def _research_one(task: ResearchTask) -> TaskResearchBundle:
    """Run a single market research task end to end: search, dedupe, distil, bundle.

    Runs on a worker thread, so it takes no state and shares nothing mutable.

    The one difference from the offer pipeline's _research_one is RECENCY:
    every search is passed start_published_date = today - market_recency_days.
    Markets decay, so current conditions are the point of this stage.
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
    # untouched; only the bytes fed to the cheap model shrink. A copy, never the
    # shared search result -- the same docs feed the sources list below.
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
            f"(market area: {area}). Keep named segments, price points, channels, "
            f"marketplaces, numbers, dates and geographies. Report what the market "
            f"does, not opinions."
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


def conduct_research(state: MarketSessionState) -> dict:
    """Run every planned task and append one bundle per task to `market_task_research`.

    The fan-out is an internal thread pool rather than a LangGraph `Send`
    fan-out, for the same reasons as the offer stage: pool.map preserves plan
    order (so the same plan always produces the same bundle order), and a
    per-task try/except gives the same failure isolation inside one node.
    """
    plan = state.get("market_tasks")
    tasks = list(plan.tasks or []) if plan else []
    if not tasks:
        print("conduct_research: no tasks planned, nothing to research")
        return {"market_task_research": []}

    # Logged in full rather than as a count, because a bad query is only visible
    # once you can read it, and the plan is the one artefact a failing run's
    # author cannot reconstruct.
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

    return {"market_task_research": bundles}


def note_down_record(state: MarketSessionState) -> dict:
    """Read the offer's own material and every market bundle, write the notes.

    The two inputs are kept distinct all the way through, because they answer
    different questions: the offer's own material says what this product IS, and
    the bundles say what its market is like. The writer has to hold both in view
    to say anything useful about market fit.

    Fails loudly. These fields are the pipeline's core product, and a
    half-written synthesis that still sets `market_complete` would let the
    section writer build on nothing.
    """
    offer_noun = _offer_noun(state)
    lens = _specialist_lens(_market_specialist_for(state), offer_noun)
    bundles = list(state.get("market_task_research") or [])
    if not bundles:
        # Do not call the writer when there is nothing to write about.
        return {
            "market_findings": "No research bundles were produced.",
            "product_market_fit_understanding": "",
            "market_complete": False,
        }

    context = _writer_context(state, bundles)

    # The canonical source list: everything this run actually retrieved, once.
    # Fed to the writer as the only things it may cite, and appended verbatim
    # after its notes, so the ### Sources contract holds even when the model
    # drops the trailing instruction, and fabricated citations become
    # structurally impossible. Same determinism trade as the offer stage.
    source_urls = _dedupe_sources(bundles)
    auditable_sources = "\n".join(
        f"[{i}] {url}" for i, url in enumerate(source_urls, start=1)
    ) or "(no source was retrieved for any research area)"

    system_message = record_instructions.format(
        offer_noun=offer_noun,
        offer_nouns=_offer_nouns(state),
        specialist_lens=lens,
        auditable_sources=auditable_sources,
        context=context,
        word_count=MARKET_FINDINGS_WORD_COUNT,
    )

    notes = invoke_structured_with_fallback(
        messages=[
            SystemMessage(content=system_message),
            SystemMessage(content="Write the market notes now."),
        ],
        schema=MarketFindings,
        log_label="note_down_record",
        # The findings writer summarises already-distilled notes -- the
        # "summarisation of already-distilled notes" workload llm/main.py's
        # thinking gate explicitly classifies as NOT the reasoning that
        # justifies the measured 3.9x thinking cost. The deliberation budget
        # belongs to interview answers and the report section writer, not a
        # second trip through notes that were already condensed once.
        thinking=False,
    )

    findings = (notes.findings or "").strip()
    fit = (notes.product_market_fit_understanding or "").strip()

    # The schema asks for 40 words, never more than 50; an LLM cannot be relied
    # on to hit that on its own (this model once returned 53), and the bound is
    # load-bearing for the report section writer. So it is clamped here, the
    # same way the task count is clamped -- a hard stop in the harness rather
    # than another prompt instruction.
    fit_words = fit.split()
    if len(fit_words) > 50:
        fit = " ".join(fit_words[:50])
        print(
            f"note_down_record: fit understanding clamped from {len(fit_words)} "
            f"to 50 words"
        )

    # Same hard-stop philosophy for the notes body: the prompt targets
    # MARKET_FINDINGS_WORD_COUNT, but an LLM cannot be relied on to hold to it
    # (the pre-brevity writer once returned ~650 words against a 400 target).
    # Clamped BEFORE the harness-built Sources block is appended, so the
    # citation contract is never truncated.
    findings_words = findings.split()
    if len(findings_words) > MARKET_FINDINGS_WORD_CAP:
        findings = " ".join(findings_words[:MARKET_FINDINGS_WORD_CAP])
        print(
            f"note_down_record: findings clamped from {len(findings_words)} "
            f"to {MARKET_FINDINGS_WORD_CAP} words"
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
        f"fit understanding in {len(fit.split())} words"
    )

    # Do not set market_complete on an empty research run — it lets downstream
    # stages treat a silent failure as success.
    if not bundles:
        return {
            "market_findings": "No research bundles were produced.",
            "product_market_fit_understanding": "",
            "market_complete": False,
        }

    return {
        "market_findings": findings,
        "product_market_fit_understanding": fit,
        "market_complete": True,
    }


def extract_market_data(state: MarketSessionState) -> dict:
    """Classify the market evidence into the structured MarketExtraction record.

    A cheap-tier classification pass (thinking off) over the same evidence the
    writer reasoned from. This is the compatibility layer with the gtmx
    consumers built against the interview-era `market_data` -- competition
    briefing, ICP, the snapshot merge -- and it SOFT-FAILS: the narrative
    findings are the pipeline's product, and the structured record is
    auxiliary. A failure here logs and returns an empty update rather than
    crashing a run whose notes are already written.
    """
    bundles = list(state.get("market_task_research") or [])
    if not bundles:
        # Nothing to extract from.
        return {}
    context = _writer_context(state, bundles)
    # Anchor the structured verdict to the narrative one: both are syntheses of
    # the same evidence, and consumers read them together, so a silent
    # contradiction (narrative "moderate", structured "strong") would propagate
    # into the report. The extractor keeps the writer's verdict unless the
    # evidence contradicts it, and says so when it does.
    fit_verdict = (state.get("product_market_fit_understanding") or "").strip()
    if not fit_verdict:
        fit_verdict = "(the findings writer produced no standalone verdict)"

    system_message = extract_instructions.format(
        context=context,
        fit_verdict=fit_verdict,
    )

    try:
        extraction = invoke_structured_with_fallback(
            messages=[
                SystemMessage(content=system_message),
                SystemMessage(content="Extract the structured market record now."),
            ],
            schema=MarketExtraction,
            log_label="extract_market_data",
            # Closed-schema classification of evidence already in hand --
            # exactly the cheap-tier workload llm/main.py's thinking gate
            # reserves for thinking-off calls.
            thinking=False,
        )
    except Exception as exc:  # noqa: BLE001 - soft-fail by design, see docstring
        print(f"extract_market_data: failed ({exc}); market_data left unset")
        return {}

    print(
        f"extract_market_data: fit={getattr(extraction, 'market_fit', None)!r}, "
        f"buyer_type={getattr(extraction, 'buyer_type', None)!r}, "
        f"{len(getattr(extraction, 'pricing', None) or [])} pricing tier(s)"
    )
    return {"market_data": extraction}


def build_market_graph(checkpointer: bool = True):
    """create_tasks_research -> conduct_research -> note_down_record -> extract_market_data.

    No conditional edges and no cycles, on purpose. See the module docstring.
    """
    builder = StateGraph(MarketSessionState)

    # -- Nodes --
    builder.add_node("create_tasks_research", create_tasks_research)
    builder.add_node("conduct_research", conduct_research)
    builder.add_node("note_down_record", note_down_record)
    builder.add_node("extract_market_data", extract_market_data)

    # -- Edges --
    builder.add_edge(START, "create_tasks_research")
    builder.add_edge("create_tasks_research", "conduct_research")
    builder.add_edge("conduct_research", "note_down_record")
    builder.add_edge("note_down_record", "extract_market_data")
    builder.add_edge("extract_market_data", END)

    return builder.compile()