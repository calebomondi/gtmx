"""Dry run of the ICP-understanding subgraph with the LLM stubbed.

Checks the node logic end to end -- gtm-specialist selection, the offer-type x
buyer-type emphasis branching, prompt rendering (all six labelled context
blocks, sibling Sources stripped), the draft -> refine -> write ordering, the
industry clamp in refine, the 50-word understanding clamp in note_down_record,
and the final state -- without spending a token or touching the network.

Deliberately asserts NOTHING about recency or search fallback: unlike the offer/
market/competition stages this pipeline performs no research, so there is no
search to gate. That absence is the point, and the structural asserts below
(documenting which channels exist) are how the dry run pins it.
"""

import sys

import agents.pipelines.discover.build_icp as b
from agents.schemas.competition import CompetitionExtraction
from agents.schemas.icp import ICP, IcpFindings
from agents.schemas.market import MarketExtraction
from agents.schemas.research import Specialist


def fake_llm(messages, schema=None, **kw):
    """The stage's only LLM dependency, stubbed to act as a faithful confirmer.

    Both create_icp and refine_icp ask for `ICP`; the two are told apart by the
    refine prompt's DRAFT ICP block, which is the load-bearing hand-off this
    dry run is here to pin.
    """
    body = messages[0].content

    if schema is IcpFindings:
        # The writer must be anchored on the structured record and see the same
        # label-stripped sibling context, and must never see sibling URLs.
        assert "STRUCTURED ICP" in body, "writer missing the structured ICP anchor"
        assert "### DOMAIN FINDINGS" in body, "writer missing the domain sibling block"
        assert "### MARKET FINDINGS" in body, "writer missing the market sibling block"
        assert "### COMPETITION FINDINGS" in body, "writer missing the competition sibling block"
        assert "### MARKET CONTEXT (STRUCTURED)" in body, "writer missing the structured market context"
        assert "### COMPETITION CONTEXT (STRUCTURED)" in body, "writer missing the structured competition context"
        assert "Synthesis: sits in the vector-index category" in body, (
            "writer missing the domain stage's understanding"
        )
        assert "https://domain.example" not in body, "sibling Sources must not reach the writer"
        assert "https://market.example" not in body, "sibling Sources must not reach the writer"
        assert "https://competition.example" not in body, "sibling Sources must not reach the writer"
        return IcpFindings(
            findings="### Notes\nbody",
            # 60 words: exercises the harness clamp down to 50.
            icp_understanding="w1 w2 w3 w4 w5 w6 w7 w8 w9 w10 "
                "w11 w12 w13 w14 w15 w16 w17 w18 w19 w20 w21 w22 w23 w24 w25 "
                "w26 w27 w28 w29 w30 w31 w32 w33 w34 w35 w36 w37 w38 w39 w40 "
                "w41 w42 w43 w44 w45 w46 w47 w48 w49 w50 w51 w52 w53 w54 w55 "
                "w56 w57 w58 w59 w60",
        )

    if schema is ICP:
        if "DRAFT ICP" in body:
            # The refine pass: it must see the draft it is asked to finalize,
            # the same stripped sibling context, and the buyer-type label.
            assert "industry-1" in body, "refine prompt missing the drafted ICP JSON"
            assert "### COMPETITION FINDINGS" in body, "refine missing competition sibling context"
            assert "PRODUCT x B2B" in body, "refine missing the buyer-type label"
            assert "https://competition.example" not in body, "sibling Sources must not reach the refiner"
            return ICP(industries=[f"industry-{i}" for i in range(1, 7)])
        # The create pass: labour all six labelled blocks, the 2x2-aware branch
        # label, the buyer_type fact, and the URL-stripping invariant.
        assert "### DOMAIN FINDINGS" in body, "create missing the domain sibling block"
        assert "### MARKET FINDINGS" in body, "create missing the market sibling block"
        assert "### COMPETITION FINDINGS" in body, "create missing the competition sibling block"
        assert "### MARKET CONTEXT (STRUCTURED)" in body, "create missing the structured market context"
        assert "### COMPETITION CONTEXT (STRUCTURED)" in body, "create missing the structured competition context"
        assert "Synthesis: sits in the vector-index category" in body, (
            "create missing the domain stage's understanding"
        )
        assert "PRODUCT x B2B" in body, "create not on the product x b2b branch"
        assert '"b2b"' in body, "create missing the structured buyer_type verdict"
        assert "https://domain.example" not in body, "sibling Sources must be stripped before the draft"
        assert "https://market.example" not in body, "sibling Sources must be stripped before the draft"
        assert "https://competition.example" not in body, "sibling Sources must be stripped before the draft"
        assert "DRAFT ICP" not in body, "create must not see a draft it has not written"
        return ICP(
            buyer_type="b2b",
            industries=[f"industry-{i}" for i in range(1, 7)],  # 6 -> clamped at refine
            company_sizes=["10-50", "51-200"],
            buyer_titles=["Head of Engineering"],
            geo=["West Africa"],
        )

    raise AssertionError(f"unexpected schema: {schema}")


b.invoke_structured_with_fallback = fake_llm


