"""The competition stage end to end with Exa, distillation and the LLM stubbed:
specialist selection, the recency gate on every search, brand-free queries,
the cross-stage sibling context reaching every prompt, the skeleton -> review
-> parallel-detail profile build, clamps, and channel separation -- without a
token or the network."""

import re
import threading
import time

import agents.pipelines.discover.understand_competition as uc
from agents.schemas.competition import (
    ArchetypeDetail,
    CompetitionExtraction,
    CompetitionFindings,
    IdealCompetitorProfile,
    ProfileSkeleton,
)
from agents.schemas.market import MarketExtraction
from agents.schemas.research import ResearchTask, Specialist, TaskList


CALLS = []


def fake_search(query, config, num_results=3, start_published_date=None):
    CALLS.append((query, num_results, start_published_date))
    if "fallback" in query:
        return [
            {"title": "Doc A", "url": f"https://ex.com/{len(CALLS)}a", "text": "x" * 50},
            {"title": "Doc B", "url": "https://ex.com/dup", "text": "y" * 50},
        ]
    return []


def doctor_area(focus: str) -> str:
    """The area name, lifted out of the distill focus string."""
    if "rivals" in focus:
        return "rivals"
    return "background"




PLAN = TaskList(tasks=[
    ResearchTask(area="rivals", objective="who the real rivals are", queries=["specific query", "broad fallback query"]),
    ResearchTask(area="positioning", objective="how they position", queries=["positioning probe"]),
    ResearchTask(area="empty_area", objective="nothing matches", queries=["nothing will match"]),
    ResearchTask(area="no_queries", objective="nothing issued", queries=[]),
    # A deliberate brand leak, as a real run produced: the planner was told not
    # to name the offer and did anyway. Its two queries cover both outcomes --
    # the first was PURE comparison plumbing and must be dropped rather than
    # searched for, the second is clean and must survive untouched.
    ResearchTask(
        area="branded",
        objective="a task the planner got wrong",
        queries=["Acme Vector DB competitors", "vector database competitors"],
    ),
])


DETAIL_CALLS: list[str] = []
ACTIVE, MAX_ACTIVE = [0], [0]
LOCK = threading.Lock()


def _sketch(label: str, scope: str) -> dict:
    return {"label": label, "archetype_description": "a kind of competitor", "geography_scope": scope}


def _assert_extraction_context(body: str) -> None:
    assert "### AREA: rivals" in body, "extract context missing"
    assert "### MARKET FINDINGS" in body, "market sibling context missing from extractor"
    # The de-geo guard: the extractor must be told the market's target_geo is
    # context, not a filter.
    assert "NOT a filter on who competes" in body, (
        "extractor not told that market geo is not a competitor filter"
    )


