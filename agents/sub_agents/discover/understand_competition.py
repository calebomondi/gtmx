"""
Competition Understanding.

The competition stage, as an explicit research pipeline rather than a multi-turn
interview, borrowed from the offer and market pipelines:

    create_tasks_research      -> plan 3-5 competition research objectives
    conduct_research           -> run them, one bundle of evidence per objective
    extract_competitor_profile -> the draft ideal competitor profile + the offer's SWOD (soft-fail)
    refine_competitor_profile  -> self-review pass over the profile (soft-fail)
    note_down_record           -> write the competitive notes + positioning view

Deliberately LINEAR, for the same reason the offer and market stages are: the
pipeline's product is the findings + positioning understanding + profile, a hard
cost bound is worth more here than marginal depth, and every extra round
multiplies Exa calls and distillation. There is no re-planning loop and no
sufficiency gate.

WHAT THIS STAGE DOES NOT DO: name competitors. It used to emit a
`competitors: list[Competitor]` -- 3-5 real, URL-verified rivals -- and that list
is gone. The stage now emits `IdealCompetitorProfile`, a set of ARCHETYPES
describing what a perfect competitor to this offer looks like, and finding real
companies is the standalone `get_competitors.py` agent's job, which runs
separately per workspace and accumulates rivals over time. Two consequences
follow from that split, and both are deliberate:

  - The stage got CHEAPER. It used to probe each named competitor's website
    with a live scrape (`verify_competitors`, up to 5 Exa calls per run). An
    archetype has no URL to verify, so that loop is gone entirely. The one
    extra LLM call this stage pays for the refine pass is more than covered.
  - The stage got GEO-UNBOUNDED. Scoping to the offer's target geographies was
    correct when the output was "the rivals this offer actually faces here".
    It is wrong now, because a global player shipping into the offer's market is
    a live competitor from anywhere. `target_geo` is therefore CONTEXT, never a
    filter: the planner and extractor hunt local incumbents AND international
    entrants, and every instruction that used to narrow by geography now widens
    instead.

THE PROFILE IS A CONSTRUCT. An archetype ("regional incumbent undercutting on
price") is something we invented to describe the shape of a rival; it asserts
nothing about any real firm. That is what licenses the profile to be
AGGRESSIVE -- 4-6 archetypes spanning the whole threat surface, speculative but
labelled confidence, no sourcing obligation. It is the exact inverse of
`Competitor`, which is a set of factual claims about a verified real company and
must be sourced or dropped. Keep the two epistemics apart; if
`get_competitors.py` ever inherits the "be aggressive" instruction from this
stage, it will start inventing pain signals.

The graph runs EXTRACT BEFORE WRITER -- deliberately the reverse of the market
stage. In the market stage the structured verdict is a judgment, so the
extractor was anchored to the narrative. Here the structured PROFILE is the
load-bearing output the downstream competitor agent reads, so the writer is
anchored on it. The refine node sits between them, mirroring `build_icp`'s
create -> refine -> narrate discipline: the profile is finalized and
self-reviewed BEFORE the writer is anchored on it, so the notes describe the
profile that actually shipped rather than the first draft.

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
context to scope the landscape by category alone, and "alternatives to X" pages
are the least trustworthy surface on the internet. Name-free category queries
surface the same real rivals without the SEO junk.

The graph runs EXTRACT BEFORE WRITER -- deliberately the reverse of the market
stage. In the market stage the structured verdict is a judgment, so the
extractor was anchored to the narrative. Here the structured PROFILE is the
load-bearing output the downstream competitor agent reads, so the writer is
anchored on it rather than the other way round.

RECENCY is inherited from the market stage: every search passes
`start_published_date = today - Config().market_recency_days` (default 365) --
the same window the interview-era understand_competition uses. Positioning,
pricing and features decay; a landscape built from stale sources is worse than
a thin one.

The single cosplayed expert is the competition specialist, selected out of
`specialists` by `Specialist.domain == "competition"` (see
`_competition_specialist_for`). BOTH the extract and refine nodes SOFT-FAIL like
the market stage's extractor: the narrative findings are the pipeline's
product, and losing the structured profile must not sink a run whose notes are
already written.
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
from agents.states import (
    CompetitionFindings,
    CompetitionRecord,
    IdealCompetitorProfile,
    TaskResearchBundle,
)
from data_sources.scraping.exa import search_and_scrape

from ..schema_states import CompetitionSessionState, ResearchTask, Specialist, TaskList
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

# The profile is asked for 4-6 archetypes and the clamp is the hard stop, same
# philosophy as MAX_RESEARCH_TASKS above. The ceiling is generous relative to
# the ask because an archetype is cheap (no search, no URL verification) and
# breadth is the point -- a wide threat surface is what the consuming agent
# needs. The floor only warns; padding a thin profile would be worse than
# shipping it short.
MAX_ARCHETYPES = 8
MIN_ARCHETYPES = 3


def _recency_cutoff(days: int) -> str:
    """ISO date (YYYY-MM-DD) for the oldest source the competition research may use."""
    return (date.today() - timedelta(days=days)).isoformat()


def _brand_patterns(state: CompetitionSessionState) -> list[re.Pattern[str]]:
    """Regexes matching the offer's own name in a search query, worst-first.

    The FULL NAME is the brand, and it is what must never be searched -- so that
    is what gets matched, whitespace-flexibly so a query cannot dodge it by
    reformatting the name.

    Individual sub-tokens are matched ONLY for a single-word name, where the one
    token IS the brand. Splitting a multi-word name is a trap: "Acme Vector DB"
    tokenizes to acme/vector/db, and stripping "vector" destroys the category
    noun out of every honest query about vector databases. A generic word inside
    a brand name is not a brand, and only the whole phrase identifies this offer.
    """
    name = (state.get("offer_name") or "").strip()
    if not name:
        return []
    tokens = [t for t in re.split(r"[^\w]+", name.lower()) if t]
    if not tokens:
        return []
    phrase = r"\s+".join(re.escape(t) for t in tokens)
    patterns = [re.compile(rf"\b{phrase}\b", re.IGNORECASE)]
    if len(tokens) == 1:
        # A one-word brand is often written with a suffix the model adds
        # ("AuraPod Pro"), so match the stem too. Multi-word names get no such
        # treatment: their trailing word may be a category noun.
        if len(tokens[0]) > 3:
            patterns.append(re.compile(rf"\b{re.escape(tokens[0])}\w{{0,6}}\b", re.IGNORECASE))
    return patterns


def _scrub_brand(query: str, brand_patterns: list[re.Pattern[str]]) -> str:
    """Remove the offer's own name from a query, keeping the category words.

    The planner is instructed to stay brand-free and usually does, but it slips:
    a real run emitted "alternatives to StitchUp" despite an explicit rule, and
    "alternatives to X" is exactly the comparison-list SEO surface the rule
    exists to avoid. Enforcing it here rather than trusting the prompt makes the
    invariant structural.

    Two cleanups run with the brand strip, because removing a name can leave
    behind a query that is still a comparison, or no query at all:

    - the connective that needed the name ("alternatives to", "vs") goes too,
      since deleting only the name leaves "on-demand tailoring app" reading as a
      comparison it no longer names;
    - a query that was NOTHING BUT the comparison ("StitchUp competitors") is
      returned empty, and the caller drops it. Left alone it would search for
      the single word "competitors" and return the SEO junk the rule exists to
      avoid. Emptiness is a real outcome here, which is why the return type is
      the scrubbed query or "" and never the input unchanged.
    """
    if not brand_patterns:
        return query
    scrubbed = query
    for pattern in brand_patterns:
        scrubbed = pattern.sub("", scrubbed)
    # Only the residue of an actual removal gets the cleanup below. A query that
    # never named the offer is left byte-for-byte alone -- even a bare "pricing"
    # is a legitimate thing to search for, and it is not this function's job to
    # second-guess query quality it did not break.
    if scrubbed == query:
        return query
    scrubbed = _BRAND_CONNECTIVE.sub(" ", scrubbed)
    scrubbed = re.sub(r"\s{2,}", " ", scrubbed).strip(" -,&")
    if scrubbed and all(word in _DEGENERATE_HEADS for word in scrubbed.lower().split()):
        return ""
    return scrubbed


# Connectives that only make sense when a brand name is attached to them, in
# either order ("alternatives to X" and "X competitors" both occur).
_BRAND_CONNECTIVE = re.compile(
    r"\b(alternatives?\s+to|competitors?\s+(?:to|of|for)|versus|vs\.?|compared?\s+(?:to|with))\b",
    re.IGNORECASE,
)

# What a query is left holding when the name was all it had. Searching for these
# alone is worse than not searching: "competitors" returns the comparison-list
# SEO that made the brand-free rule worth having. Not a general stopword list --
# a short check for a query that is now pure competitive plumbing.
_DEGENERATE_HEADS = frozenset(
    {
        "competitor", "competitors", "competing", "competition",
        "alternative", "alternatives", "alternative", "alts",
        "vs", "versus", "compare", "compared", "comparison", "reviews", "review",
        "pricing", "price", "prices", "options", "best",
    }
)


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
    scope the competitive landscape (category, buyer, geos, pricing). The
    pipeline carries the same block so a session that ran the market stage first
    reads identically.

    The header matters: `geo` in that JSON is where the OFFER sells, not where
    its competitors live, and the two stopped being the same thing when this
    stage stopped naming rivals. An explicit note keeps the model from reading
    the market's geos as a filter on the landscape.
    """
    market = state.get("market_data")
    if market is None:
        return (
            "No structured market data available -- scope the landscape to the "
            "offer and its category alone, and still look beyond the offer's "
            "own geographies for competitors."
        )
    return (
        "NOTE: `geo` below is where the OFFER intends to sell. It is NOT a "
        "filter on who competes -- competitors headquartered elsewhere but "
        "operating in this market are in scope.\n\n"
        + market.model_dump_json(indent=2, exclude_none=True)
    )


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


