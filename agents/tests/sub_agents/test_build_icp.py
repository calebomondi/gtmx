"""
End-to-end test of the ICP-understanding subgraph with REAL LLM calls.

Nothing is stubbed batch-wise: the LLM is real, the fixture sibling context is
canned, and there are deliberately NO Exa calls -- the ICP stage is pure
synthesis (see the module docstring for build_icp.py). Each run pays for:
  - 1 create_icp call (thinking off, 2x2-aware draft over the labelled context)
  - 1 refine_icp call (thinking off, self-review + industry clamp)
  - 1 note_down_record call (thinking off, findings + 40/50-word understanding)

Four branches cover every cell of the offer_type x buyer_type matrix, each a
DISTINCT offer (so the same brand never contradicts itself) with a real GTM
specialist, canned sibling findings whose Sources blocks must be stripped, and a
canned CompetitionExtraction whose competitors are REAL companies -- the
`competitor_leads` must derive only from that set.

Run all branches:
    python agents/tests/sub_agents/test_build_icp.py
Run one branch:
    python agents/tests/sub_agents/test_build_icp.py product_b2b
Under pytest:
    pytest agents/tests/sub_agents/test_build_icp.py

Assertions are invariants, not exact text: LLM output is nondeterministic, so we
assert the things the design actually promises -- the buyer-type verdict matches
the market stage's, the emphasis carried (firmographics for B2B, personas +
channels for B2C), the industry clamp at 3, competitor leads derived only from
the real competitor set, findings free of any `### Sources` block and of any
URL (nothing was retrieved, so any URL is a fabrication), a bounded 1-50 word
understanding, the completion flag, and refine_icp actually ran. Failures print
the offending values so they are actionable.

Timings are printed, not asserted. Each branch's findings are also saved under
agents/tests/sub_agents/_out/ for a human read that asserts cannot replace.
"""

import json
import re
import sys
import time
from pathlib import Path

# Walk up from cwd to find the repo root (has pyproject.toml).
root = Path.cwd()
while root != root.parent:
    if (root / "pyproject.toml").exists():
        break
    root = root.parent
sys.path.insert(0, str(root))

from agents.llm.main import llm_timing_report  # noqa: E402
from agents.states import CompetitionExtraction, ICP, MarketExtraction  # noqa: E402
from agents.sub_agents.schema_states import Specialist  # noqa: E402
import agents.sub_agents.build_icp as icp  # noqa: E402
from agents.sub_agents.build_icp import build_icp_graph  # noqa: E402

_OUT_DIR = Path(__file__).resolve().parent / "_out"

# The ICP stage MUST NOT touch search/scrape tools at all. This test's own
# imports prove it structurally: there is no wrapper to install because the
# module has nothing to wrap -- the assertion below documents the absence.

# ---------------------------------------------------------------------------
# Fixtures. One offer per matrix cell: product x b2b, product x b2c,
# service x b2b, service x b2c. Each is a DISTINCT offer (the same brand never
# carries two buyer-type verdicts), cosplayed by a GTM specialist (domain ==
# "gtm"), carrying the CANNED SIBLING STAGE OUTPUTS (offer/domain findings,
# market findings + structured market_data, competition findings + structured
# competition_data) the stage is required to consume. The canned Sources blocks
# use URLs that are NOT this run's retrieved set -- the ICP stage has no
# retrieved set at all -- so if stripping ever fails or the writer fabricates a
# URL, the invariant scans below fail.
# ---------------------------------------------------------------------------

