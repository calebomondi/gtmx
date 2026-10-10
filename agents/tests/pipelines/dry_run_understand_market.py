"""Dry run of the market-understanding subgraph with Exa, distillation and the
LLM stubbed.

Checks the node logic end to end -- market-specialist selection, prompt
rendering, query fallback ordering, the RECENCY gate on every search (the
deliberate inversion of understand_offer, which must NOT recency-gate), bundle
accumulation into the dedicated market_* channels, and the final state --
without spending a token or touching the network.
"""

import sys

import agents.pipelines.discover.understand_market as um
from agents.states import MarketExtraction, MarketFindings
from agents.pipelines.schema_states import ResearchTask, Specialist, TaskList


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


um.search_and_scrape = fake_search
um.distill_documents = lambda docs, focus, log_label: (
    "condensed evidence for: " + doctor_area(focus)
)

def doctor_area(focus: str) -> str:
    """The area name, lifted out of the distill focus string."""
    if "buyer segments" in focus:
        return "buyer segments"
    return "background"


PLAN = TaskList(tasks=[
    ResearchTask(area="buyer segments", objective="who buys", queries=["specific query", "broad fallback query"]),
    ResearchTask(area="pricing norms", objective="what they pay", queries=["pricing probe"]),
    ResearchTask(area="empty_area", objective="nothing matches", queries=["nothing will match"]),
    ResearchTask(area="no_queries", objective="nothing issued", queries=[]),
])


def fake_llm(messages, schema=None, **kw):
    if schema is TaskList:
        return PLAN
    if schema is MarketFindings:
        body = messages[0].content
        assert "### AREA: buyer segments" in body, "bundle block missing"
        assert "### AREA: pricing norms" in body, "second bundle missing"
        assert "No usable sources" in body, "empty-area gap not surfaced"
        assert "own material" in body, "offer material must lead the context"
        return MarketFindings(
            findings="### Notes\nbody\n\n### Sources\n[1] https://ex.com/dup",
            product_market_fit_understanding="fits its market",
        )
    if schema is MarketExtraction:
        body = messages[0].content
        assert "### AREA: buyer segments" in body, "extract context missing"
        return MarketExtraction(
            market_fit="moderate",
            market_fit_reasoning="demand evidence supports a moderate verdict",
        )
    raise AssertionError(schema)


um.invoke_structured_with_fallback = fake_llm

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
        Specialist(domain="market", affiliation="Ma", name="Market Person", role="Analyst", description="d"),
        Specialist(domain="product", affiliation="Pa", name="Product Person", role="Engineer", description="index nerd"),
    ],
}

# --- node 1 ---
out1 = um.create_tasks_research(STATE)
print("\n[1] tasks:", [t.area for t in out1["market_tasks"].tasks])

state = {**STATE, **out1}

# --- node 2 ---
out2 = um.conduct_research(state)
state = {**state, **out2}
print("[2] queries issued:", [q for q, _, _ in CALLS])
print("[2] recency gated:", [r for _, _, r in CALLS if r])
print("[2] bundles:", [(b.area, b.search_failed, len(b.sources)) for b in out2["market_task_research"]])

# --- node 3 ---
out3 = um.note_down_record(state)
state = {**state, **out3}
print("[3] keys:", sorted(out3))
print("[3] fit:", out3["product_market_fit_understanding"])

# --- node 4 ---
out4 = um.extract_market_data(state)
state = {**state, **out4}
print("[4] market_data:", out4.get("market_data"))

# --- assertions ---
assert [t.area for t in out1["market_tasks"].tasks] == ["buyer segments", "pricing norms", "empty_area", "no_queries"]
assert CALLS[0][0] == "specific query", "most specific query must be issued first"
# 4 searches total: buyer segments burns its specific query then falls back (2),
# pricing norms and empty_area each issue their single query and come back empty (2),
# and no_queries issues none (0).
assert len(CALLS) == 4, f"expected 4 searches, got {len(CALLS)}: {CALLS}"
assert all(n == 3 for _, n, _ in CALLS), "num_results must be 3"
assert all(r is not None for _, _, r in CALLS), (
    f"market research must recency-gate every search; un-gated calls: "
    f"{[i for i, (_, _, r) in enumerate(CALLS) if r is None]}"
)

b = {x.area: x for x in out2["market_task_research"]}
assert b["buyer segments"].queries == ["specific query", "broad fallback query"], b["buyer segments"].queries
assert b["buyer segments"].search_failed is False and len(b["buyer segments"].sources) == 2
assert b["pricing norms"].search_failed is True
assert b["empty_area"].search_failed is True
assert b["no_queries"].search_failed is True and b["no_queries"].queries == []

assert out3["market_complete"] is True
assert out3["market_findings"].startswith("### Notes")
assert isinstance(out4.get("market_data"), MarketExtraction)
assert out4["market_data"].market_fit == "moderate"
assert out4["market_data"].market_fit_reasoning

# channel separation: the market stage writes its own channels, never the offer's
assert "market_tasks" in out1 and "tasks" not in out1
assert "market_task_research" in out2 and "task_research" not in out2
assert "market_findings" in out3 and "offer_findings" not in out3

# specialist selection is by domain "market", not position
assert um._market_specialist_for(STATE).name == "Market Person"

print("\nmarket dry-run OK")
sys.exit(0)