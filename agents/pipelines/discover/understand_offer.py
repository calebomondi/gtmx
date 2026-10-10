"""
Offer Domain Understanding.

The product/service domain stage, as an explicit three-step research pipeline
rather than a multi-turn interview:

    create_tasks_research  -> plan 3-5 research objectives
    conduct_research       -> run them, one bundle of evidence per objective
    note_down_record       -> write the domain notes + the fit-understanding

Deliberately LINEAR. There is no re-planning loop and no sufficiency gate. The
pipeline's product is the two findings fields, a hard cost bound is worth more
here than marginal depth, and every extra round multiplies Exa calls and
distillation. If a future change adds a re-plan loop, it needs a round counter on
the state and a back edge from note_down_record to create_tasks_research; the
absence here is a decision, not an oversight.

The single cosplayed expert is the offer's own domain specialist, selected out of
`specialists` by `Specialist.domain`. That is why the field exists: without it,
picking the right persona out of a four-person team is list-position guesswork.

Search is brand-free by design. The offer's own material is the authoritative
source for what the product IS; the research exists to supply the DOMAIN to judge
it against. Letting the planner put the brand in a query would turn the domain
stage into a study of the company's own marketing copy.
"""

import json
from concurrent.futures import ThreadPoolExecutor
from typing import Optional

from langgraph.graph import START, END, StateGraph
from langchain_core.messages import SystemMessage

from config import get_settings
from agents.llm.main import invoke_structured_with_fallback
from agents.context_budget import _truncate_to_tokens, budget_context, distill_documents
from agents.helpers import format_offer_material
from agents.schemas.offer import OfferDataSnapshot, ProductFindings, SnapshotFeature
from agents.schemas.research import TaskResearchBundle
from data_sources.scraping.exa import search_and_scrape

from agents.schemas.research import ResearchTask, Specialist, TaskList
from agents.schemas.sessions import OfferSessionState


# The planner is asked for 3-5; this is the hard stop. A schema hint is a
# suggestion, so the clamp is what actually bounds the fan-out cost of a run.
MAX_RESEARCH_TASKS = 5

# Matches understand_product's search budget. Domain conventions and architectures
# are stable, so this stage does NOT recency-gate the way market and competition do.
SEARCH_RESULTS_PER_QUERY = 3

# Tasks fan out here, and each task's own distillation fans out again inside
# distill_documents (4 workers). Left unthrottled that is up to 20 concurrent
# cheap-model calls against a single provider account, which is the burst
# context_budget.py warns causes mid-run throttling. Four was chosen not because
# that burst is safe but because the input-truncated distills below are short
# calls (a few seconds each on qwen-flash), so all tasks land in one wave and
# the per-call cost stays under the provider's token-per-minute window. The
# Exa round-trips ride the same pool, and research wall clock is the slowest
# task rather than the sum of two waves.
TASK_RESEARCH_MAX_WORKERS = 4

# How much of each scraped page is fed to the distiller. A typical page is
# ~11k tokens, the great majority navigation, cookie banners and boilerplate
# (see context_budget's module docstring), so the substantive head plus the
# focus-aware condensation carries the depth. Truncating the INPUT, not the
# note, is what turns a 14-20s qwen-flash call into a ~4-6s one: distillation
# is input-bound, and research wall clock is the slowest distill per task.
DISTILL_INPUT_TOKEN_CAP = 4_000

# Domain findings feed the report's domain section, which write_sections budgets
# at 400 words. The notes themselves are deliberately brief -- a distillation of
# the distilled bundles, not a second compendium -- so the target is 150 words
# with a hard harness cap at 300 words, 2x the target (same stop-in-the-harness
# philosophy as the understanding clamps below). OfferSessionState carries no
# section_word_count, so this is the local target rather than a value inherited
# from the parent.
DOMAIN_FINDINGS_WORD_COUNT = 150
DOMAIN_FINDINGS_WORD_CAP = 300

# How much of each bundle's distilled notes the writer's synthesis reads. The
# notes are already condensed once (each source block is capped at 1.8k tokens),
# and the writer produces one ~150-word notes doc from all four areas, so
# re-reading 2k+ tokens per area is throughput the synthesis does not use. The
# cap is applied per bundle at render time, before budget_context, so every area
# keeps a voice and no single area silently disappears. What drops is the tail of
# each area's evidence, which is the lowest-ranked Exa result -- the same
# drop policy the context budget already applies to search docs.
WRITER_NOTES_TOKEN_CAP = 800