def fake_llm(messages, schema=None, **kw):
    body = messages[0].content
    if schema is TaskList:
        assert "### DOMAIN FINDINGS" in body, "planner missing the domain sibling block"
        assert "### MARKET FINDINGS" in body, "planner missing the market sibling block"
        assert "Synthesis: sits in the vector-index category" in body, (
            "planner missing the domain stage's understanding"
        )
        assert "b2b" in body, "structured market context must reach the planner"
        assert "https://domain.example" not in body, (
            "sibling Sources block must be stripped before the planner sees it"
        )
        return PLAN
    if schema is CompetitionFindings:
        assert "### AREA: rivals" in body, "bundle block missing from writer"
        assert "IDEAL COMPETITOR PROFILE" in body, "profile anchor missing from writer"
        # The writer must be anchored on the REFINED profile, not the draft: a
        # refined-only archetype appearing here proves refine ran first.
        assert "Refined Archetype" in body, (
            "writer was anchored on the draft profile, not the refined one -- "
            "the refine node must run before the writer"
        )
        assert "### DOMAIN FINDINGS" in body, "domain context missing from writer"
        assert "https://domain.example" not in body, "sibling Sources must not reach the writer"
        assert "b2b" in body, "structured market context must reach the writer"
        # 2 ("### Notes") + 349 = 351 words: exercises the harness clamp down to 300.
        return CompetitionFindings(
            findings="### Notes\n" + " ".join(f"n{i}" for i in range(1, 350)),
            # 60 words: exercises the harness clamp down to 50.
            competitive_positioning_understanding="w1 w2 w3 w4 w5 w6 w7 w8 w9 w10 "
                "w11 w12 w13 w14 w15 w16 w17 w18 w19 w20 w21 w22 w23 w24 w25 "
                "w26 w27 w28 w29 w30 w31 w32 w33 w34 w35 w36 w37 w38 w39 w40 "
                "w41 w42 w43 w44 w45 w46 w47 w48 w49 w50 w51 w52 w53 w54 w55 "
                "w56 w57 w58 w59 w60",
        )
    if schema is ProfileSkeleton:
        blob = "\n".join(m.content for m in messages)
        if "Draft skeleton under review" in blob:
            assert '"label": "Draft Archetype 1"' in blob, "review did not receive the draft"
            return ProfileSkeleton(
                category_definition="Vector search engines (refined)",
                archetypes=[_sketch("Refined Archetype 1", "global")]
                + [_sketch(f"Draft Archetype {i}", "global" if i % 2 else "local") for i in range(2, 10)],
                confidence="high",
            )
        _assert_extraction_context(body)
        return ProfileSkeleton(
            category_definition="vector search engines",
            archetypes=[_sketch(f"Draft Archetype {i}", "global" if i % 2 else "local") for i in range(1, 10)],
            confidence="medium",
        )
    if schema is CompetitionExtraction:
        _assert_extraction_context(body)
        return CompetitionExtraction(
            strengths=["cheap on commodity hardware"],
            weaknesses=["young ecosystem"],
            opportunities=["gap in the local market"],
            differentiators=["storage-shaped reasoning"],
        )
    if schema is ArchetypeDetail:
        label = re.search(r"for the '(.+)' archetype", messages[1].content).group(1)
        with LOCK:
            DETAIL_CALLS.append(label)
            ACTIVE[0] += 1
            MAX_ACTIVE[0] = max(MAX_ACTIVE[0], ACTIVE[0])
        time.sleep(0.05)
        with LOCK:
            ACTIVE[0] -= 1
        if label == "Draft Archetype 3":
            raise RuntimeError("detail call failed")
        return ArchetypeDetail(
            likely_advantages=["wins on X"], likely_weaknesses=["loses on Y"],
            where_to_find_them=["a directory"], confidence="medium",
        )
    raise AssertionError(schema)


STATE = {
    "offer_type": "product",
    "offer_name": "Acme Vector DB",
    "offer_description": "A vector index.",
    "target_market": ["West Africa", "EU"],
    "problem": "Slow nearest-neighbour search.",
    "solution": "A quantised index.",
    "target_users": ["search engineers"],
    "features": ["HNSW", "on-disk compaction"],
    "service_uniqueness": [],
    "how_it_works": "Quantise, then graph-index.",
    "scraped_content": "Acme builds a vector index. " * 40,
    "specialists": [
        Specialist(domain="competition", affiliation="Cc", name="Competition Person", role="Analyst", description="d"),
        Specialist(domain="market", affiliation="Mm", name="Market Person", role="Analyst", description="m"),
    ],
    # -- Sibling stage outputs this stage is REQUIRED to consume --
    "offer_findings": "### Domain notes\nA vector index is a category member.\n\n### Sources\n[1] https://domain.example",
    "offer_domain_fit_understanding": "sits in the vector-index category",
    "market_findings": "### Market notes\nB2B buyers pay $1-5k/yr.\n\n### Sources\n[1] https://market.example",
    "product_market_fit_understanding": "fits the B2B search market",
    "market_data": MarketExtraction(buyer_type="b2b", category="saas"),
}


