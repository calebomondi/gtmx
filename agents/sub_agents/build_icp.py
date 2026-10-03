"""
ICP Understanding.

The GTM stage, as an explicit SYNTHESIS pipeline rather than a research pipeline
or a multi-turn interview, borrowed from the interview-era `determine_icp`
subgraph and completed in the idiom of the offer/market/competition pipelines:

    create_icp        -> draft the structured ICP (offer-type x buyer-type aware)
    refine_icp        -> self-review: prune guesses, enforce buyer coherence,
                         clamp the industry set
    note_down_record  -> write the narrative findings + 40/50-word understanding,
                         anchored on the refined record

DELIBERATELY NO RESEARCH. The ICP is the GTM specialist's judgment derived from
what the session already knows: who buys and what they pay (market findings +
structured market context), who else wins this business and where their
customers hurt (competition findings, which name the real rivals, plus the
structured SWOD and archetype profile), and what the
offer IS (offer material + domain findings). The account-discovery stage
immediately downstream does the reach research -- it searches the target
channels/communities/events/industries this profile names. Re-researching the
buyer here would duplicate that stage and pay for synthesis the ICP cannot
out-source. The absence of `icp_tasks`/`icp_task_research` in`IcpSessionState`, of a recency gate, and of a `### Sources` block on the notes
is therefore structural, not an oversight: nothing is retrieved in this stage,
so there is nothing to gate and nothing honest to cite by number. Every claim in
the findings is citable only by LABEL (`[offer material]`, `[market findings]`,
`[competition findings]`, `[market context]`, `[competition context]`, `[ICP]`).

The stage branches on BOTH axes a GTM expert actually uses (and the interview-era
stage used only one). `_icp_emphasis(offer_type, buyer_type)` selects the branch:

    product x b2b  -> firmographics (<=3 industries, size bands, technical +
                      economic buyer titles), adoption lens
    product x b2c  -> named consumer personas, where they congregate, channels
    service x b2b  -> firms that buy services, trust/procurement lens, the roles
                      who hold the budget, geo-scoped delivery
    service x b2c  -> local consumer-service personas, geo-specific channels,
                      trust signals
    both           -> both sides

buyer_type comes from the market stage's structured extraction
(`market_data.buyer_type`), defaulting to b2b exactly as the interview-era stage
did; offer_type is the offer snapshot's own `offer_type`.

Graph shape keeps the extract-before-writer discipline of the competition stage:
the structured ICP is the load-bearing output account discovery consumes, so
`create_icp + refine_icp` (the "extraction" side, internal to the record) runs
before the writer, and `note_down_record` is anchored on the finalized record --
it names the same industries, personas, channels, exclusions and competitor
leads, never additions the record did not support.

The single cosplayed expert is the GTM specialist, selected out of `specialists`
by `Specialist.domain == "gtm"` (see `_gtm_specialist_for`), exactly as the
market/competition stages select by their own domains.

All three nodes run with `thinking=False`: drafting and refining a closed
schema, and summarising already-synthesised context, are exactly the workloads
llm/main.py's thinking gate reserves for thinking-off calls.
"""

from typing import Optional

from langgraph.graph import START, END, StateGraph
from langchain_core.messages import SystemMessage

from agents.llm.main import invoke_structured_with_fallback
from agents.context_budget import budget_context
from agents.states import ICP, IcpFindings

from .schema_states import IcpSessionState, Specialist
from .understand_competition import _market_context_block, _sibling_block
from .understand_offer import _offer_material, _offer_noun, _offer_nouns, _specialist_lens


# The ICP findings feed the report's GTM section. IcpSessionState carries no
# section_word_count, so this is the local target, matching how the offer,
# market and competition stages set their own. The notes are deliberately brief
# -- a distillation of already-synthesised context -- so the target is 150 words
# with a hard harness cap at 300 words, 2x the target.
ICP_FINDINGS_WORD_COUNT = 150
ICP_FINDINGS_WORD_CAP = 300


