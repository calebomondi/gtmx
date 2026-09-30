"""Dry run of the competition-understanding subgraph with Exa, distillation, the
LLM and competitor-URL scraping stubbed.

Checks the node logic end to end -- competition-specialist selection, prompt
rendering, query fallback ordering, the RECENCY gate on every search, the
cross-stage sibling context (offer + market findings, Sources stripped) reaching
every consumer prompt, the extract-before-writer ordering, the 3-5 competitor
clamp, the in-node dead-URL drop, the writer's anchor on the structured
competitor set, the 50-word positioning clamp, and the final state -- without
spending a token or touching the network.
"""

import sys

import agents.sub_agents.understand_competition as uc
from agents.states import CompetitionExtraction, CompetitionFindings, MarketExtraction
from agents.sub_agents.schema_states import ResearchTask, Specialist, TaskList


# --- stub Exa: first query for each task returns nothing, second returns docs ---
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


uc.search_and_scrape = fake_search
uc.distill_documents = lambda docs, focus, log_label: (
    "condensed evidence for: " + doctor_area(focus)
)


PLAN = TaskList(tasks=[
    ResearchTask(area="rivals", objective="who the real rivals are", queries=["specific query", "broad fallback query"]),
    ResearchTask(area="positioning", objective="how they position", queries=["positioning probe"]),
    ResearchTask(area="empty_area", objective="nothing matches", queries=["nothing will match"]),
    ResearchTask(area="no_queries", objective="nothing issued", queries=[]),
])


def fake_scrape_url(url, config):
    if "dead" in url:
        raise RuntimeError("dead url")
    return "<html>ok</html>"


uc.scrape_url = fake_scrape_url


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
        assert "STRUCTURED COMPETITOR SET" in body, "competitor-set anchor missing from writer"
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
    if schema is CompetitionExtraction:
        assert "### AREA: rivals" in body, "extract context missing"
        assert "### MARKET FINDINGS" in body, "market sibling context missing from extractor"
        return CompetitionExtraction(
            competitors=[
                {
                    "name": f"Rival {i}",
                    "description": "a real rival",
                    "website": "https://dead.example" if i == 1 else f"https://rival{i}.example",
                    "offering": "a rival offering",
                    "positioning": "positions against the offer",
                    "comparison": "rival wins on X, loses on Y",
                    "feature_flags": {"HNSW": True, "on-disk compaction": i % 2 == 0},
                }
                for i in range(1, 7)
            ],
            strengths=["cheap on commodity hardware"],
            weaknesses=["young ecosystem"],
            opportunities=["gap in the local market"],
            differentiators=["storage-shaped reasoning"],
        )
    raise AssertionError(schema)


uc.invoke_structured_with_fallback = fake_llm

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

# --- node 1 ---
out1 = uc.create_tasks_research(STATE)
print("\n[1] tasks:", [t.area for t in out1["competition_tasks"].tasks])

state = {**STATE, **out1}

# --- node 2 ---
out2 = uc.conduct_research(state)
state = {**state, **out2}
print("[2] queries issued:", [q for q, _, _ in CALLS])
print("[2] recency gated:", [r for _, _, r in CALLS if r])
print("[2] bundles:", [(b.area, b.search_failed, len(b.sources)) for b in out2["competition_task_research"]])

# --- node 3 (EXTRACT, before the writer -- the reverse of the market graph) ---
out3 = uc.extract_competition_data(state)
state = {**state, **out3}
print("[3] competition_data:", out3.get("competition_data"))

# --- node 4 ---
out4 = uc.note_down_record(state)
state = {**state, **out4}
print("[4] keys:", sorted(out4))
print("[4] positioning words:", len(out4["competitive_positioning_understanding"].split()))

# --- assertions ---
assert [t.area for t in out1["competition_tasks"].tasks] == ["rivals", "positioning", "empty_area", "no_queries"]
assert CALLS[0][0] == "specific query", "most specific query must be issued first"
# 4 searches total: rivals burns its specific query then falls back (2),
# positioning and empty_area each issue their single query and come back empty (2),
# and no_queries issues none (0).
assert len(CALLS) == 4, f"expected 4 searches, got {len(CALLS)}: {CALLS}"
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

# extract-before-writer: the structured set is what the writer is anchored on.
data = out3.get("competition_data")
assert isinstance(data, CompetitionExtraction), type(data)
names = [c.name for c in data.competitors]
# 6 extracted -> clamped to 5; Rival 1's dead website dropped, Rival 6 clamped away.
assert len(data.competitors) == 4, f"expected 4 after clamp+verify, got {names}: {names if len(names) <= 10 else ''}"
assert "Rival 1" not in names and "Rival 6" not in names, f"clamp/verify failed: {names}"
assert data.strengths == ["cheap on commodity hardware"]
assert data.competitors[0].feature_flags["HNSW"] is True, "feature_flags must survive as a real dict"

assert out4["competition_complete"] is True
assert out4["competition_findings"].startswith("### Notes")
assert len(out4["competitive_positioning_understanding"].split()) == 50, (
    "positioning understanding must be clamped to 50 words"
)

# findings clamp: the 351-word canned reply is cut to the 300-word cap before
# the harness appends the real ### Sources block.
findings_body = out4["competition_findings"].split("### Sources")[0].strip()
assert len(findings_body.split()) == 300, (
    f"findings must be clamped to 300 words, got {len(findings_body.split())}"
)

# channel separation: the competition stage writes its own channels, never the
# offer's or the market's.
assert "competition_tasks" in out1 and "tasks" not in out1
assert "competition_task_research" in out2 and "task_research" not in out2
assert "competition_findings" in out4 and "offer_findings" not in out4
assert "competition_data" in out3 and "market_data" not in out3

# specialist selection is by domain "competition", not position.
assert uc._competition_specialist_for(STATE).name == "Competition Person"
# ...and degrades to the market-person fallback if the team has no competition slot.
assert uc._competition_specialist_for({**STATE, "specialists": STATE["specialists"][1:]}).name == "Market Person"

# Source-stripping helper behaves: the sibling block drops everything after ### Sources.
assert "https://domain.example" not in uc._strip_sources_block(STATE["offer_findings"])

print("\ncompetition dry-run OK")
sys.exit(0)