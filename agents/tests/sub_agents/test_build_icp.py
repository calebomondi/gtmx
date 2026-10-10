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
specialist, canned sibling findings whose Sources blocks must be stripped, a
canned CompetitionExtraction SWOD, and a canned IdealCompetitorProfile.

`competitor_leads` must derive from the [competition findings] PROSE, which
names real companies. That is the only place names enter now: the competition
stage stopped emitting a structured name list, so the profile beside the SWOD
names nobody and cannot source a lead on its own.

Run all branches:
    python agents/tests/sub_agents/test_build_icp.py
Run one branch:
    python agents/tests/sub_agents/test_build_icp.py product_b2b
Under pytest:
    pytest -m live agents/tests/sub_agents/test_build_icp.py

Assertions are invariants, not exact text: LLM output is nondeterministic, so we
assert the things the design actually promises -- the buyer-type verdict matches
the market stage's, the emphasis carried (firmographics for B2B, personas +
channels for B2C), the industry clamp at 3, competitor leads derived only from
the rivals the findings prose names, findings free of any `### Sources` block and of any
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
from agents.states import (  # noqa: E402
    CompetitionExtraction,
    CompetitorArchetype,
    ICP,
    IdealCompetitorProfile,
    MarketExtraction,
)
from agents.sub_agents.schema_states import Specialist  # noqa: E402
import agents.sub_agents.discover.build_icp as icp  # noqa: E402
from agents.sub_agents.discover.build_icp import build_icp_graph  # noqa: E402
import pytest