create_tasks_instructions = """
You are {specialist_name}, a {specialist_role} working in {specialist_affiliation}.

YOUR LENS
{specialist_description}

You are the {offer_noun} domain specialist. You know the domain space this
{offer_noun} sits in, and you have the {offer_noun}'s own material in front of
you. Before you can judge how deeply it fits that domain, you need evidence you
do not have yet.

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
{offer_noun} and what you need to know about its DOMAIN in order to understand it
properly. You are planning, not answering. Nothing has been searched yet, and the
results come back to you afterwards for you to read.

Each task is ONE objective that a set of public web sources could genuinely
settle, in an area such as:
- the domain/category background a reader needs before they can judge the
  {offer_noun}: the terminology, the systems, and the standards in play
- the conventions, benchmarks and norms {offer_nouns} in this category are held
  to, and what "good" looks like to the people who buy or use them
- the technical mechanisms such {offer_nouns} are built on, and how those
  mechanisms actually work
- how {offer_nouns} in this category are expected to behave, deploy and operate,
  and what the established approaches are
- where the category is contested or unsettled, and what recent work has moved it

SCOPE: what this research is NOT
- Market demand, buyer segments, pricing norms and product-market fit are
  researched separately. Do not plan tasks for them.
- Competitors, their pricing, their positioning and their customer complaints
  are researched separately. Do not plan tasks for them.
Your tasks are about the DOMAIN SPACE and how the {offer_noun} sits inside it.

RULES
1. Plan between 3 and 5 tasks. Fewer leaves the picture too thin to write from;
   more cannot be researched well in a single round.
2. Give each task exactly 2 independent queries, ordered most specific first. The
   second is the broad fallback, used only if the specific one returns nothing, so
   it should be broad enough to always return something.
3. NEVER put the {offer_noun}'s name or its brand in a query. Research the
   DOMAIN/CATEGORY, so the sources describe the category rather than this
   {offer_noun} or its own marketing claims.
4. Scope queries to the target markets where they are known, because how a
   category actually works differs by geography.
5. Every objective is a research goal, not a search string. It must be specific
   enough that "this task came back with nothing" is itself a meaningful finding.
6. Do not assert what you will find, and do not invent facts about the
   {offer_noun} or the domain. You are choosing what to look up.

Return only the structured task list. No commentary.
"""


record_instructions = """
You are an expert technical analyst.

Write the RESEARCH NOTES that ground this {offer_noun} in its domain/category
space, from the {offer_noun}'s own material plus the research that was carried out
for it.

These are notes, not a finished report section. A single report is written later
by someone who will also have the market and competitive analyses in hand, so:

- Write NOTES, not report prose. No report title, no "# Heading" scaffolding.
- Be specific and evidence-dense. Another writer cannot recover what you leave
  out, but they can trim what you hand them.
- Keep every concrete claim: named technologies, architectures, standards, limits,
  latencies, numbers, dates, versions, named organisations and products. Those are
  what get cited downstream.
- Be brief. These notes are conclusions plus the claims that evidence them, not a
  ledger of everything retrieved. Cut reasoning bridges, elaboration, and anything
  the report writer can recover from the sibling stages. When in doubt, leave it
  out.
- Say plainly where the evidence is thin or contested. Do not smooth over a gap.
- If a research area returned nothing, name it and state that the area is
  therefore still open. A visible gap is worth more than a papered-over one.

Two kinds of material are in front of you, and they are not interchangeable:

1. The {offer_noun}'s OWN MATERIAL, labelled as such, is AUTHORITATIVE. It is the
   source for what the {offer_noun} is, how it works, {offer_features}, who it is
   for, and the problem it solves. Where the research contradicts it, the
   {offer_noun}'s own material wins and the contradiction is worth noting.

2. The RESEARCH BUNDLES, one per research objective, describe the DOMAIN/CATEGORY
   the {offer_noun} sits in: standards, architecture conventions, how {offer_nouns}
   in this category are expected to work, adjacent approaches. These are
   independent of the {offer_noun} and frequently do not mention it at all. That
   is expected and correct.

SPECIALIST LENS
{specialist_lens}

CITATIONS
Every inline citation must be a bracketed number from this list:

{auditable_sources}

- Cite with the exact numbers above, e.g. "markets expect 48-hour delivery [2]".
- Never cite a URL that is not in this list. The list is the full, deduplicated
  set of pages this run actually retrieved; anything else is fabrication.
- The {offer_noun}'s own material has no URL and may be cited as
  "[offer material]".
- Do NOT reproduce the list at the end of your notes. The harness appends the
  ### Sources section from it automatically, so a second copy would be redundant.

MATERIAL AND RESEARCH

{context}

1. Separate what is fact about the {offer_noun} itself from what describes the
   domain/category. Do not blur the two into a single undifferentiated account.

2. Organise the notes with markdown sub-headers of your choosing (###). Cover:
- the domain/category background a reader needs in order to judge the {offer_noun}
- what the {offer_noun} is and how it works mechanically, from its own material
- how the {offer_noun} fits its domain space: where it aligns with, extends,
  deviates from, or outpaces how {offer_nouns} in this category are expected to
  work and the standards they are held to. What is novel, interesting or
  surprising about it relative to the domain
- which research areas returned evidence, and which returned little or nothing
- open questions and weak points

Keep the {offer_noun} as the subject and the domain as the framing.

3. Also return `product_domain_understanding`: a brief standalone synthesis of the
   {offer_noun}'s fit within its domain. Target 40 words, never exceed 50.

4. Aim for roughly {word_count} words -- a brief, evidence-dense summary. Plain
   short sentences: state the findings and the understanding directly. Keep every
   concrete claim (numbers, names, citations), but cut reasoning bridges and
   anything a reader could recover from the other stages' findings.
"""