def _gtm_specialist_for(state: IcpSessionState) -> Optional[Specialist]:
    """Pick the go-to-market specialist out of the team.

    `Specialist.domain == "gtm"` exists precisely so this is a lookup rather than
    a guess at list position. The fallbacks are for a hand-built team that
    skipped the field; they degrade rather than raising, because a persona is
    presentation, not correctness. Deliberately does NOT select by offer_type.
    """
    specialists = [s for s in (state.get("specialists") or []) if s]
    if not specialists:
        return None
    for s in specialists:
        if getattr(s, "domain", None) == "gtm":
            return s
    for s in specialists:
        if getattr(s, "domain", None) in ("product", "service"):
            return s
    for s in specialists:
        if getattr(s, "domain", None) in ("market", "competition"):
            return s
    return specialists[0]


def _buyer_type_value(state: IcpSessionState) -> str:
    """The market stage's buyer-type verdict: b2b / b2c / both, defaulting to b2b.

    Same default the interview-era determine_icp used when the market phase had
    not decided; a b2c/both verdict can only come from the actual market stage.
    """
    market = state.get("market_data")
    if market is not None:
        bt = getattr(market, "buyer_type", None)
        if bt is not None:
            value = bt.value if hasattr(bt, "value") else bt
            if value in ("b2b", "b2c", "both"):
                return value
    return "b2b"


def _icp_emphasis(offer_type: str, buyer_type: str) -> tuple[str, str]:
    """Return (label, branch instructions) choosing how thoroughly the ICP should
    lean on personas + reach channels vs firmographics -- keyed on BOTH the offer
    kind and the buyer type, the two axes a GTM expert actually branches on."""
    kind = offer_type or "product"
    buyer = buyer_type or "b2b"

    if buyer == "b2c":
        if kind == "service":
            return (
                "SERVICE x B2C (consumer service offer)",
                """This is a CONSUMER SERVICE — the buyer is an individual paying for a service, so
INDUSTRIES, COMPANY SIZES and BUYER TITLES are NOT the point of this profile. Instead make
these the core:
- `buyer_personas`: 2-4 sharply-defined CONSUMER personas — each with a name, who they are,
  the job-to-be-done this {offer_noun} helps with, where they congregate (local venues,
  platforms, neighborhoods), and their intent signals.
- `target_channels`: the DISCOVERABLE local venues where those personas actually are — local
  social (WhatsApp, Instagram, TikTok), neighborhood marketplaces, review platforms,
  community pages/groups, creators with local audiences. For each: a concrete name (or a
  typed placeholder), WHY the right audience is there, and a `first_angle` for engaging.
- `event_focus`: local events/meetups/fairs whose attendees match the ICP.
- `messaging_angles`: opening hooks per channel, including trust-building angles (this is a
  service: people pay for reliability and references).
- `beachhead`: one line naming the first segment/channel/neighborhood to attack first.
- `geo`: target geographies by name.
- `exclusions`, `pain_signals`, `intent_keywords`: still required.
- `competitor_leads`: competitors whose CUSTOMERS are prime targets — their review threads,
  complaint platforms and local communities.""",
            )
        return (
            "PRODUCT x B2C (consumer product offer)",
            """This is a CONSUMER PRODUCT — the buyer is an individual adopting a product, so
INDUSTRIES, COMPANY SIZES and BUYER TITLES are NOT the point of this profile. Instead make
these the core:
- `buyer_personas`: 2-4 sharply-defined CONSUMER personas — each with a name, who they are,
  the job-to-be-done this {offer_noun} helps with, where they congregate, and their intent
  signals.
- `target_channels`: the DISCOVERABLE venues where those personas actually are — social
  platforms, communities (subreddits, Discords, Facebook/LinkedIn groups), creators +
  newsletters whose audience matches, and marketplaces/app stores. For each: a concrete name
  (or a typed placeholder), WHY the right audience is there, and a `first_angle` for engaging.
- `event_focus`: the events/summits/meetups whose attendees match the ICP.
- `messaging_angles`: opening hooks per channel — what to say where.
- `beachhead`: one line naming the first segment/channel to attack first.
- `geo`: target geographies by name.
- `exclusions`, `pain_signals`, `intent_keywords`: still required.
- `competitor_leads`: competitors whose USERS/audiences are prime targets — for consumer
  products these are often competitor communities, review threads, or channels where their
  users complain.""",
        )
    if buyer == "both":
        return (
            "BOTH B2B and B2C",
            """This {offer_noun} serves BOTH companies and consumers. Cover both sides:
- B2B side: `industries`, `company_sizes`, `buyer_titles` — the companies that buy.
- Consumer side: `buyer_personas` (named, with where they congregate), `target_channels`
  (social platforms, communities, creators, newsletters, marketplaces, with audience_fit +
  first_angle), and `event_focus` (events/summits/meetups whose attendees match).
- `geo`, `exclusions`, `pain_signals`, `intent_keywords`, `messaging_angles`, `beachhead`:
  whichever segments are relevant.
- `competitor_leads`: companies AND communities/creators whose customers/audiences are prime
  targets.""",
        )
    if kind == "service":
        return (
            "SERVICE x B2B (business service offer)",
            """This {offer_noun} is a SERVICE sold to companies — build the firmographic profile
precisely, with the trust/procurement lens a business service buyer demands:
- `industries`: no more than 3 industries whose companies are the best fit.
- `company_sizes`: concrete size bands the {offer_noun} realistically serves.
- `buyer_titles`: the roles who choose and budget for services like this — the decision
  makers and the operational owners (e.g. ops, procurement, facilities, HR).
- `buyer_personas`: secondary depth — where those named roles congregate, for the account phase.
- `target_channels`: a light list is fine — only venues that clearly concentrate the target
  accounts (relevant industry associations, trade events, professional communities).
- `event_focus`: if a specific summit/conference/meetup concentrates the buyer titles,
  describe the attendees; otherwise leave it empty.
Trust is the currency of service deals: scope the exclusions, pain signals and messaging
angles around risk, reliability and referenceability, geo-scoped to where the {offer_noun}
delivers.""",
        )
    return (
        "PRODUCT x B2B (business product offer)",
        """This {offer_noun} sells to companies — build the firmographic profile precisely,
with the adoption lens a product buyer uses:
- `industries`: no more than 3 industries whose companies are the best fit.
- `company_sizes`: concrete size bands the {offer_noun} realistically serves.
- `buyer_titles`: the job titles/personas who own the problem this {offer_noun} solves —
  the technical buyers who adopt it AND the economic buyers who fund it.
- `buyer_personas`: secondary depth — where the named personas congregate, for the account phase.
- `target_channels`: a light list is fine — only include venues that clearly concentrate the
  target accounts (relevant events/summits, associations, communities the role follows).
- `event_focus`: if a specific summit/conference/meetup concentrates the buyer titles,
  describe the attendees; otherwise leave it empty.""",
    )