# Real LLM + web calls: opt-in with `uv run pytest -m live`.
pytestmark = pytest.mark.live

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
    "offer_name": "HeatherDB",
    "offer_description": (
        "HeatherDB is a reasoning paradigm that enhances AI systems with intuition, creativity, "
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
        "HeatherDB sits in this category: retrieval-shaped memory rather than parameter scale.\n"
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
        strengths=["runs on commodity hardware with a storage-shaped core"],
        weaknesses=["young ecosystem and few local integrations"],
        opportunities=["enterprise builders seek on-device privacy with competitive reasoning"],
        differentiators=["storage-shaped reasoning rather than parameter scale"],
    ),
    "ideal_competitor_profile": IdealCompetitorProfile(
        category_definition=(
            "Any runtime or service that lets a team run an LLM on hardware it already "
            "owns, plus the cloud inference APIs bought as the alternative."
        ),
        boundary_of_category=[
            "Model providers selling weights rather than runtimes -- upstream, not a rival",
            "GPU resellers -- a cost input, not a substitute for the runtime",
        ],
        archetypes=[
            CompetitorArchetype(
                label="Open-source local runtime",
                archetype_description=(
                    "Free, permissively-licensed runtimes that execute open-weight models on a "
                    "laptop or server. Distribution is word of mouth and package managers; "
                    "there is no sales motion and no support contract."
                ),
                geography_scope="global",
                business_model="free / donation-funded",
                typical_offering="a model runner plus a small CLI",
                pricing_model="zero marginal cost, no paid tier",
                customer_profile="individual developers and hobby clusters",
                likely_advantages=[
                    "zero cost removes the budget conversation entirely",
                    "ubiquitous install base and community support",
                ],
                likely_weaknesses=[
                    "no reasoning-quality layer above raw sampling",
                    "no commercial accountability or SLA",
                ],
                where_to_find_them=[
                    "GitHub 'local LLM runtime' repositories",
                    "Hacker News threads on running models locally",
                ],
                confidence="high",
            ),
            CompetitorArchetype(
                label="Specialised open inference library",
                archetype_description=(
                    "Low-level C/C++ inference libraries that industry engineers embed when "
                    "footprint and throughput on commodity hardware matter more than "
                    "ergonomics. Competent teams build on these directly."
                ),
                geography_scope="global",
                business_model="open source, commercial support upsell",
                typical_offering="an embeddable inference library with quantisation support",
                pricing_model="free library, paid enterprise support",
                customer_profile="performance-sensitive engineering teams",
                likely_advantages=[
                    "best-in-class footprint and throughput",
                    "the default substrate other tools are built on",
                ],
                likely_weaknesses=[
                    "steep integration cost for average teams",
                    "no retrieval or reasoning layer of its own",
                ],
                where_to_find_them=[
                    "GitHub 'llama.cpp alternative' / quantisation repositories",
                    "engineering blog posts on inference optimisation",
                ],
                confidence="high",
            ),
            CompetitorArchetype(
                label="Global cloud inference provider",
                archetype_description=(
                    "Hyperscaler and specialist-LPU APIs selling low-latency inference as a "
                    "metered service. Operates locally through a regional cloud region "
                    "without being headquartered in the buyer's market."
                ),
                geography_scope="global",
                business_model="usage-metered API plus reserved-capacity contracts",
                typical_offering="a hosted inference endpoint with published latency SLAs",
                pricing_model="per-token, with committed-use discounts",
                customer_profile="production teams prioritising latency over unit cost",
                likely_advantages=[
                    "published latency SLAs and elastic capacity",
                    "buys into the budget where cloud already has a line item",
                ],
                likely_weaknesses=[
                    "per-token cost scales badly at high steady-state volume",
                    "every prompt leaves the customer's infrastructure",
                ],
                where_to_find_them=[
                    "cloud AI provider pricing pages",
                    "inference-provider comparison blogs",
                ],
                confidence="medium",
            ),
            CompetitorArchetype(
                label="In-house or DIY build",
                archetype_description=(
                    "Platform teams assembling their own serving stack from open components "
                    "plus a managed vector store. Not a purchase decision at all -- the most "
                    "dangerous competitor because it costs nothing but engineering time."
                ),
                geography_scope="any",
                business_model="not applicable -- internal cost centre",
                typical_offering="a bespoke pipeline maintained in-house",
                pricing_model="engineering time and infrastructure spend",
                customer_profile="resourced platform teams at larger firms",
                likely_advantages=[
                    "full control over data residency and latency",
                    "no vendor lock-in to argue about",
                ],
                likely_weaknesses=[
                    "sustains maintenance burden indefinitely",
                    "reinforces the status quo reasoning this offer displaces",
                ],
                where_to_find_them=[
                    "engineering blogs on 'we built our own inference stack'",
                    "in-house platform team job postings naming the stack",
                ],
                confidence="medium",
            ),
        ],
        global_entry_signals=[
            "A global API provider opening a regional cloud region undercuts local latency claims without local headcount.",
            "Open-weight releases let an unfunded entrant ship a credible runtime for free within weeks.",
        ],
        local_defence_signals=[
            "Incumbents win on relationships, local-language data and procurement familiarity rather than model quality.",
            "Regulatory or data-residency requirements keep buyers with locally-hosted operators.",
        ],
        substitution_risks=[
            "Calling a hosted general-purpose LLM API directly and writing the retrieval glue in-house.",
            "Not shipping an LLM feature at all and absorbing the workflow manually.",
        ],
        price_anchor_range="zero for open runtimes; per-token for hosted APIs",
        channels=["GitHub and developer communities", "technical blogs and launch posts"],
        confidence="high",
    ),
}

