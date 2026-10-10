"""Dry run of the offer-domain subgraph with Exa, distillation and the LLM stubbed.

Checks the node logic end to end -- specialist selection, prompt rendering,
query fallback ordering, bundle accumulation, and the final state -- without
spending a token or touching the network.
"""

import sys
import types

import agents.sub_agents.discover.understand_offer as uo
from agents.states import ProductFindings
from agents.sub_agents.schema_states import OfferSessionState, Perspectives, Specialist, TaskList


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


uo.search_and_scrape = fake_search
uo.distill_documents = lambda docs, focus, log_label="": (
    f"[distilled {len(docs)} doc(s)] focus={focus[:40]!r}"
)
uo.Config = lambda: "CFG"

PLAN = TaskList(
    tasks=[
        {"area": "background", "objective": "Establish category background",
         "queries": ["specific query", "broad fallback query"]},
        {"area": "mechanisms", "objective": "Establish the architecture",
         "queries": ["arch query"]},
        {"area": "empty_area", "objective": "Establish contested ground",
         "queries": ["nothing matches"]},
        {"area": "no_queries", "objective": "Planner produced no queries", "queries": []},
    ]
)


def fake_llm(messages, schema=None, **kw):
    if schema is TaskList:
        return PLAN
    if schema is ProductFindings:
        body = messages[0].content
        assert "### AREA: background" in body, "bundle block missing"
        assert "No usable sources" in body, "empty-area gap not surfaced"
        # 2 ("### Notes") + 349 = 351 words: exercises the harness clamp down to 300.
        return ProductFindings(
            findings="### Notes\n" + " ".join(f"n{i}" for i in range(1, 350)),
            product_domain_understanding="fits its category",
        )
    raise AssertionError(schema)


uo.invoke_structured_with_fallback = fake_llm

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
out1 = uo.create_tasks_research(STATE)
print("\n[1] tasks:", [t.area for t in out1["tasks"].tasks])

state = {**STATE, **out1}

# --- node 2 ---
out2 = uo.conduct_research(state)
state = {**state, **out2}
print("[2] queries issued:", [q for q, _, _ in CALLS])
print("[2] recency gated:", [r for _, _, r in CALLS if r])
print("[2] bundles:", [(b.area, b.search_failed, len(b.sources)) for b in out2["task_research"]])

# --- node 3 ---
out3 = uo.note_down_record(state)
print("[3] keys:", sorted(out3))
print("[3] fit:", out3["offer_domain_fit_understanding"])

# --- assertions ---
assert [t.area for t in out1["tasks"].tasks] == ["background", "mechanisms", "empty_area", "no_queries"]
assert CALLS[0][0] == "specific query", "most specific query must be issued first"
# 4 searches total: background burns its specific query then falls back (2),
# mechanisms and empty_area each issue their single query and come back empty (2),
# and no_queries issues none (0).
assert len(CALLS) == 4, f"expected 4 searches, got {len(CALLS)}: {CALLS}"
assert all(n == 3 for _, n, _ in CALLS), "num_results must be 3"
assert all(r is None for _, _, r in CALLS), "domain research must not recency-gate"
b = {x.area: x for x in out2["task_research"]}
assert b["background"].queries == ["specific query", "broad fallback query"], b["background"].queries
assert b["background"].search_failed is False and len(b["background"].sources) == 2
assert b["mechanisms"].search_failed is True
assert b["empty_area"].search_failed is True
assert b["no_queries"].search_failed is True and b["no_queries"].queries == []
assert out3["offer_under_complete"] is True
assert out3["offer_findings"].startswith("### Notes")

# findings clamp: the 351-word canned reply is cut to the 300-word cap before
# the harness appends the real ### Sources block.
findings_body = out3["offer_findings"].split("### Sources")[0].strip()
assert len(findings_body.split()) == 300, (
    f"findings must be clamped to 300 words, got {len(findings_body.split())}"
)

# specialist selection is by domain, not position
assert uo._specialist_for(STATE).name == "Product Person"
print("\nOK - all node assertions passed")