# Loose snapshot fields the planner is shown verbatim, alongside the offer's own
# material. The four the pipeline is seeded with (offer_type, offer_name,
# offer_description, target_market) are named in the prompt directly; the rest
# are what discovery additionally captured and would otherwise be dropped.
_KNOWN_FACT_KEYS = (
    "offer_name",
    "offer_type",
    "offer_description",
    "target_market",
    "problem",
    "solution",
    "target_users",
    "features",
    "service_uniqueness",
    "how_it_works",
)


def _offer_noun(state: OfferSessionState) -> str:
    """'service' when the offer is a service, else 'product'."""
    return "service" if state.get("offer_type") == "service" else "product"


def _offer_nouns(state: OfferSessionState) -> str:
    """The plural form, for phrasing like 'how services in this category work'."""
    return "services" if _offer_noun(state) == "service" else "products"


def _specialist_for(state: OfferSessionState) -> Optional[Specialist]:
    """Pick the offer's own domain specialist out of the team.

    `Specialist.domain` exists precisely so this is a lookup rather than a guess
    at list position. The fallbacks are for a hand-built team that skipped the
    field; they degrade to 'first specialist' rather than raising, because a
    persona is presentation, not correctness, and losing the whole domain section
    over a missing name would be the wrong trade.
    """
    specialists = [s for s in (state.get("specialists") or []) if s]
    if not specialists:
        return None

    want = state.get("offer_type") or "product"
    for s in specialists:
        if getattr(s, "domain", None) == want:
            return s
    for s in specialists:
        if getattr(s, "domain", None) in ("product", "service"):
            return s
    return specialists[0]


def _specialist_lens(specialist: Optional[Specialist], offer_noun: str) -> str:
    """Render the persona for a prompt slot, or say plainly that there is none."""
    if specialist is None:
        return f"No specialist persona was supplied. Answer as a neutral {offer_noun} domain analyst."
    return (
        f"Name: {specialist.name}\n"
        f"Role: {specialist.role}\n"
        f"Domain: {specialist.domain}\n"
        f"Affiliation: {specialist.affiliation}\n"
        f"Description: {specialist.description}"
    )


def _known_facts(state: OfferSessionState) -> str:
    """The loose snapshot fields as JSON, minus everything empty.

    The fields are separate keys on the state rather than one nested object, so
    they are reassembled here. solution and target_users are included because
    they are real discovery signal, and because OfferDataSnapshot (below) has
    nowhere to put them.
    """
    facts = {
        key: state.get(key)
        for key in _KNOWN_FACT_KEYS
        if state.get(key) not in (None, "", [], {})
    }
    if not facts:
        return "No offer details were captured during discovery."
    return json.dumps(facts, indent=2, ensure_ascii=False, default=str)