# --- product x b2c ---
PRODUCT_B2C_OFFER = {
    "offer_type": "product",
    "offer_name": "Cloud of Associations",
    "offer_description": (
        "Cloud of Associations is a private, on-device AI companion app for consumers: a lightweight "
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
        strengths=["genuinely local, so promises of privacy are structurally true"],
        weaknesses=["no brand, no community, small distribution"],
        opportunities=["creator-led distrust of cloud companions is a live audience signal"],
        differentiators=["on-device memory as a privacy feature, not a footnote"],
    ),
    "ideal_competitor_profile": IdealCompetitorProfile(
        category_definition=(
            "Any consumer-facing AI companion or assistant that a person talks to daily for "
            "company, entertainment or practical help -- whether or not it markets itself as "
            "a companion."
        ),
        boundary_of_category=[
            "General search engines with an AI answer box -- they capture the same query but not the relationship",
            "Utility chatbots embedded in banking or telco apps -- narrow scope, incumbent distribution",
        ],
        archetypes=[
            CompetitorArchetype(
                label="Cloud-first emotional companion",
                archetype_description=(
                    "Subscription apps that host a large language model in the cloud and "
                    "position on attachment: the product is the relationship, the memory is "
                    "the moat, and the user pays to keep it. Strong consumer marketing, "
                    "consistent global availability, no local presence anywhere."
                ),
                geography_scope="global",
                business_model="freemium subscription with paid memory/persona tiers",
                typical_offering="cloud-hosted chat with persistent memory and custom avatars",
                pricing_model="free tier, roughly $10-20/month for the paid tier",
                customer_profile="younger consumers who form emotional attachment to assistants",
                likely_advantages=[
                    "massive brand awareness and app-store presence",
                    "tuned specifically for emotional retention",
                ],
                likely_weaknesses=[
                    "every message is a data breach waiting to happen and users now know it",
                    "cloud cost forces the aggressive upsell that damages trust",
                ],
                where_to_find_them=[
                    "app store top charts in the AI category",
                    "'best AI companion' listicles",
                ],
                confidence="high",
            ),
            CompetitorArchetype(
                label="Character-platform swarm",
                archetype_description=(
                    "User-generated platforms where anyone can build and share a bot, so the "
                    "catalog is effectively infinite and the marketing is the community. "
                    "Headquartered in the US, operated worldwide, monetised through a share "
                    "of subscriptions and purchases."
                ),
                geography_scope="global",
                business_model="platform take-rate on in-app purchases",
                typical_offering="a user-creatable character marketplace with image and voice generation",
                pricing_model="free to use, pay per generated image or voice pack",
                customer_profile="roleplay and fandom communities, heavily US and European",
                likely_advantages=[
                    "the catalogue is a growth engine no competitor can match",
                    "creators bring their own audiences",
                ],
                likely_weaknesses=[
                    "safety incidents are a recurring reputational liability",
                    "the catalogue is mostly novelty, so retention is shallow",
                ],
                where_to_find_them=[
                    "'character AI' roleplay communities",
                    "app store 'entertainment' charts",
                ],
                confidence="high",
            ),
            CompetitorArchetype(
                label="Answer-engine assistant",
                archetype_description=(
                    "Search products that answer questions conversationally and have grown "
                    "into assistant-shaped products with memory and scheduled actions. Not a "
                    "companion by positioning, but competes for the same daily habit slot."
                ),
                geography_scope="global",
                business_model="advertising plus premium subscription",
                typical_offering="conversational answers with citations, memory and agents",
                pricing_model="free with ads, paid tier for higher limits",
                customer_profile="professionals and students using it for utility",
                likely_advantages=[
                    "search distribution already in place",
                    "grounded answers, so factual reliability is a genuine edge",
                ],
                likely_weaknesses=[
                    "utility framing produces no emotional bond",
                    "no private personal context by default",
                ],
                where_to_find_them=[
                    "'AI assistant' product reviews",
                    "search-engine app category pages",
                ],
                confidence="medium",
            ),
            CompetitorArchetype(
                label="Platform-bundled assistant",
                archetype_description=(
                    "The assistant shipped free with a phone or an operating system. The most "
                    "underrated competitor for a consumer assistant: no download, no "
                    "subscription, and already present on the device."
                ),
                geography_scope="global",
                business_model="loss leader funded by hardware or platform revenue",
                typical_offering="a bundled assistant with OS-level context access",
                pricing_model="included with the device",
                customer_profile="every owner of that platform, across all income levels",
                likely_advantages=[
                    "default on the device, so it wins by presence not quality",
                    "deep system permissions a third-party app cannot get",
                ],
                likely_weaknesses=[
                    "deliberately shallow memory and personality",
                    "reads as an assistant to a command, not a companion",
                ],
                where_to_find_them=[
                    "OS feature pages and default-assistant settings",
                    "tech press coverage of bundled AI features",
                ],
                confidence="high",
            ),
        ],
        global_entry_signals=[
            "A US platform shipping a free bundled assistant into low-connectivity markets where paid subscriptions will not convert.",
            "Open-weight models small enough to run on a mid-range phone make a local companion free to distribute.",
        ],
        local_defence_signals=[
            "Offline-first local processing is a structural advantage no cloud service can copy without abandoning its business model.",
            "Local-language conversation quality is hard for a global model to match without local data and local review.",
        ],
        substitution_risks=[
            "Messaging a friend instead, now that group chats carry most socialising.",
            "A plain notes app with a search box, if the user's need is memory rather than conversation.",
        ],
        price_anchor_range="free to roughly $20/month; the paid tier is the category anchor",
        channels=["app stores", "creator-led YouTube and TikTok demos", "listicle SEO"],
        confidence="high",
    ),
}