def _competition_context_block(state: IcpSessionState) -> str:
    """The structured competition context: the offer-vs-standard SWOD plus, when
    the competition stage produced one, the ideal competitor profile.

    The SWOD used to arrive with a `competitors` list attached and was rendered
    whole; that list is gone from the stage, so the block is now assembled from
    two channels that say different things. The profile names no companies, so
    it cannot source a `competitor_lead` — it supplies the query shapes and
    likely weaknesses those leads are shaped around, and the real names come
    from the [competition findings] prose instead.
    """
    swod = state.get("competition_data")
    profile = state.get("ideal_competitor_profile")

    parts = []
    if swod is not None:
        parts.append(
            "### OFFER VS. COMPETITIVE STANDARD (SWOD)\n"
            + swod.model_dump_json(indent=2, exclude_none=True)
        )
    else:
        parts.append(
            "### OFFER VS. COMPETITIVE STANDARD (SWOD)\n"
            "(not available -- the competition stage has not run)"
        )
    if profile is not None:
        parts.append(
            "### IDEAL COMPETITOR PROFILE (ARCHETYPES)\n"
            "Describes KINDS of company that compete here; names none.\n"
            + profile.model_dump_json(indent=2, exclude_none=True)
        )
    else:
        parts.append(
            "### IDEAL COMPETITOR PROFILE (ARCHETYPES)\n"
            "(not available -- competitor_leads must stay empty rather than invented.)"
        )
    return "\n\n".join(parts)