def _offer_material(state: OfferSessionState) -> str:
    """The offer's own material, as one authoritative block.

    Built by adapting the loose state onto OfferDataSnapshot so the existing,
    memoised format_offer_material path is reused rather than reimplemented. That
    buys offer_brief's cached condensation for free, which matters because the
    same block is rendered at two prompt sites in a single run.

    The loose schema's features and service_uniqueness are plain strings, so they
    arrive here name-only. The material block therefore renders bare feature
    names with no description or differentiator attached. That is thinner than the
    other three subgraphs get, and is the price of the loose-field schema; the fix
    is richer feature objects on OfferSessionState, not anything in this file.
    """
    offer_noun = _offer_noun(state)
    snapshot = OfferDataSnapshot(
        offer_name=state.get("offer_name"),
        offer_description=state.get("offer_description"),
        target_geo=list(state.get("target_market") or []),
        problem_solved=state.get("problem"),
        how_it_works=state.get("how_it_works"),
        features=[SnapshotFeature(name=f) for f in (state.get("features") or []) if f],
        service_uniqueness=[
            SnapshotFeature(name=s) for s in (state.get("service_uniqueness") or []) if s
        ],
    )
    material = format_offer_material(
        snapshot, state.get("scraped_content"), offer_noun
    )

    # OfferDataSnapshot has no home for these two, and dropping them would lose
    # discovery signal the domain notes can use, so they are appended.
    extras = []
    if state.get("solution"):
        extras.append(f"Solution: {state['solution']}")
    if state.get("target_users"):
        extras.append(f"Target users: {', '.join(state['target_users'])}")
    if extras:
        material = "\n".join(filter(None, [material.strip(), *extras]))

    return material or "No offer material was captured during discovery."


def _render_task_plan(tasks: list[ResearchTask]) -> str:
    lines = []
    for i, task in enumerate(tasks, start=1):
        lines.append(f"### Task {i}: {task.area}")
        lines.append(f"Objective: {task.objective}")
        for j, query in enumerate(task.queries or [], start=1):
            role = "specific" if j < len(task.queries) else "fallback (broadest)"
            lines.append(f"  Query {j} [{role}]: {query}")
        lines.append("")
    return "\n".join(lines).strip()


def _render_bundle(bundle: TaskResearchBundle) -> str:
    """One research objective's evidence, as a block the writer can reason over.

    The notes are truncated to WRITER_NOTES_TOKEN_CAP before rendering: the
    writer synthesises across four areas into one ~150-word document, and its
    latency on the flagship tier is input-proportional, so feeding the full
    per-area notes (up to 1.8k tokens per source block) would spend the run's
    time on tokens the synthesis cannot use. Truncating the *rendering*, rather
    than the notes themselves, keeps the full evidence in the state/checkpoint
    verbatim; only what reaches this one synthesis call is trimmed, tail-first.
    """
    header = f"### AREA: {bundle.area}\nOBJECTIVE: {bundle.objective}"
    if bundle.queries:
        header += f"\nQUERIES ISSUED: {'; '.join(bundle.queries)}"
    if bundle.sources:
        header += f"\nSOURCES RETRIEVED: {len(bundle.sources)}"

    if bundle.search_failed or not bundle.notes.strip():
        return (
            f"{header}\n"
            "RESEARCH RESULT: No usable sources were returned for this area. "
            "This area is therefore still open and must be reported as a gap."
        )

    notes = _truncate_to_tokens(bundle.notes, WRITER_NOTES_TOKEN_CAP)
    sources = "\n".join(f"- {url}" for url in bundle.sources)
    return f"{header}\n\nRESEARCH NOTES:\n{notes}\n\nSOURCE URLS:\n{sources}"


def _dedupe_sources(bundles: list[TaskResearchBundle]) -> list[str]:
    """The union of every bundle's retrieved URLs, first-seen order.

    This is the canonical source list for a run: it is exactly what the
    pipeline actually retrieved, deduplicated once, so the writer can be told
    to cite against it and the harness can append `### Sources` from it. Both
    make fabricated citations structurally impossible rather than merely
    discouraged.
    """
    seen: set[str] = set()
    urls: list[str] = []
    for bundle in bundles:
        for url in bundle.sources or []:
            url = (url or "").strip()
            if url and url not in seen:
                seen.add(url)
                urls.append(url)
    return urls


def _sources_section(urls: list[str]) -> str:
    """The `### Sources` block, appended by the harness.

    Two trailing spaces per line: the report section writer renders this block
    through markdown, and the two-space line break is the convention every
    findings prompt in this codebase relies on for newlines.
    """
    if not urls:
        return ""
    lines = ["### Sources", ""]
    for i, url in enumerate(urls, start=1):
        lines.append(f"[{i}] {url}  ")
    return "\n".join(lines).rstrip() + "\n"