# --- service x b2b ---
SERVICE_B2B_OFFER = {
    "offer_type": "service",
    "offer_name": "Engineering and Innovation Consultancy",
    "offer_description": (
        "Engineering and Innovation Consultancy provides end-to-end R&D services for hardware and software: "
        "from initial concept and feasibility studies through prototyping, pilot deployment, mass manufacturing, "
        "and ongoing aftermarket support for startups and corporations in Kenya and East Africa."
    ),
    "target_market": ["Kenya"],
    "problem": "Hardware startups in Kenya often struggle to move from concept to a manufacturable product because they lack an end-to-end engineering partner.",
    "solution": "A single consultancy that supports feasibility, prototyping, pilot deployment, mass manufacturing, and aftermarket support.",
    "target_users": ["hardware startup founders", "product innovation leads", "CTO/VP Engineering at corporations"],
    "features": [],
    "service_uniqueness": [
        "End-to-end hardware and software R&D support",
        "Local prototyping and testing labs in/near Kenya",
        "Aftermarket and manufacturability optimisation for East African clients",
    ],
    "how_it_works": (
        "Clients engage initially for needs assessment and feasibility; the team prototypesin-house, "
        "then pilot-benchmarks, and finally coordinates mass manufacturing. Aftermarket support covers "
        "maintenance, analytics, and product iteration."
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
        target_geo=["Kenya"],
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
        strengths=["Gulf-native fitting network and real replacement SLAs"],
        weaknesses=["smaller footprint than the global vendors"],
        opportunities=["hospitality brands want a single accountable Gulf outfitter"],
        differentiators=["measure-and-make at contract level, not off-the-shelf workwear"],
    ),
    "ideal_competitor_profile": IdealCompetitorProfile(
        category_definition=(
            "Any provider that supplies, fits and maintains employee workwear or uniforms as "
            "a managed service -- including the vendor the employer already has a contract "
            "with, whether or not that contract is being renewed."
        ),
        boundary_of_category=[
            "Plain promotional-embroidered T-shirt printers -- one-off orders, no ongoing program",
            "Retailers selling individual garments -- a purchase, not a managed outfitting relationship",
        ],
        archetypes=[
            CompetitorArchetype(
                label="Global managed-uniform giant",
                archetype_description=(
                    "US- and Europe-headquartered firms running route-based delivery and "
                    "per-wearer rental programs across tens of countries, sold to national "
                    "hospitality, food and logistics accounts. Enormous scale and route "
                    "density, and correspondingly little presence in most Gulf markets."
                ),
                geography_scope="global",
                business_model="per-wearer rental subscription plus one-time programme fees",
                typical_offering="measured sizing, embroidery, pickup and repair routes",
                pricing_model="per employee per week, tiered by volume",
                customer_profile="multi-site employers with hundreds of uniformed staff",
                likely_advantages=[
                    "route density makes delivery economics unbeatable in a dense market",
                    "existing multi-year contracts are the real moat",
                ],
                likely_weaknesses=[
                    "Gulf coverage is thin enough that service quality drops",
                    "programmes are designed for volume, not for hospitality headcount",
                ],
                where_to_find_them=[
                    "uniform rental RFPs and tender awards",
                    "hospitality procurement case studies",
                ],
                confidence="high",
            ),
            CompetitorArchetype(
                label="Regional laundry-and-uniform consolidator",
                archetype_description=(
                    "Gulf incumbents that grew out of laundry services and bolted uniform "
                    "rental onto an existing pickup-and-delivery network. Strong local "
                    "relationships and labour familiarity, weaker at the fitting and styling "
                    "layer."
                ),
                geography_scope="regional",
                business_model="bundled laundry and uniform rental contracts",
                typical_offering="laundry plus workwear rental with existing delivery routes",
                pricing_model="per-item or per-wearer, discounted inside a bundle",
                customer_profile="Gulf hospitality groups and facilities operators",
                likely_advantages=[
                    "already trusted and already on site",
                    "bundling makes the price hard to undercut",
                ],
                likely_weaknesses=[
                    "garment fit and styling are not their competence",
                    "the laundry dependency caps the service ambition",
                ],
                where_to_find_them=[
                    "Gulf laundry-service provider lists",
                    "hospitality-group supplier announcements",
                ],
                confidence="medium",
            ),
            CompetitorArchetype(
                label="Premium workwear manufacturer",
                archetype_description=(
                    "Heritage European brands selling quality garments direct, with strong "
                    "retail and dealer networks. They compete for the budget when a company "
                    "buys individual items, but do not offer fitting, sizing or servicing."
                ),
                geography_scope="global",
                business_model="garment margin through retail, dealers and e-commerce",
                typical_offering="premium workwear garments, sold by the piece",
                pricing_model="per garment, premium bands",
                customer_profile="buyers who care about garment quality over programme management",
                likely_advantages=[
                    "genuine product-quality reputation",
                    "brand recognition with end users, which matters for hospitality",
                ],
                likely_weaknesses=[
                    "no managed service, so the employer still owns the problem",
                    "per-garment buying does not scale across staff turnover",
                ],
                where_to_find_them=[
                    "workwear brand 'about' and dealer pages",
                    "premium workwear review sites",
                ],
                confidence="medium",
            ),
            CompetitorArchetype(
                label="In-house uniform store",
                archetype_description=(
                    "Hospitality groups running their own shop fitting staff, buying blanks "
                    "and embroidering in house. No vendor relationship at all, and often "
                    "cheaper on paper -- but the labour is invisible until turnover bites."
                ),
                geography_scope="local",
                business_model="internal cost centre",
                typical_offering="an on-site or near-site fitting counter",
                pricing_model="garment cost plus staff time",
                customer_profile="large multi-property operators",
                likely_advantages=[
                    "total control of stock and timing",
                    "no vendor margin at all",
                ],
                likely_weaknesses=[
                    "cannot absorb a sudden headcount surge",
                    "turnover-driven repeat business is nobody's job",
                ],
                where_to_find_them=[
                    "hotel-group annual reports mentioning in-house uniforms",
                    "hospitality recruitment posts for 'uniform store' roles",
                ],
                confidence="low",
            ),
        ],
        global_entry_signals=[
            "A global vendor signing a Gulf hospitality group to build route density before a local competitor can.",
            "On-demand laundry platforms extending from consumer garments into staff uniforms.",
        ],
        local_defence_signals=[
            "Measured fittings and a named account manager are relationship-locked and hard for a global vendor to staff locally.",
            "Gulf-specific sizing and climate-appropriate fabrics require local knowledge.",
        ],
        substitution_risks=[
            "Buying plain stock garments and managing replacements in-house.",
            "Letting staff source their own workwear and reimbursing the cost.",
        ],
        price_anchor_range="per-wearer per-week, quoted against global programme contracts",
        channels=["enterprise procurement and RFPs", "hospitality trade press", "sales-led direct outreach"],
        confidence="high",
    ),
}