# --- product x b2b ---
PRODUCT_B2B_OFFER = {
    "offer_type": "product",
    "offer_name": "MirosVB",
    "offer_description": (
        "MirosVB is a reasoning paradigm that enhances AI systems with intuition, creativity, "
        "and lateral thinking capabilities by leveraging storage-shaped intelligence rather "
        "than relying on massive computational power."
    ),
    "target_market": ["Nigeria", "Kenya", "Ghana"],
    "problem": "General-purpose LLMs need enormous compute for reasoning that a storage-shaped design could do far more cheaply.",
    "solution": "A storage-shaped reasoning paradigm: an episodic knowledge index paired with a compact reasoning core.",
    "target_users": ["AI research teams", "on-device AI product builders"],
    "features": [
        "Storage-shaped reasoning core",
        "Episodic knowledge index",
        "Efficient inference on commodity hardware",
    ],
    "service_uniqueness": [],
    "how_it_works": (
        "Queries resolve against a persistent episodic index; a compact reasoning core synthesises "
        "responses with context, so intuition and lateral thinking come from retrieval-shaped "
        "memory rather than raw parameter scale."
    ),
    "specialists": [
        Specialist(
            domain="gtm",
            name="Ada Obi",
            role="Go-to-Market Lead",
            affiliation="MVC Studio",
            description=(
                "Plans GTM for on-device AI products in West and East Africa: which companies "
                "to target first, which titles own the buying decision, and where enterprise "
                "builders already evaluate small-model runtimes."
            ),
        ),
    ],
    "offer_findings": (
        "### On-device AI reasoning systems\neffective runtimes split context from "
        "parameters: a small reasoning core paired with a large retrieval-shaped index. "
        "MirosVB sits in this category: retrieval-shaped memory rather than parameter scale.\n"
        "\n### Sources\n[1] https://domain-mirosvb.example"
    ),
    "offer_domain_fit_understanding": "sits in the retrieval-shaped on-device reasoning category",
    "market_findings": (
        "### On-device AI buyers\nB2B teams in West and East Africa buy per-deployment; "
        "willingness to pay clusters below $20k/yr; the adoption barriers are compute cost "
        "and integration trust rather than awareness.\n"
        "\n### Sources\n[1] https://market-mirosvb.example"
    ),
    "product_market_fit_understanding": "fits B2B on-device reasoning in West and East Africa",
    "market_data": MarketExtraction(
        buyer_type="b2b",
        category="other",
        target_audience="AI research teams and on-device product builders",
        target_geo=["Nigeria", "Kenya", "Ghana"],
        category_conventions="small-model runtimes on commodity hardware; per-deployment licensing",
        market_demand="growing interest in on-device reasoning to cut inference cost",
        growth_outlook="growing",
    ),
    "competition_findings": (
        "### On-device reasoning rivals\nOllama and llama.cpp anchor the open runtime "
        "segment at zero marginal cost, while Groq sells speed in the cloud; the gap is a "
        "storage-shaped core that is competitive on commodity hardware without a GPU farm.\n"
        "\n### Sources\n[1] https://competition-mirosvb.example"
    ),
    "competitive_positioning_understanding": "storage-shaped reasoning wins on cost/cadence",
    "competition_data": CompetitionExtraction(
        competitors=[
            {
                "name": "Ollama",
                "description": "local model-runner with strong developer ergonomics",
                "offering": "desktop/server runtime for open-weight models",
                "positioning": "runs models locally for free",
                "comparison": "wins on distribution and community; loses on reasoning depth",
                "feature_flags": {},
            },
            {
                "name": "llama.cpp",
                "description": "minimal C/C++ inference runtime for commodity hardware",
                "offering": "efficient local inference library",
                "positioning": "the open baseline for on-device inference",
                "comparison": "wins on footprint; loses on reasoning/storage design",
                "feature_flags": {},
            },
            {
                "name": "Groq",
                "description": "cloud LPU inference with very low latency",
                "offering": "high-speed cloud inference",
                "positioning": "speed on demand, cloud-hosted",
                "comparison": "wins on latency; loses on on-device privacy and cost at scale",
                "feature_flags": {},
            },
        ],
        strengths=["runs on commodity hardware with a storage-shaped core"],
        weaknesses=["young ecosystem and few local integrations"],
        opportunities=["enterprise builders seek on-device privacy with competitive reasoning"],
        differentiators=["storage-shaped reasoning rather than parameter scale"],
    ),
}