def create_tasks_research(state: OfferSessionState) -> dict:
    """Plan the domain research: read what is known, name what is missing.

    Fails loudly. A planner failure means there is nothing to research, and
    substituting a default task would produce a report-shaped hole that reads as
    a finished analysis. That is the same policy create_specialists takes.
    """
    offer_noun = _offer_noun(state)
    specialist = _specialist_for(state)
    lens = _specialist_lens(specialist, offer_noun)

    system_message = create_tasks_instructions.format(
        specialist_name=specialist.name if specialist else "a domain analyst",
        specialist_role=specialist.role if specialist else f"{offer_noun} domain analyst",
        specialist_affiliation=specialist.affiliation if specialist else "independent",
        specialist_description=specialist.description if specialist else lens,
        offer_noun=offer_noun,
        offer_nouns=_offer_nouns(state),
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
        # Planning on a closed schema, like search-query generation and ICP
        # generation, which both run thinking=False. The one call in this
        # pipeline that genuinely deliberates is the writer below.
        thinking=False,
    )

    tasks = list(plan.tasks or [])[:MAX_RESEARCH_TASKS]
    print(f"create_tasks_research: planned {len(tasks)} domain research task(s)")
    for i, task in enumerate(tasks, start=1):
        print(f"  {i}. {task.area} ({len(task.queries or [])} queries)")

    return {"tasks": plan.model_copy(update={"tasks": tasks})}


def _research_one(task: ResearchTask) -> TaskResearchBundle:
    """Run a single research task end to end: search, dedupe, distil, bundle.

    Runs on a worker thread, so it takes no state and shares nothing mutable.
    """
    area = task.area or "unnamed area"
    cfg = get_settings()
    issued: list[str] = []
    docs: list[dict] = []
    seen: set[str] = set()

    for query in task.queries or []:
        query = (query or "").strip()
        if not query:
            continue
        issued.append(query)
        try:
            results = search_and_scrape(query, cfg, num_results=SEARCH_RESULTS_PER_QUERY)
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

    # Distillation is input-bound (14-20s on a full ~11k-token page), so trim
    # each page to the substantive front before condensing. The note output cap
    # inside distill_document is untouched; only the bytes fed to the cheap
    # model shrink. A copy, never the shared search result -- the same docs
    # feed the sources list below, and truncating in place would leak the trim
    # into every consumer of the doc dict.
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
            f"(domain area: {area}). Keep named technologies, standards, numbers "
            f"and dates. Report what the domain/category does, not opinions."
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


def conduct_research(state: OfferSessionState) -> dict:
    """Run every planned task and append one bundle per task to `task_research`.

    The fan-out is an internal thread pool rather than a LangGraph `Send` fan-out.
    `Send` would give each task its own checkpoint entry, but the bundles would
    then be reduced into the `operator.add` channel from concurrent super-step
    branches in nondeterministic order. pool.map preserves plan order, so the same
    plan always produces the same bundle order, and a per-task try/except gives the
    same failure isolation inside one node.
    """
    plan = state.get("tasks")
    tasks = list(plan.tasks or []) if plan else []
    if not tasks:
        print("conduct_research: no tasks planned, nothing to research")
        return {"task_research": []}

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

    return {"task_research": bundles}