STATE = {
    "offer_type": "product",
    "offer_name": "MirosVB",
    "offer_description": "A vector index.",
    "target_market": ["West Africa", "EU"],
    "problem": "Slow nearest-neighbour search.",
    "solution": "A quantised index.",
    "target_users": ["search engineers"],
    "features": ["HNSW", "on-disk compaction"],
    "service_uniqueness": [],
    "how_it_works": "Quantise, then graph-index.",
    "scraped_content": "MirosVB builds a vector index. " * 40,
    "specialists": [
        Specialist(domain="gtm", affiliation="MVC Studio", name="GTM Person", role="GTM specialist", description="d"),
        Specialist(domain="market", affiliation="Mm", name="Market Person", role="Analyst", description="m"),
    ],
    # -- Sibling stage outputs this stage is REQUIRED to consume --
    "offer_findings": "### Domain notes\nA vector index is a category member.\n\n### Sources\n[1] https://domain.example",
    "offer_domain_fit_understanding": "sits in the vector-index category",
    "market_findings": "### Market notes\nB2B buyers pay $1-5k/yr.\n\n### Sources\n[1] https://market.example",
    "product_market_fit_understanding": "fits the B2B search market",
    "market_data": MarketExtraction(buyer_type="b2b", category="saas", target_geo=["West Africa", "EU"]),
    "competition_findings": "### Competition notes\nRivals are cheap on commodity hardware.\n\n### Sources\n[1] https://competition.example",
    "competitive_positioning_understanding": "storage-shaped reasoning wins on cost/cadence",
    # competitor_leads derive only from THIS set, so it must carry the names.
    "competition_data": CompetitionExtraction(
        strengths=["cheap on commodity hardware"],
        weaknesses=["young ecosystem"],
        opportunities=["gap in the local market"],
        differentiators=["storage-shaped reasoning"],
    ),
}

# --- structural checks first (they pin what the stage is and is not) ---
assert "icp_tasks" not in STATE and "icp_task_research" not in STATE
assert not hasattr(b, "search_and_scrape") and not hasattr(b, "scrape_url"), (
    "the ICP stage must not import search/scrape tools at all"
)
for combo, label in [
    (("product", "b2b"), "PRODUCT x B2B (business product offer)"),
    (("product", "b2c"), "PRODUCT x B2C (consumer product offer)"),
    (("service", "b2b"), "SERVICE x B2B (business service offer)"),
    (("service", "b2c"), "SERVICE x B2C (consumer service offer)"),
    (("product", "both"), "BOTH B2B and B2C"),
    (("service", "both"), "BOTH B2B and B2C"),
]:
    got, _ = b._icp_emphasis(*combo)
    assert got == label, f"_icp_emphasis{combo} -> {got!r}, expected {label!r}"

# gtm specialist is selected by domain, and only then by the market fallback.
assert b._gtm_specialist_for(STATE).name == "GTM Person", "gtm specialist must win"
assert b._gtm_specialist_for({**STATE, "specialists": STATE["specialists"][1:]}).name == "Market Person", (
    "must degrade to the market fallback without a gtm slot"
)
# The buyer-type verdict comes from the market stage; the interview-era default
# is b2b when no verdict exists.
assert b._buyer_type_value(STATE) == "b2b"
assert b._buyer_type_value({**STATE, "market_data": None}) == "b2b", "default buyer type must be b2b"

# Source-stripping helper behaves: the sibling block drops everything after ### Sources.
assert "https://domain.example" not in b._sibling_block("x", STATE["offer_findings"], None)

# --- node 1: draft ---
out1 = b.create_icp(STATE)
print("\n[1] draft industries:", out1["icp_data"].industries)
state = {**STATE, **out1}

# --- node 2: refine (clamps the industry set to 3) ---
out2 = b.refine_icp(state)
state = {**state, **out2}
print("[2] finalized industries:", state["icp_data"].industries)

# --- node 3: write (clamps the understanding to 50 words) ---
out3 = b.note_down_record(state)
state = {**state, **out3}
print("[3] keys:", sorted(out3))
print("[3] understanding words:", len(out3["icp_understanding"].split()))

# --- assertions ---
assert isinstance(out1["icp_data"], ICP)
assert out1["icp_data"].buyer_type == "b2b"
assert len(out1["icp_data"].industries) == 6, "draft must keep all six industries pre-clamp"

assert isinstance(out2["icp_data"], ICP)
assert len(out2["icp_data"].industries) == 3, "refine must clamp the draft's 6 industries to 3"

assert out3["icp_complete"] is True
assert out3["icp_findings"].startswith("### Notes")
assert len(out3["icp_understanding"].split()) == 50, (
    "icp_understanding must be clamped to 50 words"
)

# channel separation: the ICP stage writes its own channels, never the
# offer's, the market's or the competition's.
assert "icp_data" in out1 and "market_data" not in out1 and "competition_data" not in out1
assert "icp_findings" in out3 and "offer_findings" not in out3 and "market_findings" not in out3
assert "icp_understanding" in out3 and "icp_tasks" not in out1 and "icp_task_research" not in out2

# graph shape: three nodes, linear, no cycles, never recency-gated.
graph = b.build_icp_graph(checkpointer=False)
node_names = {n for n in graph.nodes if not n.startswith("__")}
assert node_names == {"create_icp", "refine_icp", "note_down_record"}, node_names

print("\nicp dry-run OK")
sys.exit(0)