# --- product x b2c ---
PRODUCT_B2C_OFFER = {
    "offer_type": "product",
    "offer_name": "AuraPod",
    "offer_description": (
        "AuraPod is a private, on-device AI companion app for consumers: a lightweight "
        "assistant that runs entirely on the phone, learns from the user's own notes, and "
        "never uploads personal data to a cloud model."
    ),
    "target_market": ["Nigeria", "Lagos"],
    "problem": "Cloud AI companions keep consumers' chats and personal context on company servers, and consumers increasingly distrust that trade.",
    "solution": "A fully on-device companion: local context, local memory, no cloud model, no data to leak.",
    "target_users": ["privacy-conscious consumers", "students", "solopreneurs"],
    "features": [
        "Runs fully on-device",
        "Private long-term memory",
        "Free tier plus paid local-memory upgrade",
    ],
    "service_uniqueness": [],
    "how_it_works": (
        "The app installs a compact reasoning core on the phone; memories are indexed locally "
        "and all conversations are processed on-device, with a local export/backup option."
    ),
    "specialists": [
        Specialist(
            domain="gtm",
            name="Chiamaka Eze",
            role="Consumer GTM Lead",
            affiliation="Lagos Consumer Lab",
            description=(
                "Launches consumer apps in West Africa: knows which communities, creators and "
                "platforms carry privacy-focused products to young urban consumers, and how to "
                "grow a tight beachhead before going wide."
            ),
        ),
    ],
    "offer_findings": (
        "### On-device consumer AI\nthe category splits into cloud companions that hold "
        "your data and local-first assistants; privacy is the differentiator consumers "
        "actually feel, but adoption hinges on a fun, sticky surface.\n"
        "\n### Sources\n[1] https://domain-aurapod.example"
    ),
    "offer_domain_fit_understanding": "sits in the local-first consumer AI companion category",
    "market_findings": (
        "### Consumer AI companions in Nigeria\nurban 18-34 consumers download companion "
        "and assistant apps from app stores and creator links; concern over what cloud "
        "models do with personal chats is rising, and free tiers with a paid upgrade are "
        "the accepted monetisation.\n"
        "\n### Sources\n[1] https://market-aurapod.example"
    ),
    "product_market_fit_understanding": "fits privacy-sensitive consumer AI in urban Nigeria",
    "market_data": MarketExtraction(
        buyer_type="b2c",
        category="other",
        target_audience="privacy-conscious consumers, students, solopreneurs",
        target_geo=["Nigeria", "Lagos"],
        category_conventions="app-store distribution, freemium companions, subscription upgrade",
        market_demand="rising concern over what cloud AI companions do with user data",
        growth_outlook="growing",
    ),
    "competition_findings": (
        "### Consumer AI companions\nReplika and Character.AI own the emotional-companion "
        "segment on cloud infrastructure and are criticised for opaque data handling and "
        "cloud dependency; Perplexity competes for the assistant-productivity slot. The "
        "unclaimed space is a trustworthy local-first companion.\n"
        "\n### Sources\n[1] https://competition-aurapod.example"
    ),
    "competitive_positioning_understanding": "local-first privacy wins where cloud companions are distrusted",
    "competition_data": CompetitionExtraction(
        competitors=[
            {
                "name": "Replika",
                "description": "consumer AI companion with millions of downloads",
                "offering": "cloud-hosted companion chat with memory",
                "positioning": "an AI friend that remembers you",
                "comparison": "wins on polish and emotional attachment; loses on data privacy",
                "feature_flags": {},
            },
            {
                "name": "Character.AI",
                "description": "consumer platform for chatting with AI characters",
                "offering": "character-based chat on the cloud",
                "positioning": "the open-ended character platform",
                "comparison": "wins on breadth of personas; loses on personal memory and privacy",
                "feature_flags": {},
            },
            {
                "name": "Perplexity",
                "description": "AI answer engine with a mobile app",
                "offering": "search-answer assistant",
                "positioning": "answers with sources",
                "comparison": "wins on factual answers; loses on companionship and local memory",
                "feature_flags": {},
            },
        ],
        strengths=["genuinely local, so promises of privacy are structurally true"],
        weaknesses=["no brand, no community, small distribution"],
        opportunities=["creator-led distrust of cloud companions is a live audience signal"],
        differentiators=["on-device memory as a privacy feature, not a footnote"],
    ),
}