def note_down_record(state: OfferSessionState) -> dict:
    """Read the offer's own material and every research bundle, write the notes.

    The two inputs are kept distinct all the way through, because they answer
    different questions: the offer's own material says what this product IS, and
    the bundles say what its category is like. The writer has to hold both in view
    to say anything useful about fit.

    Fails loudly. These two fields are the pipeline's entire product, and a
    half-written synthesis that still sets `offer_under_complete` would let the
    section writer build on nothing.
    """
    offer_noun = _offer_noun(state)
    lens = _specialist_lens(_specialist_for(state), offer_noun)
    bundles = list(state.get("task_research") or [])
    if not bundles:
        # No research, no report. Do not call the writer on an empty corpus.
        return {
            "offer_findings": "No research bundles were produced.",
            "offer_domain_fit_understanding": "",
            "offer_under_complete": True,
        }

    # budget_context, not a bare join. _render_bundle already caps each bundle's
    # notes at WRITER_NOTES_TOKEN_CAP, so the per-bundle cost here is fixed
    # rather than a property of the current page sizes, but the offer material
    # and the header/source lines still vary, and a run that doubles the task
    # count would otherwise overflow at this last call, having already paid for
    # all of it. The offer's own material goes first because budget_context
    # protects the first chunk, which is exactly the right chunk to protect.
    context = budget_context(
        [_offer_material(state), *(_render_bundle(b) for b in bundles)],
        label="offer domain research",
    )

    # The canonical source list: everything this run actually retrieved, once.
    # Fed to the writer as the only things it may cite, and appended verbatim
    # after its notes, so the ### Sources contract holds even when the model
    # drops the trailing-instruction, and fabricated citations become
    # structurally impossible. This is the same determinism trade
    # `understand_product` makes with its source-block rules, but pinned in code
    # rather than left to a prompt that loses tail-instructions under thinking.
    source_urls = _dedupe_sources(bundles)
    auditable_sources = "\n".join(
        f"[{i}] {url}" for i, url in enumerate(source_urls, start=1)
    ) or "(no source was retrieved for any research area)"

    system_message = record_instructions.format(
        offer_noun=offer_noun,
        offer_nouns=_offer_nouns(state),
        offer_features="its features" if offer_noun == "product" else "its service elements",
        specialist_lens=lens,
        auditable_sources=auditable_sources,
        context=context,
        word_count=DOMAIN_FINDINGS_WORD_COUNT,
    )

    notes = invoke_structured_with_fallback(
        messages=[
            SystemMessage(content=system_message),
            SystemMessage(content="Write the domain notes now."),
        ],
        schema=ProductFindings,
        log_label="note_down_record",
        # The findings writer summarises already-distilled notes: every source
        # has been condensed against the task that retrieved it, and its only
        # remaining job is faithful synthesis into one bounded document. That is
        # the "summarisation of already-distilled notes" workload --
        # llm/main.py's comment at the thinking gate explicitly classifies it as
        # NOT the reasoning that justifies the measured 3.9x. The deliberation
        # budget belongs to interview answers and the report section writer
        # (write_sections), where synthesis builds on live context; it does not
        # survive a second trip through notes that were already condensed once.
        thinking=False,
    )

    findings = (notes.findings or "").strip()
    fit = (notes.product_domain_understanding or "").strip()

    # The schema asks for 40 words, never more than 50; an LLM cannot be relied
    # on to hit that on its own (the market twin once returned 53), and the
    # bound is load-bearing for the report section writer. So it is clamped
    # here, the same way the task count is clamped -- a hard stop in the
    # harness rather than another prompt instruction.
    fit_words = fit.split()
    if len(fit_words) > 50:
        fit = " ".join(fit_words[:50])
        print(
            f"note_down_record: fit understanding clamped from {len(fit_words)} "
            f"to 50 words"
        )

    # Same hard-stop philosophy for the notes body: the prompt targets
    # DOMAIN_FINDINGS_WORD_COUNT, but an LLM cannot be relied on to hold to it
    # (the pre-brevity writer once returned ~700 words against a 400 target).
    # Clamped BEFORE the harness-built Sources block is appended, so the
    # citation contract is never truncated.
    findings_words = findings.split()
    if len(findings_words) > DOMAIN_FINDINGS_WORD_CAP:
        findings = " ".join(findings_words[:DOMAIN_FINDINGS_WORD_CAP])
        print(
            f"note_down_record: findings clamped from {len(findings_words)} "
            f"to {DOMAIN_FINDINGS_WORD_CAP} words"
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

    # If there was no research data, don't pretend the stage succeeded — a
    # zero-bundle run is not \"under complete\".
    if not bundles:
        return {
            "offer_findings": "No research bundles were produced.",
            "offer_domain_fit_understanding": "",
            "offer_under_complete": True,
        }

    return {
        "offer_findings": findings,
        "offer_domain_fit_understanding": fit,
        "offer_under_complete": True,
    }


def build_product_graph(checkpointer: bool = True):
    """create_tasks_research -> conduct_research -> note_down_record.

    No conditional edges and no cycles, on purpose. See the module docstring.
    """
    builder = StateGraph(OfferSessionState)

    # -- Nodes --
    builder.add_node("create_tasks_research", create_tasks_research)
    builder.add_node("conduct_research", conduct_research)
    builder.add_node("note_down_record", note_down_record)

    # -- Edges --
    builder.add_edge(START, "create_tasks_research")
    builder.add_edge("create_tasks_research", "conduct_research")
    builder.add_edge("conduct_research", "note_down_record")
    builder.add_edge("note_down_record", END)

    return builder.compile()