def _icp_context(state: IcpSessionState) -> str:
    """The evidence every node reads: the offer's own material first
    (budget_context protects the first chunk), then the three sibling stages'
    findings (Sources stripped), then the structured market + competition
    records -- all labelled so the model can cite by label and never by number.
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
            _sibling_block(
                "COMPETITION FINDINGS",
                state.get("competition_findings"),
                state.get("competitive_positioning_understanding"),
            ),
            f"### MARKET CONTEXT (STRUCTURED)\n{_market_context_block(state)}",
            f"### COMPETITION CONTEXT (STRUCTURED)\n{_competition_context_block(state)}",
        ],
        label="icp synthesis",
    )


create_icp_instructions = """
You are {specialist_name}, a {specialist_role} working in {specialist_affiliation}.

YOUR LENS
{specialist_description}

You are the go-to-market specialist for this {offer_noun}. You understand this
{offer_noun}'s category, its buyers and its target geographies — the market and
competition stages have already researched the landscape — and you know the
{offer_noun} itself from its own material. Your job is to turn that
understanding into the IDEAL CUSTOMER PROFILE (ICP) the account-discovery phase
will use to find real targets: companies, and for consumer offers the
communities, platforms, events and creators where the ideal buyers congregate.

This stage is a SYNTHESIS, not a research stage. Nothing has been searched and
nothing will be: every fact you use must come from the material below, so stay
honest with yourself about what is actually supported.

OFFER
- name          : {offer_name}
- type          : {offer_type}
- description   : {offer_description}
- target market : {target_market}