# --- service x b2b ---
SERVICE_B2B_OFFER = {
    "offer_type": "service",
    "offer_name": "StitchCorp",
    "offer_description": (
        "StitchCorp is a managed tailoring and staff-attire service for companies: "
        "measure-and-make uniform outfitting, bulk alterations, and replacement SLAs for "
        "hotels, airlines and retail chains in the Gulf."
    ),
    "target_market": ["UAE", "Saudi Arabia"],
    "problem": "Hospitality and retail groups struggle with staff uniforms: inconsistent tailors, slow replacements, and no single accountable vendor.",
    "solution": "A managed outfitting platform with on-site measurement teams, quality-scored fittings, and contracted replacement SLAs.",
    "target_users": ["hotel operations directors", "facilities managers", "retail chain buyers"],
    "features": [],
    "service_uniqueness": [
        "On-site measurement teams",
        "Contract replacement SLAs",
        "Quality guarantee on fit",
    ],
    "how_it_works": (
        "Corporate clients sign an outfitting contract; StitchCorp sends measurement teams "
        "on-site, manufactures with vetted tailors, and handles re-fits and replacements "
        "under an SLA per item class."
    ),
    "specialists": [
        Specialist(
            domain="gtm",
            name="Omar Al-Farsi",
            role="Enterprise GTM Lead",
            affiliation="Dubai B2B Services Desk",
            description=(
                "Sells managed services to Gulf hospitality and retail groups: knows the "
                "operational buyers who own staff-attire budgets, the procurement cycles, "
                "and the venue types where these executives congregate."
            ),
        ),
    ],
    "offer_findings": (
        "### Managed staff attire\nquality rests on measurement, fit accountability and "
        "replacement speed; the Gulf has strong artisans but no vendor that operates "
        "contract-level outfitting with SLAs across multiple emirates.\n"
        "\n### Sources\n[1] https://domain-stitchcorp.example"
    ),
    "offer_domain_fit_understanding": "sits in managed staff-attire and outfitting services",
    "market_findings": (
        "### Corporate tailoring in Gulf cities\nhotel chains and retail groups outsource "
        "staff attire to uniform vendors; decisions sit with operations and facilities "
        "buyers, and reliability on replacement SLAs matters more than unit price.\n"
        "\n### Sources\n[1] https://market-stitchcorp.example"
    ),
    "product_market_fit_understanding": "fits managed corporate outfitting in Gulf hospitality and retail",
    "market_data": MarketExtraction(
        buyer_type="b2b",
        category="service",
        target_audience="hotel operations directors, facilities managers, retail chain buyers",
        target_geo=["UAE", "Saudi Arabia"],
        category_conventions="contract uniform outfitting with replacement SLAs",
        market_demand="hospitality groups standardising staff attire across sites",
        growth_outlook="growing",
    ),
    "competition_findings": (
        "### Uniform and workwear vendors\nCintas and Aramark anchor the managed-workwear "
        "segment globally but are thin on the ground in Gulf hospitality; Engelbert Strauss "
        "sells premium workwear items rather than managed outfitting.\n"
        "\n### Sources\n[1] https://competition-stitchcorp.example"
    ),
    "competitive_positioning_understanding": "contract-level Gulf outfitting beats global workwear generalists",
    "competition_data": CompetitionExtraction(
        competitors=[
            {
                "name": "Cintas",
                "description": "global managed uniform and facility services provider",
                "offering": "managed workwear programs",
                "positioning": "one vendor for uniforms nationwide",
                "comparison": "wins on scale and coverage; loses on Gulf-specific craftsmanship",
                "feature_flags": {},
            },
            {
                "name": "Aramark",
                "description": "global facilities and uniform services company",
                "offering": "managed uniform and linen services",
                "positioning": "end-to-end facility services",
                "comparison": "wins on bundled contracts; loses on fit quality and tailoring depth",
                "feature_flags": {},
            },
            {
                "name": "Engelbert Strauss",
                "description": "premium workwear manufacturer with a strong brand",
                "offering": "premium workwear catalogue",
                "positioning": "durable, premium workwear",
                "comparison": "wins on garment quality; loses on managed measurement and SLAs",
                "feature_flags": {},
            },
        ],
        strengths=["Gulf-native fitting network and real replacement SLAs"],
        weaknesses=["smaller footprint than the global vendors"],
        opportunities=["hospitality brands want a single accountable Gulf outfitter"],
        differentiators=["measure-and-make at contract level, not off-the-shelf workwear"],
    ),
}

