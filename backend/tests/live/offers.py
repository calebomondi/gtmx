"""Ground truth for the live GTM chain: what each test offer actually is,
read from the companies' own sites (2026-10-12), so the agents' output is
judged against the source rather than against itself.

Both sites list several offers. `conflations` are claims that belong to a
SIBLING offer on the same site: an agent that makes them has mixed offers up.
"""

from dataclasses import dataclass, field

GEO = ["Kenya", "Nigeria", "South Africa"]


@dataclass(frozen=True)
class Offer:
    key: str
    name: str
    url: str
    offer_type: str
    # full = every stage; intake = offer intake only.
    depth: str
    truth: str
    # Each inner list is one fact; the description must mention one of its terms.
    must_mention: list[list[str]] = field(default_factory=list)
    conflations: list[str] = field(default_factory=list)
    own_domains: tuple[str, ...] = ()
    # What the market stage should find: "b2b", or "b2c" (which also accepts "both").
    buyer: str = "b2b"


HEATHERDB = Offer(
    key="heatherdb", name="HeatherDB", url="https://aphorion.co/", offer_type="product", depth="full",
    truth=(
        "HeatherDB (Aphorion Labs, Nairobi) is an open-source, self-organizing 'natively intelligent' database: "
        "data written to it becomes the model, with no weights, no retraining and no GPU. It powers anomaly "
        "detection, recommendations and semantic recall on commodity hardware (Raspberry Pi 5 to enterprise; demo "
        "on a $5 VPS), claims ~10x lower compute cost than GPU stacks, and can ingest existing models and vector "
        "indexes (Pinecone, Weaviate, Milvus, Qdrant). Fornix is the enterprise tier (model distillation 115x "
        "smaller, bit-identical answers)."
    ),
    must_mention=[["database"], ["gpu"], ["retrain", "training", "no model"]],
    conflations=["sound more human", "more human", "associations before it writes", "chain of thought"],
    own_domains=("aphorion.co",),
)

CLOUD_OF_ASSOCIATIONS = Offer(
    key="cloud-of-associations", name="Cloud of Associations", url="https://aphorion.co/", offer_type="product",
    depth="intake",
    truth=(
        "Cloud of Associations (CoA, Aphorion Labs) is a FREE developer tool that gives an AI a few short "
        "associations before it writes, so its answers sound more human without changing the facts. It plugs "
        "into Claude, ChatGPT, Codex, MCP clients or your own app; it is not a source of facts and does not "
        "reduce compute cost."
    ),
    must_mention=[["association"], ["human", "intuition", "creativ", "lateral"]],
    conflations=["database", "10x", "10×", "compute cost", "gpu bill"],
    own_domains=("aphorion.co",),
)

ENGINEERING_CONSULTANCY = Offer(
    key="engineering-innovation-consultancy", name="Engineering and Innovation Consultancy",
    url="https://shangalabs.com/", offer_type="service", depth="full",
    truth=(
        "Shanga Labs (Nairobi) offers end-to-end hardware and software R&D for founders, enterprises and research "
        "teams: concept and feasibility, hardware/firmware architecture, edge AI/ML integration, prototyping, "
        "field pilots, design for manufacturability, mass manufacturing and aftermarket support -- embedded with "
        "the client's team or run by Shanga. Outcome: faster time-to-market, lower iteration cost, one partner "
        "from idea to deployed fleet."
    ),
    must_mention=[["prototyp"], ["hardware", "electronics", "firmware"], ["pilot", "manufactur", "feasibility"]],
    # DePIN is in Shanga's company-wide capability list, so it isn't a sibling-only claim.
    conflations=["crypto atm", "lora", "over-the-air", "ota update", "satellite connectivity"],
    own_domains=("shangalabs.com",),
)

HARDWARE_INTEGRATION = Offer(
    key="hardware-system-integration-support", name="Hardware System Integration Support",
    url="https://shangalabs.com/", offer_type="service", depth="intake",
    truth=(
        "Shanga Labs' Hardware Systems Integration & Support is the software and connectivity layer for deployed "
        "hardware fleets: API integration, real-time monitoring dashboards, cellular/LoRa/satellite connectivity, "
        "DePIN, crypto ATM and on-chain payments, access control, IoT fleet management with OTA updates, and edge "
        "AI inference."
    ),
    must_mention=[["integrat", "api"], ["fleet", "iot", "device"], ["dashboard", "monitor", "connectivity", "ota"]],
    conflations=["feasibility stud", "design for manufacturability", "injection-mould", "injection mold"],
    own_domains=("shangalabs.com",),
)

POCKETAUTHOR = Offer(
    key="pocketauthor", name="PocketAuthor", url="https://pocketauthor.com/", offer_type="product", depth="full",
    buyer="b2c",
    truth=(
        "PocketAuthor is book writing and publishing software: it turns the notes, drafts, recordings and expertise "
        "an author already has into a structured, source-backed manuscript, then prepares ebook (EPUB) and print "
        "editions with metadata, ISBN and preflight checks, and a handoff to KDP or other distributors. Built for "
        "founders, consultants, professors and creators (plus ghostwriters, publishers and teams)."
    ),
    must_mention=[["book"], ["publish"], ["note", "draft", "manuscript", "expertise", "recording"]],
    conflations=[],
    own_domains=("pocketauthor.com",),
)

NOTION = Offer(
    key="notion", name="Notion", url="https://notion.so/", offer_type="product", depth="full", buyer="b2c",
    truth=(
        "Notion is an AI workspace for notes, docs, wikis and projects, with AI agents, enterprise search and "
        "automation. It has a free plan for individuals and 100M users in 50+ countries, and is also sold to teams "
        "and enterprises."
    ),
    must_mention=[["workspace", "notes", "docs", "wiki"], ["ai", "agent"]],
    conflations=[],
    own_domains=("notion.so", "notion.com"),
)

OFFERS = [HEATHERDB, ENGINEERING_CONSULTANCY, CLOUD_OF_ASSOCIATIONS, HARDWARE_INTEGRATION, POCKETAUTHOR, NOTION]