SESSION CONTEXT (what the offer's other stages already established — treat as fact)
{context}

The blocks above are labelled so you can attribute everything you write:
"[offer material]", "[domain findings]", "[market findings]",
"[competition findings]", "[market context]", "[competition context]".

BUYER TYPE
{buyer_type_label}

{buyer_emphasis}

FIELDS
- `product_name`: the {offer_noun} being profiled.
- `buyer_type`: set it to exactly "{buyer_type_value}" — the value is a fact from
  the market context, not a choice; do not paraphrase it.
- `geo`: the target geographies from the market context.
- The buyer-bearing fields the emphasis above directs — fill those richly; keep
  everything else light.
- `exclusions`: be explicit about who is NOT a fit (e.g. "agencies", "hobbyists",
  "consumers outside the target geo"). These become hard filters during account validation.
- `pain_signals`: the problems/intents that indicate an audience/account is actively
  searching for a solution.
- `intent_keywords`: keywords that appear when audiences/accounts are in-market (e.g.
  "evaluate", "switch from", "compare", "rollout"), so searches stay grounded in buying intent.
- `messaging_angles`: opening angles/hooks — how to first engage the audience in each channel.
- `beachhead`: one line naming the segment/channel to attack first.
- `competitor_leads`: derive ONE lead per real competitor NAMED IN THE
  [competition findings] prose — use their exact name, generate 1-2 web queries that surface
  accounts/audiences evaluating or reviewing them, and derive concrete `pain_angles` from
  what the competitive research found their customers complain about. The structured
  [competition context] no longer contains a name list (the competition stage emits an
  archetype profile instead), so the prose is your only source of real names — but the
  profile's `where_to_find_them` and `likely_weaknesses` are where your queries and pain
  angles get their shape. Never invent a competitor that no retrieved source named, and
  never pad the list: if the prose named no rivals, an empty list is the correct answer.

Drive the profile through your distinctive lens, and keep it anchored to the
geographies where this {offer_noun} actually operates.

RULES
1. Be conservative — a tight, high-quality ICP beats a broad, fuzzy one.
2. Everything must be defensible from the blocks provided.
3. If a field cannot be derived, leave it empty rather than guessing.
4. Only synthesize from the context provided here. Do not reach into live research.

Return only the structured ICP. No commentary.
"""


refine_icp_instructions = """
You are {specialist_name}, a {specialist_role} working in {specialist_affiliation}.

YOUR LENS
{specialist_description}

You drafted the ICP below for this {offer_noun}. Review and finalize it before
it seeds account discovery — this is the quality gate that turns a draft into
the load-bearing profile the account phase searches against.

DRAFT ICP
{draft_icp}

SESSION CONTEXT (the same blocks you drafted from — treat as fact)
{context}

BUYER TYPE
{buyer_type_label}

REVIEW RULES
1. Fill every field the evidence supports; leave a field empty when the context
   cannot support it.
2. Prune guesses — anything not defensible from the offer/market/competition
   blocks must go.
3. Buyer-type coherence: for consumer offers the `buyer_personas`, `target_channels`
   and `event_focus` must be rich enough to drive account discovery; for B2B the
   firmographics (`industries`, `company_sizes`, `buyer_titles`) carry the weight.
   Don't let a weak emphasis cripple the profile.
4. Industry discipline: no more than 3 industries — the tightest defensible set wins.
5. `competitor_leads` — CORRECT them, do not clear them. The draft's leads were
   derived from the [competition findings] prose, and a lead whose `name` appears
   in that prose is grounded and MUST be kept: fix its queries or `pain_angles`
   if they drifted, but do not delete a lead just because the structured
   [competition context] beside it carries no name list (it no longer does — the
   competition stage emits an archetype profile instead). Drop a lead only when
   its name appears NOWHERE in the findings prose, and never invent a name or a
   pain angle the prose does not report.
6. Keep `geo` aligned to the market stage's target markets.
7. Expand `target_channels` with concrete names/typed placeholders +
   `audience_fit` + `first_angle` so account discovery can actually search them.
8. Offer-type coherence: for a SERVICE the profile must lean on trust, geo-scoped
   delivery and how people/companies buy services where it operates; for a
   PRODUCT on adoption and how the category is acquired there.

Return the FINAL, complete ICP — no commentary.
"""


note_down_record_instructions = """
You are an expert go-to-market strategist.

Write the RESEARCH NOTES that lay out this {offer_noun}'s IDEAL CUSTOMER PROFILE
and how it will be reached, from the {offer_noun}'s own material, the session's
market and competition context, and the structured ICP finalized for this stage.

These are notes, not a finished report section. A single report is written later
by someone who will also have the domain, market and competition analyses in hand.

- Write NOTES, not report prose. No report title, no "# Heading" scaffolding.
- Be specific and evidence-dense. Another writer cannot recover what you leave out.
- Keep every concrete claim: named industries, size bands, titles, personas,
  channels, communities, events, geographies and exclusion rules.
- Be brief. These notes are conclusions plus the claims that evidence them, not a
  ledger of everything retrieved. Cut reasoning bridges, elaboration, and anything
  the report writer can recover from the sibling stages. When in doubt, leave it
  out.
- The STRUCTURED ICP below is the load-bearing set: ground the notes in it
  exactly. Do not add industries, personas, channels or competitors the record
  does not contain.

What is in front of you:
1. The {offer_noun}'s OWN MATERIAL — authoritative for what the {offer_noun} is
   and who it is for.
2. The DOMAIN, MARKET and COMPETITION blocks — the session's gathered
   understanding; use them to scope and justify the profile, citing by LABEL.
3. The STRUCTURED ICP — the finalized, self-review-passed profile. This is the anchor.

SESSION CONTEXT (the same blocks the ICP was synthesized from — treat as fact)
{context}

STRUCTURED ICP
{icp_data}

CITATIONS
Cite inline by LABEL only — "[offer material]", "[domain findings]",
"[market findings]", "[competition findings]", "[market context]",
"[competition context]", or "[ICP]".
There is NO numbered source list and NO "### Sources" block in this stage: the
ICP is a synthesis and nothing new was retrieved. Never include a URL anywhere
in your notes.

SPECIALIST LENS
{specialist_lens}

COVER
- who the ICP is, exactly — firmographics for B2B (industries, company sizes,
  buyer titles), personas + where they congregate for B2C — and WHY these buyers,
  grounded in the market findings
- where to reach them, per the buyer type: the channels/communities/events/
  creators for consumer offers, the venues that concentrate target accounts for B2B
- the beachhead and the opening move
- messaging angles that fit how this {offer_noun} is actually acquired
  (product: adoption and category; service: trust, delivery and references)
- the competitor-lead surfaces (accounts/audiences evaluating the named competitors)
- exclusions as hard filters, and why they are drawn where they are
- open questions and thin areas — say plainly where the profile rests on
  judgment rather than evidence

Also return `icp_understanding`: a brief standalone synthesis of who the ICP is
and where to reach them. Target 40 words, never exceed 50.

Keep the {offer_noun} as the subject and the target audience as the framing.
Aim for roughly {word_count} words -- a brief, evidence-dense summary of who the
ICP is and where to reach them. Plain short sentences; keep names, sizes,
titles, channels and exclusions exactly as the structured record has them, cut
elaboration.
"""


def create_icp(state: IcpSessionState) -> dict:
    """Draft the structured, buyer-type-aware ICP from the offer's own material
    + the sibling market/competition context. Fails loudly: the ICP is the
    stage's whole output, and a failed draft is a failed stage.

    Anchored on the market stage's buyer_type verdict and the offer's own type
    (the two-axis emphasis), the same way the interview-era generate_icp was
    anchored on buyer type alone.
    """
    offer_noun = _offer_noun(state)
    buyer_value = _buyer_type_value(state)
    buyer_label, buyer_emphasis = _icp_emphasis(state.get("offer_type") or "product", buyer_value)
    specialist = _gtm_specialist_for(state)

    system_message = create_icp_instructions.format(
        specialist_name=specialist.name if specialist else "a go-to-market analyst",
        specialist_role=specialist.role if specialist else f"{offer_noun} GTM strategist",
        specialist_affiliation=specialist.affiliation if specialist else "independent",
        specialist_description=specialist.description if specialist else _specialist_lens(specialist, offer_noun),
        offer_noun=offer_noun,
        offer_name=state.get("offer_name") or f"Unknown {offer_noun}",
        offer_type=state.get("offer_type") or "product",
        offer_description=state.get("offer_description") or "(not captured)",
        target_market=", ".join(state.get("target_market") or []) or "(not captured)",
        context=_icp_context(state),
        buyer_type_label=buyer_label,
        buyer_emphasis=buyer_emphasis,
        buyer_type_value=buyer_value,
    )

    print(f"create_icp: drafting the ICP ({buyer_label}, buyer_type={buyer_value!r})")
    draft = invoke_structured_with_fallback(
        messages=[
            SystemMessage(content=system_message),
            SystemMessage(content="Draft the structured ICP now."),
        ],
        schema=ICP,
        log_label="create_icp",
        # Synthesising a closed-schema profile over already-gathered context is
        # not the deliberation that justifies the flagship thinking cost. Same
        # gate the market/competition planners run under.
        thinking=False,
    )

    print(
        f"create_icp: draft has {len(draft.industries or [])} industrie(s), "
        f"{len(draft.company_sizes or [])} size band(s), {len(draft.buyer_titles or [])} "
        f"title(s), {len(draft.buyer_personas or [])} persona(s), "
        f"{len(draft.target_channels or [])} channel(s), "
        f"{len(draft.competitor_leads or [])} competitor lead(s)"
    )
    return {"icp_data": draft}


def refine_icp(state: IcpSessionState) -> dict:
    """Self-review pass over the draft: fill evidence-backed fields, prune
    guesses, enforce buyer-type + offer-type coherence — the GTM expert's
    quality gate before the profile seeds account discovery."""
    draft = state.get("icp_data")
    offer_noun = _offer_noun(state)
    buyer_value = _buyer_type_value(state)
    buyer_label, _ = _icp_emphasis(state.get("offer_type") or "product", buyer_value)
    specialist = _gtm_specialist_for(state)

    system_message = refine_icp_instructions.format(
        specialist_name=specialist.name if specialist else "a go-to-market analyst",
        specialist_role=specialist.role if specialist else f"{offer_noun} GTM strategist",
        specialist_affiliation=specialist.affiliation if specialist else "independent",
        specialist_description=specialist.description if specialist else _specialist_lens(specialist, offer_noun),
        offer_noun=offer_noun,
        draft_icp=draft.model_dump_json(indent=2, exclude_none=True) if draft else "No draft — build the ICP from the context.",
        context=_icp_context(state),
        buyer_type_label=buyer_label,
    )

    final = invoke_structured_with_fallback(
        messages=[
            SystemMessage(content=system_message),
            SystemMessage(content="Finalize the ICP now."),
        ],
        schema=ICP,
        log_label="refine_icp",
        thinking=False,
    )

    # 'No more than 3 industries' is a rule the GTM expert actually enforces; a
    # schema hint is a suggestion, so the clamp is the bound — same philosophy as
    # the task-count and competitor-set clamps in the sibling pipelines.
    industries = list(final.industries or [])[:3]
    if len(final.industries or []) > 3:
        print(f"refine_icp: industries clamped from {len(final.industries)} to 3")
    final = final.model_copy(update={"industries": industries})

    print(
        f"refine_icp: finalized -- {len(final.industries)} industrie(s), "
        f"{len(final.company_sizes or [])} size band(s), {len(final.buyer_titles or [])} "
        f"title(s), {len(final.buyer_personas or [])} persona(s), "
        f"{len(final.target_channels or [])} channel(s), "
        f"{len(final.competitor_leads or [])} competitor lead(s)"
    )
    return {"icp_data": final}


def note_down_record(state: IcpSessionState) -> dict:
    """Write the narrative findings, anchored on the refined structured ICP.

    Runs AFTER refine_icp — deliberately — so the notes describe the profile
    that actually seeds account discovery, not a superseded draft. Deliberately
    appends NO `### Sources` block: the ICP stage retrieves nothing, and the
    honest synthesis carries label citations only.

    Fails loudly. These fields are the stage's product, and a half-written
    synthesis that still set `icp_complete` would let the report writer build
    on nothing.
    """
    offer_noun = _offer_noun(state)
    lens = _specialist_lens(_gtm_specialist_for(state), offer_noun)
    context = _icp_context(state)
    data = state.get("icp_data")

    system_message = note_down_record_instructions.format(
        offer_noun=offer_noun,
        offer_nouns=_offer_nouns(state),
        specialist_lens=lens,
        icp_data=data.model_dump_json(indent=2, exclude_none=True) if data else "(no structured ICP — the refine pass failed)",
        context=context,
        word_count=ICP_FINDINGS_WORD_COUNT,
    )

    notes = invoke_structured_with_fallback(
        messages=[
            SystemMessage(content=system_message),
            SystemMessage(content="Write the ICP notes now."),
        ],
        schema=IcpFindings,
        log_label="note_down_record",
        # Summarising already-synthesised context — the "summarisation of
        # already-distilled notes" workload the thinking gate classifies as NOT
        # the reasoning that justifies the premium tier. Same gate all four
        # pipelines run their findings writers under.
        thinking=False,
    )

    findings = (notes.findings or "").strip()
    understanding = (notes.icp_understanding or "").strip()

    # The schema asks for 40 words, never more than 50; an LLM cannot be relied
    # on to hit that on its own, and the bound is load-bearing for the report
    # section writer. Clamped here — a hard stop in the harness, not another
    # prompt instruction.
    understanding_words = understanding.split()
    if len(understanding_words) > 50:
        understanding = " ".join(understanding_words[:50])
        print(
            f"note_down_record: icp_understanding clamped from "
            f"{len(understanding_words)} to 50 words"
        )

    # Same hard-stop philosophy for the notes body: the prompt targets
    # ICP_FINDINGS_WORD_COUNT, but an LLM cannot be relied on to hold to it (the
    # pre-brevity writer once returned ~430 words against a 400 target). No
    # Sources block exists in this stage, so the clamp is unconditional.
    findings_words = findings.split()
    if len(findings_words) > ICP_FINDINGS_WORD_CAP:
        findings = " ".join(findings_words[:ICP_FINDINGS_WORD_CAP])
        print(
            f"note_down_record: findings clamped from {len(findings_words)} "
            f"to {ICP_FINDINGS_WORD_CAP} words"
        )

    print(
        f"note_down_record: {len(findings.split())} words of notes, "
        f"icp_understanding in {len(understanding.split())} words"
    )

    return {
        "icp_findings": findings,
        "icp_understanding": understanding,
        "icp_complete": True,
    }


def build_icp_graph(checkpointer: bool = True):
    """create_icp -> refine_icp -> note_down_record.

    The structured record is finalized (create + refine) BEFORE the writer is
    anchored on it — the extract-before-writer discipline of the competition
    stage, applied internally within the record. No conditional edges and no
    cycles, on purpose. See the module docstring.
    """
    builder = StateGraph(IcpSessionState)

    # -- Nodes --
    builder.add_node("create_icp", create_icp)
    builder.add_node("refine_icp", refine_icp)
    builder.add_node("note_down_record", note_down_record)

    # -- Edges --
    builder.add_edge(START, "create_icp")
    builder.add_edge("create_icp", "refine_icp")
    builder.add_edge("refine_icp", "note_down_record")
    builder.add_edge("note_down_record", END)

    return builder.compile()