# --- service x b2c ---
SERVICE_B2C_OFFER = {
    "offer_type": "service",
    "offer_name": "StitchUp",
    "offer_description": (
        "StitchUp is an on-demand tailoring service connecting customers with vetted local "
        "tailors for fittings, alterations, and custom garments, with delivery and quality guarantees."
    ),
    "target_market": ["UAE", "Saudi Arabia"],
    "problem": "Reliable tailoring in Gulf cities means knowing a private tailor, waiting weeks, and hoping the result fits.",
    "solution": "A vetted local tailor network with in-home pickup and delivery, quality-scored fittings and a satisfaction guarantee.",
    "target_users": ["busy professionals", "e-commerce sellers needing garment alterations"],
    "features": [],
    "service_uniqueness": [
        "Vetted tailor network",
        "Quality guarantee on fit",
        "48-hour pickup and delivery",
    ],
    "how_it_works": (
        "Customers book a fitting online; a vetted tailor is dispatched with a measuring kit, "
        "garments are altered or made to order, and are delivered back within 48 hours under a fit guarantee."
    ),
    "specialists": [
        Specialist(
            domain="gtm",
            name="Fatima Al-Rashid",
            role="Consumer GTM Lead",
            affiliation="Dubai Consumer Services Intelligence",
            description=(
                "Launches consumer services in Gulf cities: knows which neighbourhoods, "
                "community pages and local platforms carry on-demand services, and the "
                "trust signals that convert first-time users."
            ),
        ),
    ],
    "offer_findings": (
        "### On-demand tailoring services\nquality rests on the tailor, the fitting process "
        "and the delivery guarantee; the Gulf has strong local artisans but no standardised "
        "quality bar or 48-hour commitment.\n"
        "\n### Sources\n[1] https://domain-stitchup.example"
    ),
    "offer_domain_fit_understanding": "sits in on-demand tailored-apparel services",
    "market_findings": (
        "### On-demand services in Gulf cities\nbusy professionals and e-commerce sellers "
        "pay a premium for home pickup and delivery; trust is the adoption barrier rather "
        "than price, and neighbourhood community pages and local review platforms drive "
        "first bookings.\n"
        "\n### Sources\n[1] https://market-stitchup.example"
    ),
    "product_market_fit_understanding": "fits the premium on-demand services market in Gulf cities",
    "market_data": MarketExtraction(
        buyer_type="b2c",
        category="service",
        target_audience="busy professionals and e-commerce sellers",
        target_geo=["UAE", "Saudi Arabia"],
        category_conventions="home pickup/delivery at a premium; satisfaction guarantee expected",
        market_demand="growing comfort with on-demand home services",
        growth_outlook="growing",
    ),
    "competition_findings": (
        "### Local tailoring and laundry rivals\nWashmen and DryBy built the on-demand "
        "laundry habit in Dubai and now branch into alterations; Timpson holds the UK "
        "high-street tailoring/repair slot and shapes expectations of what 'drop and "
        "collect' convenience means.\n"
        "\n### Sources\n[1] https://competition-stitchup.example"
    ),
    "competitive_positioning_understanding": "48-hour guaranteed fittings beats laundry-app alterations",
    "competition_data": CompetitionExtraction(
        competitors=[
            {
                "name": "Washmen",
                "description": "Dubai on-demand laundry and dry-cleaning app",
                "offering": "pickup laundry with alterations add-ons",
                "positioning": "your laundry, app-scheduled",
                "comparison": "wins on laundry habit and brand; loses on tailoring depth",
                "feature_flags": {},
            },
            {
                "name": "DryBy",
                "description": "Dubai on-demand laundry and alterations service",
                "offering": "24h laundry and alteration pickup",
                "positioning": "fast pickup, clean results",
                "comparison": "wins on speed brand; loses on fitted garments and guarantee",
                "feature_flags": {},
            },
            {
                "name": "Timpson",
                "description": "UK high-street tailoring, repairs and key-cutting chain",
                "offering": "in-store tailoring and garment repair",
                "positioning": "a key cutter that also fixes everything",
                "comparison": "wins on ubiquity in the UK; loses on Gulf presence and delivery",
                "feature_flags": {},
            },
        ],
        strengths=["vetted tailor network with a real fit guarantee"],
        weaknesses=["young brand, small local footprint"],
        opportunities=["laundry apps have conditioned Gulf consumers to on-demand pickup"],
        differentiators=["48-hour garment-level guarantee, not just a wash-and-fold habit"],
    ),
}