def test_competition_stage_offline(monkeypatch):
    monkeypatch.setattr(uc, "search_and_scrape", fake_search)
    monkeypatch.setattr(uc, "distill_documents", lambda docs, focus, log_label: "condensed evidence for: " + doctor_area(focus))
    monkeypatch.setattr(uc, "invoke_structured_with_fallback", fake_llm)

    # --- node 1 ---
    out1 = uc.create_tasks_research(STATE)

    state = {**STATE, **out1}

    # --- node 2 ---
    out2 = uc.conduct_research(state)
    state = {**state, **out2}

    # --- node 3 (EXTRACT, before the writer -- the reverse of the market graph) ---
    out3 = uc.extract_competitor_profile(state)
    state = {**state, **out3}

    # --- node 5 ---
    out5 = uc.note_down_record(state)
    state = {**state, **out5}

    # --- assertions ---
    assert [t.area for t in out1["competition_tasks"].tasks] == [
        "rivals", "positioning", "empty_area", "no_queries", "branded",
    ]
    assert CALLS[0][0] == "specific query", "most specific query must be issued first"
    # 5 searches total: rivals burns its specific query then falls back (2),
    # positioning and empty_area each issue their single query and come back empty (2),
    # no_queries issues none (0), and `branded` contributes its one surviving clean
    # query (1) -- the branded one is scrubbed away before it can be searched.
    assert len(CALLS) == 5, f"expected 5 searches, got {len(CALLS)}: {CALLS}"
    assert all(n == 3 for _, n, _ in CALLS), "num_results must be 3"
    assert all(r is not None for _, _, r in CALLS), (
        f"competition research must recency-gate every search; un-gated calls: "
        f"{[i for i, (_, _, r) in enumerate(CALLS) if r is None]}"
    )

    b = {x.area: x for x in out2["competition_task_research"]}
    assert b["rivals"].queries == ["specific query", "broad fallback query"], b["rivals"].queries
    assert b["rivals"].search_failed is False and len(b["rivals"].sources) == 2
    assert b["positioning"].search_failed is True
    assert b["empty_area"].search_failed is True
    assert b["no_queries"].search_failed is True and b["no_queries"].queries == []

    # Brand-free search is enforced in code, not trusted from the prompt. The
    # planner was handed a query naming the offer; neither the name nor the
    # comparison plumbing it was wrapped in survived into the plan, the bundle, or
    # a single issued query.
    tasks_by_area = {t.area: t for t in out1["competition_tasks"].tasks}
    assert tasks_by_area["branded"].queries == ["vector database competitors"], (
        f"the pure-comparison query should be dropped and the clean one kept: "
        f"{tasks_by_area['branded'].queries}"
    )
    assert b["branded"].queries == ["vector database competitors"]
    issued = [q for q, _, _ in CALLS]
    assert not any("acme vector db" in q.lower() for q in issued), f"brand reached a search: {issued}"
    assert "Acme Vector DB competitors" not in issued, (
        "a query that was nothing but the brand plus a comparison word should never "
        "be searched; it returns exactly the listicle SEO the brand-free rule exists "
        "to avoid"
    )
    # ...and the generic noun inside the brand name is never collateral damage: it
    # is the category these queries are actually about.
    assert any("vector database competitors" == q for q in issued), f"clean query lost: {issued}"

    # skeleton -> review -> parallel details: the shipped profile is the REVIEWED
    # skeleton, every archetype detailed in parallel, clamped, and a failed detail
    # keeps its sketch rather than vanishing.
    profile = out3.get("ideal_competitor_profile")
    assert isinstance(profile, IdealCompetitorProfile), type(profile)
    labels = [a.label for a in profile.archetypes]
    assert labels[0] == "Refined Archetype 1", "the reviewed skeleton must be the one detailed"
    # 9 sketches -> clamped to MAX_ARCHETYPES (8), without duplicates.
    assert len(labels) == 8 and len(set(labels)) == 8, labels
    assert sorted(DETAIL_CALLS) == sorted(labels), "every archetype gets exactly one detail call"
    assert MAX_ACTIVE[0] > 1, "archetype details must run in parallel"
    by_label = {a.label: a for a in profile.archetypes}
    assert by_label["Draft Archetype 3"].where_to_find_them == [] and by_label["Draft Archetype 3"].confidence == "low", (
        "a failed detail call keeps the sketch with empty detail, not a dropped archetype"
    )
    assert by_label["Draft Archetype 2"].where_to_find_them == ["a directory"]
    assert profile.category_definition == "Vector search engines (refined)", "definition keeps its case"
    # The de-geo invariant: the profile must not be all-local.
    assert {a.geography_scope for a in profile.archetypes} & {"global", "regional", "any"}, (
        "profile collapsed to local-only; the stage must span international operators"
    )

    data = out3.get("competition_data")
    assert isinstance(data, CompetitionExtraction), type(data)
    assert data.strengths == ["cheap on commodity hardware"]

    # The stage must not import or call a URL verifier any more: an archetype has
    # no website to probe, and the old loop was the stage's dominant Exa cost.
    assert not hasattr(uc, "scrape_url"), (
        "understand_competition still imports scrape_url -- the competitor-URL "
        "verification loop should have been deleted with the named competitor set"
    )

    assert out5["competition_complete"] is True
    assert out5["competition_findings"].startswith("### Notes")
    assert len(out5["competitive_positioning_understanding"].split()) == 50, (
        "positioning understanding must be clamped to 50 words"
    )

    # findings clamp: the 351-word canned reply is cut to the 300-word cap before
    # the harness appends the real ### Sources block.
    findings_body = out5["competition_findings"].split("### Sources")[0].strip()
    assert len(findings_body.split()) == 300, (
        f"findings must be clamped to 300 words, got {len(findings_body.split())}"
    )

    # channel separation: the competition stage writes its own channels, never the
    # offer's or the market's.
    assert "competition_tasks" in out1 and "tasks" not in out1
    assert "competition_task_research" in out2 and "task_research" not in out2
    assert "competition_findings" in out5 and "offer_findings" not in out5
    assert "competition_data" in out3 and "market_data" not in out3
    # The profile lives in its own channel and never contaminates the SWOD record.
    assert "ideal_competitor_profile" in out3 and "ideal_competitor_profile" not in out5

    # specialist selection is by domain "competition", not position.
    assert uc._competition_specialist_for(STATE).name == "Competition Person"
    # ...and degrades to the market-person fallback if the team has no competition slot.
    assert uc._competition_specialist_for({**STATE, "specialists": STATE["specialists"][1:]}).name == "Market Person"

    # Source-stripping helper behaves: the sibling block drops everything after ### Sources.
    assert "https://domain.example" not in uc._strip_sources_block(STATE["offer_findings"])


def test_empty_skeleton_is_retried_once(monkeypatch):
    calls = []

    def fake(messages, schema=None, **kw):
        calls.append((schema, messages[1].content))
        if schema is ProfileSkeleton and "must contain" not in messages[1].content:
            return ProfileSkeleton(category_definition="x", archetypes=[])
        if schema is ProfileSkeleton:
            return ProfileSkeleton(category_definition="x", archetypes=[_sketch("Only One", "global")])
        if schema is ArchetypeDetail:
            return ArchetypeDetail(where_to_find_them=["a directory"], confidence="medium")
        return CompetitionExtraction(strengths=["s"])
    monkeypatch.setattr(uc, "invoke_structured_with_fallback", fake)
    out = uc.extract_competitor_profile(STATE)
    assert [a.label for a in out["ideal_competitor_profile"].archetypes] == ["Only One"]
    assert sum(1 for schema, _ in calls if schema is ProfileSkeleton and True) >= 2