def _profile_anchors(state: CompetitionSessionState) -> str:
    """The archetype profile the writer must stay grounded on.

    Replaces the old `_competitor_names`, which handed the writer a
    comma-joined list of real company names to describe. The writer no longer
    gets a name list -- it gets the archetypes that shipped, so its notes and
    the profile the downstream competitor agent consumes cannot describe
    different landscapes.
    """
    profile = state.get("ideal_competitor_profile")
    if profile is None:
        return (
            "(no ideal competitor profile was produced -- ground the notes in "
            "the research alone)"
        )
    lines = []
    for archetype in profile.archetypes or []:
        lines.append(f"- {archetype.label} ({archetype.geography_scope}): {archetype.archetype_description}")
    if profile.category_definition:
        lines.insert(0, f"Category boundary: {profile.category_definition}")
    return "\n".join(lines) if lines else "(the profile carries no archetypes -- ground the notes in the research alone)"


create_tasks_instructions = """
You are {specialist_name}, a {specialist_role} working in {specialist_affiliation}.

YOUR LENS
{specialist_description}

You are the competition specialist. You understand this {offer_noun}'s category,
its buyers and its target geographies -- you have that context in front of you
-- and you know the {offer_noun} itself from its own material. Before you can
say what a REAL rival looks like here, how that kind of rival positions, and
where the {offer_noun} wins and loses against it, you need evidence you do not
have yet.

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
Plan the research that maps this {offer_noun}'s real competitive landscape --
the kinds of company that actually compete for this buyer in this category, how
they position, what they charge, where their customers hurt, and where the
landscape leaves room for the {offer_noun}. You are planning, not answering.
Nothing has been searched yet, and the results come back to you afterwards for
you to read.

GEOGRAPHY IS NOT A BOUNDARY. The {offer_noun}'s target geographies are where it
intends to SELL. They are not where its competitors live. A company headquartered
in another country that sells into this market competes just as hard as a local
one, and in many categories that is where the most dangerous rivals come from.
Research BOTH:
- local and regional incumbents defending this specific market, and
- international players already operating in or adjacent to it, including the
  ones a global brand field would put on a local buyer.
If a task can only be answered by looking outside the offer's own geographies,
that is a reason to plan it, not a reason to skip it.

Each task is ONE objective that a set of public web sources could genuinely
settle, in an area such as:
- the KINDS of company that compete in this category -- direct rivals,
  substitutes, and the local incumbents a buyer would default to
- how rival companies position and what they offer: their messaging, their
  product or service scope, and their publicly stated pricing, funding and
  traction
- foreign or global entrants into this market: who they are, how they enter,
  what they charge, and whether local buyers actually adopt them
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
3. NEVER put the {offer_noun}'s name or its brand in a query. Not "alternatives
   to {offer_name}", not "{offer_name} competitors", not the brand in any casing
   or with any suffix. This is checked, and a violating query is rewritten before
   it is ever searched. Research the CATEGORY instead, so the sources describe
   the rivals rather than this {offer_noun} or its own marketing claims.
   "Who competes in <category>" finds the same rivals that "X competitors"
   would -- without the comparison-list SEO junk, which is the whole reason for
   the rule.
4. Do NOT narrow queries to the offer's target geographies. Name the category and
   the kind of rival you want instead; add a geography only when the COMPETITOR
   is defined by it (a city-level service business, say). Where you do name one,
   cover at least one task aimed at international operators of this category.
5. Every objective is a research goal, not a search string. It must be specific
   enough that "this task came back with nothing" is itself a meaningful finding.
6. Do not assert what you will find, and do not invent rivals or facts. You are
   choosing what to look up.

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
- Keep every concrete claim: the rivals the research actually names, their
  positioning, pricing, funding and traction figures, dates, feature gaps, and
  where each one operates. Those are what get cited downstream, and the named
  ones are what seed the downstream competitor agent's search.
- Be brief. These notes are conclusions plus the claims that evidence them, not a
  ledger of everything retrieved. Cut reasoning bridges, elaboration, and anything
  the report writer can recover from the sibling stages. When in doubt, leave it
  out.
- Name only rivals the research actually supports. Never infer or invent one.
  This does NOT mean the notes must be archetype-only -- naming real rivals here
  is correct and valuable, because a named rival with a source is evidence, and
  the stage that finds competitors later will read this prose.
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

3. The IDEAL COMPETITOR PROFILE below is the archetype profile built from this
   same evidence: the KINDS of company that would compete against this
   {offer_noun}, spanning local incumbents through international entrants. This
   is the load-bearing structure: ground your notes in it, and do not describe a
   landscape that contradicts it. It names no companies by design, so it does
   not constrain which real rivals you may mention -- a retrieved source naming
   one is always allowed, and you should.

4. The RESEARCH BUNDLES, one per research objective, describe the rivals
   directly: who competes, how they position, what they charge, where they fall
   short.

SPECIALIST LENS
{specialist_lens}

IDEAL COMPETITOR PROFILE
{profile_anchors}

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
- the competitive landscape: the kinds of company that compete against this
  {offer_noun}, and the real rivals the research named, covering BOTH local
  incumbents and international players operating in this market
- rival by rival: positioning, offering, and publicly stated pricing, funding
  and traction where the research supports it, and where each rival operates
- foreign entrants specifically: who is already selling into this market from
  abroad, and what the local incumbents do about it
- a comparison of the {offer_noun} to its real rivals: where it beats them,
  where it falls short, and what is genuinely unique about it
- strengths, weaknesses, opportunities and gaps relative to the archetype
  profile
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

Read the COMPETITIVE EVIDENCE in front of you and build two things: an
`IdealCompetitorProfile` describing the KINDS of company that would compete
against this {offer_noun}, and a SWOD record of how the {offer_noun} stacks up
against the competitive standard.

This is a classification task over evidence you already hold, not a research
task. Nothing here is to be invented, and nothing here is a claim about a real
company.

{context}

THE PROFILE NAMES NOBODY -- AND THAT IS THE POINT
The profile is a CONSTRUCT: a set of archetypes describing the shape of a
perfect competitor. You are NOT producing a list of companies. A later, separate
agent searches the web for real firms matching these archetypes; your job is to
tell it what to look for. So:
- Never put a real company name in an archetype. Write "regional incumbent
  undercutting on price", not "Acme undercutting on price". An archetype that
  names a real firm is a bug.
- The archetypes SHOULD be specific and opinionated. This is the one place in
  the pipeline where you are expected to be aggressive: a vague profile is worth
  nothing to the agent that consumes it. Reach for the archetype a strategist
  would actually worry about.

BE AGGRESSIVE AND SPAN THE WHOLE THREAT SURFACE
Aim for 4-6 archetypes (never fewer than 3 unless the evidence is genuinely
empty). Cover the range deliberately rather than three variations on one idea:
- local incumbents defending this specific market
- regional players from neighbouring markets
- INTERNATIONAL competitors -- companies headquartered abroad that sell into
  this market. Do not skip these because the offer's target geographies are
  local. Where a global brand would put a local buyer is exactly the threat the
  profile exists to name.
- premium/niche specialists attacking the same buyer from a different angle
- indirect and substitute threats: adjacent products, in-house builds, DIY
  workarounds, or simply doing nothing

Rules for each archetype:
- label: a short name for the KIND of company, e.g. "Regional incumbent",
  "Global SaaS entrant", "DIY substitute".
- archetype_description: concretely what this kind of competitor is and how it
  operates. Two or three sentences, specific enough to be recognisable.
- geography_scope: "local", "regional", "global" or "any". Be honest about which.
- business_model / typical_offering / pricing_model / customer_profile: how it
  makes money, what it sells, how it charges, and whom it serves.
- likely_advantages: where THIS KIND of competitor would beat the {offer_noun}.
- likely_weaknesses: where this kind of competitor would be VULNERABLE to the
  {offer_noun}. These are the openings worth having.
- where_to_find_them: search surfaces, directories or query shapes where real
  instances of this archetype would be found. Be practical -- this is the
  hunting ground the next agent will use, so "Google" is useless and
  "regional dental practice directories, '<service> <city>'" is useful.
- confidence: "high", "medium" or "low" -- how well the evidence supports this
  archetype. Mark a speculative archetype "low" rather than dropping it or
  inflating it.

Profile-level fields:
- category_definition: what counts as a competitor in this category.
- boundary_of_category: adjacent things that are NOT competitors -- substitutes,
  complements, upstream suppliers. Keeps the next agent from chasing the wrong
  firms.
- global_entry_signals: what a foreign entrant would attack this market with,
  and why it could win.
- local_defence_signals: what local incumbents defend with, and why entrants
  struggle against them.
- substitution_risks: non-company alternatives a buyer may choose instead.
- price_anchor_range: the observed price band across the landscape, when the
  evidence supports one. Empty string otherwise.
- channels: how competitors in this category reach buyers -- the routes a rival
  already owns.
- confidence: overall, how well the research supports this profile.

SWOD (the `swod` object) -- these ARE claims about the offer, so ground them in
the evidence and return an empty list rather than inventing:
- strengths: where the {offer_noun} meets or beats the competitive standard.
- weaknesses: where it falls short of the standard.
- opportunities: gaps in the landscape the {offer_noun} could exploit.
- differentiators: what genuinely sets it apart.

JSON discipline: every list field must be a real JSON array -- no
double-serialized strings. For optional string fields that do not apply, use an
empty string ""; never null and never omit the key. The record is validated
against a strict schema.
"""