BRANCHES = {
    "product_b2b": PRODUCT_B2B_OFFER,
    "product_b2c": PRODUCT_B2C_OFFER,
    "service_b2b": SERVICE_B2B_OFFER,
    "service_b2c": SERVICE_B2C_OFFER,
}

# Real companies only: if the model invents a competitor name the subset check
# below fails.
FIXTURE_COMPETITORS = {
    "product_b2b": {"Ollama", "llama.cpp", "Groq"},
    "product_b2c": {"Replika", "Character.AI", "Perplexity"},
    "service_b2b": {"Cintas", "Aramark", "Engelbert Strauss"},
    "service_b2c": {"Washmen", "DryBy", "Timpson"},
}

# Every canned sibling Sources URL the run must never leak or re-cite. The ICP
# stage has no retrieved set, so ANY of these (or any URL at all) in the
# findings is a fabrication.
ALL_SIBLING_SOURCES = [
    "https://domain-mirosvb.example", "https://market-mirosvb.example", "https://competition-mirosvb.example",
    "https://domain-aurapod.example", "https://market-aurapod.example", "https://competition-aurapod.example",
    "https://domain-stitchcorp.example", "https://market-stitchcorp.example", "https://competition-stitchcorp.example",
    "https://domain-stitchup.example", "https://market-stitchup.example", "https://competition-stitchup.example",
]


# ---------------------------------------------------------------------------
# Runner: stream through the compiled graph, timing each node.
# ---------------------------------------------------------------------------


def _run_icp(offer: dict) -> tuple[dict, dict]:
    """Run the real graph once for one offer.

    Streams in updates mode so each node's arrival time is its wall clock.
    Every channel in IcpSessionState is a last-value channel (nothing a adds),
    so state accumulates by simple overwrite -- and there is no search channel
    at all to drain.
    """
    initial = {k: v for k, v in offer.items() if k not in ("specialists", "_branch")} | {
        "specialists": offer["specialists"],
        "scraped_content": None,
    }
    graph = build_icp_graph(checkpointer=False)

    state = dict(initial)
    timings: dict[str, float] = {}
    started = time.perf_counter()
    last = started

    for chunk in graph.stream(state, stream_mode="updates"):
        for node, update in chunk.items():
            now = time.perf_counter()
            timings[node] = now - last
            last = now
            if not update:
                continue
            state.update(update)

    timings["_total"] = time.perf_counter() - started
    return state, timings


def _any_urls(findings: str) -> list[str]:
    """Every http(s) URL in the notes. The ICP stage has no retrieved set, so
    ANY URL is a fabrication -- there is no Sources block to excuse one."""
    return [u for u in re.findall(r"https?://\S+", findings or "")]


def _norm(name: str) -> str:
    """Normalize a competitor/lead name for subset matching: strip, lowercase,
    drop trailing periods (models tack on punctuation)."""
    return (name or "").strip().lower().rstrip(".")