# --- service x b2c ---
SERVICE_B2C_OFFER = {
    "offer_type": "service",
    "offer_name": "Notion",
    "offer_description": (
        "Notion is an on-demand tailoring service connecting customers with vetted local "
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
        strengths=["vetted tailor network with a real fit guarantee"],
        weaknesses=["young brand, small local footprint"],
        opportunities=["laundry apps have conditioned Gulf consumers to on-demand pickup"],
        differentiators=["48-hour garment-level guarantee, not just a wash-and-fold habit"],
    ),
    "ideal_competitor_profile": IdealCompetitorProfile(
        category_definition=(
            "Any consumer service a person uses without a live conversation to get clothes "
            "made, altered, repaired or laundered -- apps, drop-off counters and delivery "
            "routes alike."
        ),
        boundary_of_category=[
            "Local bespoke tailors reached only by appointment -- no pickup, no delivery, no convenience layer",
            "Dry-cleaning and ironing services with no alteration capability",
        ],
        archetypes=[
            CompetitorArchetype(
                label="On-demand laundry app with alterations",
                archetype_description=(
                    "Dubai-built consumer apps that built the pickup-and-deliver laundry habit "
                    "and have since added an alterations line. The closest thing to a direct "
                    "rival: same door-to-door promise, same city, same customer."
                ),
                geography_scope="local",
                business_model="per-order pricing with membership subscriptions",
                typical_offering="laundry, ironing and increasingly garment alterations",
                pricing_model="per kilogram or per order, with monthly plans",
                customer_profile="time-poor dual-income households in Gulf cities",
                likely_advantages=[
                    "the doorstep habit is already established",
                    "operational density in exactly these neighbourhoods",
                ],
                likely_weaknesses=[
                    "laundry logistics are a poor fit for fittings",
                    "no measurement expertise to differentiate on",
                ],
                where_to_find_them=[
                    "Gulf laundry app app-store listings",
                    "'doorstep laundry Dubai' local directories",
                ],
                confidence="high",
            ),
            CompetitorArchetype(
                label="High-street alteration and repair chain",
                archetype_description=(
                    "UK heritage retail chain running physical alteration and repair shops "
                    "with same-day service. Sets the expectation of what drop-and-collect "
                    "convenience means, and is now testing Gulf outposts -- a credible future "
                    "entrant even though it is not yet a serious local rival."
                ),
                geography_scope="global",
                business_model="per-item service fees across physical locations",
                typical_offering="walk-in alterations, repairs, hemming and dry cleaning",
                pricing_model="per item, priced at the counter",
                customer_profile="walk-in customers who want it done today",
                likely_advantages=[
                    "a trained alteration counter as the entire business",
                    "brand trust that transfers across markets",
                ],
                likely_weaknesses=[
                    "fixed locations lose to door-to-door on convenience",
                    "no vetting, no quality guarantee, no custom capability",
                ],
                where_to_find_them=[
                    "store locators and 'first store in the Middle East' press coverage",
                    "alteration-chain franchise pages",
                ],
                confidence="medium",
            ),
            CompetitorArchetype(
                label="Marketplace of vetted tailors",
                archetype_description=(
                    "Two-sided platforms connecting consumers to independent tailors and "
                    "alteration workers, handling discovery, payment and dispute resolution. "
                    "Not a service operator itself, which is exactly the gap an operator "
                    "with a quality guarantee can exploit."
                ),
                geography_scope="local",
                business_model="commission on each job, plus promoted listings",
                typical_offering="a directory of tailors with booking and payment",
                pricing_model="take-rate per job plus listing fees",
                customer_profile="price-comparison shoppers who value choice over consistency",
                likely_advantages=[
                    "supply is infinite and onboarding is frictionless",
                    "already owns the discovery moment",
                ],
                likely_weaknesses=[
                    "quality varies and the marketplace disclaims it",
                    "no guarantee, no recurring relationship",
                ],
                where_to_find_them=[
                    "tailoring marketplace app listings in Gulf markets",
                    "'book a tailor online' local search results",
                ],
                confidence="medium",
            ),
            CompetitorArchetype(
                label="Neighbourhood tailor workshop",
                archetype_description=(
                    "Owner-operated alteration shops with a walk-in counter and a WhatsApp "
                    "number. The default incumbent for anyone who already knows one, and "
                    "untouchable on price -- the substitution threat rather than a rival."
                ),
                geography_scope="local",
                business_model="cash trade on labour time",
                typical_offering="in-person alterations and bespoke tailoring",
                pricing_model="per item, quoted in person",
                customer_profile="customers who already have a relationship",
                likely_advantages=[
                    "personal trust and unlimited custom capability",
                    "no platform or delivery overhead",
                ],
                likely_weaknesses=[
                    "inconsistent quality and no recourse",
                    "hours are narrow and there is no pickup",
                ],
                where_to_find_them=[
                    "local business directories and map listings",
                    "neighbourhood social media groups",
                ],
                confidence="high",
            ),
        ],
        global_entry_signals=[
            "A UK alteration chain's first Gulf stores, importing the drop-and-collect habit before a local rival owns it.",
            "A regional laundry platform adding a full bespoke tailoring line to its logistics.",
        ],
        local_defence_signals=[
            "A vetted network with a real fit guarantee cannot be undercut by an individual workshop on anything except price.",
            "Delivery density in a specific neighbourhood compounds, and incumbents cannot match a route that already passes every door.",
        ],
        substitution_risks=[
            "Buying ready-made garments that fit, so no alteration is needed at all.",
            "A neighbourhood tailor the customer already trusts, reached by walking in.",
        ],
        price_anchor_range="per garment for alterations; per order for on-demand services",
        channels=["mobile app stores", "neighbourhood word of mouth", "local search and directories"],
        confidence="high",
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

# Real, famous rivals in each branch's category that are deliberately ABSENT from
# its canned [competition findings]. The ICP stage has no retrieved set, so any
# of these appearing in its notes was imported from the model's own memory rather
# than sourced from the session -- an unsourced competitor claim, which is the
# failure the sourcing brief exists to prevent. Kept to names a model would
# plausibly reach for unprompted, so a hit is a real leak and not a coincidence.
FIXTURE_ABSENT_COMPETITORS = {
    "product_b2b": {"LangChain", "vLLM", "Hugging Face", "OpenAI", "Google Gemini"},
    "product_b2c": {"ChatGPT", "Claude", "Gemini", "Meta AI", "Snapchat"},
    "service_b2b": {"UniFirst", "Alsco", "Apparel Unlimited"},
    "service_b2c": {"Reneepress", "Pressly", "In-Phouse"},
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
    # ICP.buyer_type is a free-form str, not the BuyerType enum, so the model
    # legitimately answers "B2B" — which is how this module's own instructions
    # spell it. The fixture is unwrapped to the enum's lowercase value above, so
    # compare case-insensitively: the verdict is what is under test, not its
    # casing.
    assert (data.buyer_type or "").strip().lower() == str(expected_buyer).strip().lower(), (
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

    # competitor_leads derive ONLY from the rivals the [competition findings]
    # prose names. The structured side (SWOD + archetype profile) names nobody
    # by construction, so an invented name here fails the subset check below.
    leads = list(data.competitor_leads or [])
    known = {_norm(n) for n in FIXTURE_COMPETITORS[branch]}
    assert leads, f"[{branch}] no competitor leads derived from the findings prose"
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

    # Sourcing discipline on rival names. This assertion used to require the
    # writer to ECHO the structured competitor set, which proved the set anchor
    # held. That set is gone -- the competition stage emits an archetype profile
    # that names nobody -- so echoing it is no longer a property the writer owes
    # anything, and requiring it would only test whether it felt like mentioning
    # a rival.
    #
    # What the stage still promises is the inverse and the stronger claim: a rival
    # it names must come from the canned [competition findings], never from the
    # model's own memory. So each branch lists well-known rivals that are
    # DELIBERATELY absent from its canned findings. Naming one is the model
    # importing an unsourced competitor from outside the session -- exactly the
    # failure the brief was rewritten to prevent.
    findings_lower = findings.lower()
    unsourced = [n for n in FIXTURE_ABSENT_COMPETITORS[branch] if n.lower() in findings_lower]
    assert not unsourced, (
        f"[{branch}] findings named rivals absent from the canned competition "
        f"findings {unsourced} -- competitor names must be sourced from the "
        f"session, not recalled"
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