refine_instructions = """
You are an expert competitive strategist reviewing a draft Ideal Competitor
Profile for a {offer_noun}.

A separate agent will later search the web for real companies matching these
archetypes. Your job is to make that profile the one you would actually want to
hand it. Review the draft critically and return an improved version.

WHAT GOOD LOOKS LIKE
- SPANS the threat surface. Local incumbents AND international entrants AND at
  least one substitute or indirect threat. A profile of three variations on
  "local competitor" is a failure, not caution.
- Each archetype earns its place: distinct, recognisable, and genuinely a
  competitor for THIS buyer. Merge any two that describe the same kind of
  company. Split any that are doing two different jobs.
- SPECIFIC. "Regional incumbent undercutting on price" is useful; "a
  competitor" is not.
- `where_to_find_them` is actionable. This is the field the next agent acts on.
  Directories, marketplaces, trade associations, review sites and query shapes
  beat abstract categories.
- `likely_weaknesses` are real openings, not restated advantages. If a weakness
  is something the {offer_noun} also has, it is not a weakness of this archetype.
- `confidence` is honest. Mark a speculative archetype "low". Do not inflate
  confidence to make the profile look authoritative, and do not delete a
  speculative archetype to make the profile look tidy -- a labelled guess is
  worth more to the consumer of this profile than a confident nothing.

WHAT TO FIX
- Collapse archetypes that overlap; split ones that are incoherent.
- Fill any field left empty that the evidence supports.
- Add a missing archetype if the threat surface has an obvious hole.
- Correct any archetype that drifted into naming a real company. Archetypes
  describe KINDS of company, never specific firms -- naming one is the single
  most important error to catch, because a named archetype makes the consumer
  believe the search has already happened.
- Keep `category_definition` and `boundary_of_category` tight; they are what
  keeps the next agent from chasing the wrong companies.

Return only the corrected profile. Same schema, no commentary.
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

    # Brand-free search is an INVARIANT, not a request. The planner is told not
    # to name the offer and usually complies, but it slips -- a real run emitted
    # "alternatives to StitchUp" despite an explicit rule, and "alternatives to
    # X" is precisely the comparison-list SEO surface the rule exists to avoid.
    # Scrubbing here, once, at the single point every task flows through, makes
    # the guarantee structural instead of probabilistic: no later stage can emit
    # a branded query because none survives this line.
    brand_patterns = _brand_patterns(state)
    scrubbed_tasks = []
    for task in tasks:
        queries = [_scrub_brand(q, brand_patterns) for q in (task.queries or [])]
        queries = [q for q in queries if q]
        if queries != list(task.queries or []):
            print(f"create_tasks_research: scrubbed the offer's brand out of a query in '{task.area}'")
        scrubbed_tasks.append(task.model_copy(update={"queries": queries}))

    print(f"create_tasks_research: planned {len(scrubbed_tasks)} competition research task(s)")
    for i, task in enumerate(scrubbed_tasks, start=1):
        print(f"  {i}. {task.area} ({len(task.queries or [])} queries)")

    return {"competition_tasks": plan.model_copy(update={"tasks": scrubbed_tasks})}


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
            f"(competition area: {area}). Keep the kinds of company that compete "
            f"here, their positioning, pricing, funding, traction, dates, and "
            f"WHERE each one operates -- headquarters and operating market "
            f"separately, since a foreign operator selling locally is a distinct "
            f"and important case. Report what rivals do, not opinions."
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


def extract_competitor_profile(state: CompetitionSessionState) -> dict:
    """Read the competitive evidence and emit the DRAFT ideal competitor profile
    plus the offer's SWOD.

    A cheap-tier classification pass (thinking off) over the same evidence the
    writer reasons from. One LLM call returns both halves via `CompetitionRecord`,
    because they come from a single reading of the evidence and splitting them
    would double the cost for no gain. They land in separate state channels.

    The URL-verification loop this node used to run is GONE. It probed each named
    competitor's website with a live scrape (up to 5 Exa calls per run) and
    dropped the ones that failed -- sensible when the output was a list of real
    companies whose dead links would propagate downstream, and pure waste now
    that an archetype has no URL to verify. That deletion is why adding the
    refine node below did not make this stage more expensive overall.

    SOFT-FAILS on purpose, like the market stage's extractor: the narrative
    findings are the pipeline's product, and losing the structured profile must
    not sink a run whose notes are already written.
    """
    bundles = list(state.get("competition_task_research") or [])
    context = _competition_context(state, bundles)

    system_message = extract_instructions.format(
        offer_noun=_offer_noun(state), context=context
    )

    try:
        record = invoke_structured_with_fallback(
            messages=[
                SystemMessage(content=system_message),
                SystemMessage(content="Build the ideal competitor profile and the SWOD now."),
            ],
            schema=CompetitionRecord,
            log_label="extract_competitor_profile",
            # Closed-schema classification of evidence already in hand --
            # exactly the cheap-tier workload llm/main.py's thinking gate
            # reserves for thinking-off calls.
            thinking=False,
        )
    except Exception as exc:  # noqa: BLE001 - soft-fail by design, see docstring
        print(f"extract_competitor_profile: failed ({exc}); profile + competition_data left unset")
        return {}

    profile = record.profile
    # Hard ceiling on the archetype count. Same philosophy as MAX_RESEARCH_TASKS:
    # a schema hint is a suggestion, the clamp is the bound. The floor only warns
    # -- a thin profile is thin evidence, and padding it would be worse than
    # shipping it short.
    archetypes = list(profile.archetypes or [])[:MAX_ARCHETYPES]
    profile = profile.model_copy(update={"archetypes": archetypes})
    if len(archetypes) < MIN_ARCHETYPES:
        print(
            f"extract_competitor_profile: only {len(archetypes)} archetype(s) "
            f"extracted -- keeping the defensible set, not inventing more"
        )
    print(
        f"extract_competitor_profile: {len(archetypes)} archetype(s) "
        f"({sum(1 for a in archetypes if a.geography_scope == 'global')} global), "
        f"{len(record.swod.strengths)} strength(s)"
    )
    return {
        "ideal_competitor_profile": profile,
        "competition_data": record.swod,
    }


def refine_competitor_profile(state: CompetitionSessionState) -> dict:
    """Self-review pass over the draft profile.

    Mirrors `build_icp`'s create -> refine -> narrate discipline, applied to the
    stage's primary output: the profile is finalized BEFORE the writer is
    anchored on it, so the notes describe the profile that shipped rather than
    the first draft. Without this the writer reads a draft whose overlapping or
    missing archetypes it then faithfully describes.

    SOFT-FAILS, and SOFT-FAILS BY KEEPING THE DRAFT. A failed refine must not
    discard a profile the extractor already produced, so the except branch
    returns `{}` and the draft stands rather than being cleared.
    """
    profile = state.get("ideal_competitor_profile")
    if profile is None:
        print("refine_competitor_profile: no draft profile to refine, skipping")
        return {}

    system_message = refine_instructions.format(offer_noun=_offer_noun(state))

    try:
        refined = invoke_structured_with_fallback(
            messages=[
                SystemMessage(content=system_message),
                SystemMessage(content=f"Draft profile under review:\n\n{profile.model_dump_json(indent=2, exclude_none=True)}"),
                SystemMessage(content="Return the corrected profile now."),
            ],
            schema=IdealCompetitorProfile,
            log_label="refine_competitor_profile",
            # Same cheap-tier gate as the other three pipelines' structured
            # passes: this is critique of an in-hand artifact, not open-ended
            # reasoning that justifies the flagship thinking cost.
            thinking=False,
        )
    except Exception as exc:  # noqa: BLE001 - soft-fail by design, see docstring
        print(f"refine_competitor_profile: failed ({exc}); keeping the draft profile")
        return {}

    refined = refined.model_copy(
        update={"archetypes": list(refined.archetypes or [])[:MAX_ARCHETYPES]}
    )

    # A refine pass that returned an empty profile is a regression, not an
    # improvement -- the reviewer's job was to fix a draft, not delete it.
    if not refined.archetypes:
        print("refine_competitor_profile: returned no archetypes; keeping the draft profile")
        return {}

    print(
        f"refine_competitor_profile: {len(profile.archetypes or [])} draft "
        f"archetype(s) -> {len(refined.archetypes)} refined"
    )
    return {"ideal_competitor_profile": refined}


def note_down_record(state: CompetitionSessionState) -> dict:
    """Read the offer's own material, the sibling context, the refined
    archetype profile and every competition bundle; write the notes.

    Runs AFTER extract AND refine -- deliberately the reverse of the market
    stage -- so the writer is anchored on the profile that actually shipped,
    and the positioning verdict is judged against it.

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
        profile_anchors=_profile_anchors(state),
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
    """create_tasks_research -> conduct_research -> extract_competitor_profile
    -> refine_competitor_profile -> note_down_record.

    Extract runs BEFORE the writer (deliberately the reverse of the market
    graph): the structured profile is the load-bearing output the downstream
    competitor agent reads, and the writer is anchored on it rather than the
    other way round. Refine sits between them so the writer is anchored on the
    FINAL profile, not the draft -- the create -> refine -> narrate discipline
    build_icp applies internally, here applied across the stage boundary. No
    conditional edges and no cycles, on purpose. See the module docstring.
    """
    builder = StateGraph(CompetitionSessionState)

    # -- Nodes --
    builder.add_node("create_tasks_research", create_tasks_research)
    builder.add_node("conduct_research", conduct_research)
    builder.add_node("extract_competitor_profile", extract_competitor_profile)
    builder.add_node("refine_competitor_profile", refine_competitor_profile)
    builder.add_node("note_down_record", note_down_record)

    # -- Edges --
    builder.add_edge(START, "create_tasks_research")
    builder.add_edge("create_tasks_research", "conduct_research")
    builder.add_edge("conduct_research", "extract_competitor_profile")
    builder.add_edge("extract_competitor_profile", "refine_competitor_profile")
    builder.add_edge("refine_competitor_profile", "note_down_record")
    builder.add_edge("note_down_record", END)

    return builder.compile()