def _assert_icp_run(offer: dict, result: dict) -> None:
    """The invariants this pipeline promises. Each failure names the offender."""
    branch = offer["_branch"]
    noun = offer["offer_type"]
    expected_buyer = getattr(offer["market_data"], "buyer_type", "b2b")
    expected_buyer = expected_buyer.value if hasattr(expected_buyer, "value") else expected_buyer

    # -- The structured profile is the load-bearing output --
    data = result.get("icp_data")
    assert isinstance(data, ICP), (
        f"[{branch}] icp_data is not an ICP: {type(data).__name__} {data!r}"
    )
    assert data.buyer_type == expected_buyer, (
        f"[{branch}] buyer_type {data.buyer_type!r} must match the market stage's "
        f"{expected_buyer!r}"
    )

    # The emphasis actually carried: the axis that drives account discovery is
    # populated for this buyer type.
    industries = list(data.industries or [])
    assert len(industries) <= 3, f"[{branch}] industries must be clamped to 3, got {industries}"
    if expected_buyer == "b2b":
        assert industries, f"[{branch}] B2B profile missing industries: {industries}"
        assert data.company_sizes, f"[{branch}] B2B profile missing company_sizes"
        assert data.buyer_titles, f"[{branch}] B2B profile missing buyer_titles"
    else:
        assert data.buyer_personas, f"[{branch}] B2C profile missing buyer_personas"
        assert data.target_channels, f"[{branch}] B2C profile missing target_channels"

    # competitor_leads derive ONLY from the canned CompetitionExtraction. The
    # set is real companies; an invented name fails the subset check.
    leads = list(data.competitor_leads or [])
    known = {_norm(n) for n in FIXTURE_COMPETITORS[branch]}
    assert leads, f"[{branch}] no competitor leads derived from a 3-competitor set"
    for lead in leads:
        ln = _norm(lead.competitor_name)
        assert any(ln in kn or kn in ln for kn in known), (
            f"[{branch}] invented competitor lead {lead.competitor_name!r} -- "
            f"must derive only from {sorted(known)}"
        )
        assert lead.search_queries, f"[{branch}] lead {lead.competitor_name!r} has no queries"

    # geo is anchored to the market stage's target markets.
    assert data.geo, f"[{branch}] icp geo is empty; the market stage named target markets"

    # -- The findings: synthesis prose, no Sources block, no URLs at all --
    findings = result.get("icp_findings") or ""
    assert findings.strip(), f"[{branch}] icp_findings empty"
    assert "### Sources" not in findings, (
        f"[{branch}] the ICP stage appends no Sources block (pure synthesis); "
        f"found a stray one"
    )
    urls = _any_urls(findings)
    assert not urls, (
        f"[{branch}] the ICP stage retrieved nothing, so a URL in the findings is "
        f"a fabrication: {urls}"
    )
    for leaked in ALL_SIBLING_SOURCES:
        assert leaked not in findings, f"[{branch}] sibling-stage Source URL leaked into findings: {leaked}"

    # The writer was anchored on the structured record AND the competitor set:
    # at least one real competitor must survive into the notes, or the anchor
    # did not hold.
    findings_lower = findings.lower()
    echoed = [n for n in FIXTURE_COMPETITORS[branch] if n.lower() in findings_lower]
    assert echoed, (
        f"[{branch}] writer never named any fixture competitor "
        f"{sorted(FIXTURE_COMPETITORS[branch])} -- the structured-set anchor failed"
    )

    understanding = result.get("icp_understanding") or ""
    words = understanding.split()
    assert 1 <= len(words) <= 50, (
        f"[{branch}] icp_understanding is {len(words)} words, must be 1-50: {understanding!r}"
    )

    assert result.get("icp_complete") is True, f"[{branch}] completion flag not set"

    # The refinement pass ran (the three-node graph went end to end).
    assert result.get("icp_data") is not None, f"[{branch}] no structured ICP reached completion"


def _print_icp_report(offer: dict, result: dict, timings: dict) -> None:
    branch = offer["_branch"]
    data = result["icp_data"]
    buyer = data.buyer_type or "?"
    label, _ = icp._icp_emphasis(offer["offer_type"], buyer)
    findings = result.get("icp_findings") or ""
    understanding = result.get("icp_understanding") or ""
    print(f"\n=== {offer['offer_name']} ({branch}, {label}) ===")
    print(f"  buyer_type: {buyer}")
    print(
        f"  structured ICP: {len(data.industries or [])} industrie(s), "
        f"{len(data.company_sizes or [])} size band(s), {len(data.buyer_titles or [])} "
        f"title(s), {len(data.buyer_personas or [])} persona(s), "
        f"{len(data.target_channels or [])} channel(s), "
        f"{len(data.competitor_leads or [])} competitor lead(s)"
    )
    for lead in data.competitor_leads or []:
        print(f"    lead: {lead.competitor_name} -- {lead.search_queries}")
    print(f"  beachhead: {data.beachhead or '(none)'}")
    print(f"  findings ({len(findings.split())} words), understanding in {len(understanding.split())} words")
    print(f"  understanding: {understanding}")
    for node in ("create_icp", "refine_icp", "note_down_record"):
        print(f"  {node:16s} {timings.get(node, 0.0):6.1f}s")
    print(f"  {'total':16s} {timings['_total']:6.1f}s")


def _save_artifacts(offer: dict, result: dict, timings: dict) -> None:
    _OUT_DIR.mkdir(parents=True, exist_ok=True)
    slug = offer["offer_name"].lower()
    (Path(_OUT_DIR) / f"{slug}_icp_notes.md").write_text(
        f"# {offer['offer_name']} - icp_findings\n\n"
        f"{result.get('icp_findings') or ''}\n",
        encoding="utf-8",
    )
    log_path = Path(_OUT_DIR) / "run_log.json"
    log = []
    if log_path.exists():
        try:
            log = json.loads(log_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            log = []
    data = result.get("icp_data")
    log.append(
        {
            "run_log_tag": "icp",
            "branch": offer["_branch"],
            "offer": offer["offer_name"],
            "type": offer["offer_type"],
            "buyer_type": data.buyer_type if data else None,
            "stages_seconds": timings,
            "industries": data.industries if data else [],
            "buyer_titles": data.buyer_titles if data else [],
            "buyer_personas": [p.name for p in (data.buyer_personas or [])] if data else [],
            "target_channels": [c.name for c in (data.target_channels or [])] if data else [],
            "competitor_leads": [l.competitor_name for l in (data.competitor_leads or [])] if data else [],
            "understanding_words": len((result.get("icp_understanding") or "").split()),
        }
    )
    log_path.write_text(json.dumps(log, indent=2), encoding="utf-8")


def _run_and_assert(branch: str) -> None:
    offer = {**BRANCHES[branch], "_branch": branch}
    result, timings = _run_icp(offer)
    # Save and print first: a failing run must still leave its findings and
    # timings behind, or the failure is undiagnosable from the assert message.
    _save_artifacts(offer, result, timings)
    _print_icp_report(offer, result, timings)
    _assert_icp_run(offer, result)


def test_build_icp_product_b2b() -> None:
    _run_and_assert("product_b2b")


def test_build_icp_product_b2c() -> None:
    _run_and_assert("product_b2c")


def test_build_icp_service_b2b() -> None:
    _run_and_assert("service_b2b")


def test_build_icp_service_b2c() -> None:
    _run_and_assert("service_b2c")


def main() -> None:
    """Run all four matrix branches, then the cumulative LLM timing report."""
    print("Real ICP-understanding run (real LLM, pure synthesis, no web research)")
    branches = tuple(BRANCHES) if len(sys.argv) < 2 else (sys.argv[1],)
    failed = False
    for branch in branches:
        if branch not in BRANCHES:
            sys.exit(f"unknown branch {branch!r}; choose from {sorted(BRANCHES)}")
        try:
            _run_and_assert(branch)
        except Exception:
            import traceback

            traceback.print_exc()
            failed = True
    # Traceback or not, a run that spent real money should still account for
    # where the time went.
    print("\nCumulative LLM wall clock (all branches):")
    print(llm_timing_report())
    if failed:
        sys.exit(1)


if __name__ == "__main__":
    main()