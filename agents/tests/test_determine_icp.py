"""
Interactive driver for the determine-ICP subgraph (GTM phase).
Run: python agents/tests/test_determine_icp.py [offer_type]

Runs the full buyer-type-aware ICP determination (draft + refine) and prints the
finalized ICP plus the icp_complete flag.
"""
import sys
import uuid
from pathlib import Path

# Walk up from cwd to find project root (has pyproject.toml)
root = Path.cwd()
while root != root.parent:
    if (root / "pyproject.toml").exists():
        break
    root = root.parent

sys.path.insert(0, str(root))

from agents.states import DetermineIcpState, DomainSpecialist, OfferDataSnapshot, MarketExtraction, CompetitionExtraction, Competitor
from agents.sub_graphs.determine_icp import build_icp_graph


GTM_SPECIALIST = DomainSpecialist(
    domain="gtm",
    name="Selene Okafor",
    role_title="Developer Experience & API Growth Lead",
    background=("Selene specializes in go-to-market strategies for developer-centric infrastructure tools. She understands how to position technical innovations not just as faster or cheaper, but as fundamentally changing the workflow of building intelligent applications."),
    focus=("Developing a launch strategy that highlights MirosVB's ability to enable 'creative' AI features at a fraction of the cost, crafting messaging that appeals to CTOs and lead developers who are skeptical of the sustainability of current scaling trends."),
    region="West Africa; East Africa; United States",
    language="English",
    operating_context="Launched deep-tech and developer-infrastructure products across Lagos, Nairobi, and San Francisco, focusing on enterprise DevEx pipelines and AI infrastructure buyers",
    distinct_lens="Judges every target by who actually signs — which ICP accounts have the budget line, the authority, and a live buying signal to act on now.",
)

PRODUCT_MARKET_DATA = MarketExtraction(
    buyer_type="b2b",
    category="saas",
    target_audience="Enterprises scaling agentic/reasoning AI workloads that are constraining compute spend — COO/CIO-tier operators and platform teams in finance, healthcare, and critical infrastructure seeking reasoning without GPU-cluster dependency.",
    target_geo=["Nigeria", "Kenya", "Ghana", "United States"],
    pricing=[{"tier": "Enterprise", "monthly_sub": "$8,000", "features": ["On-premise deployment", "Unlimited reasoning calls"]}],
    market_fit="strong",
    category_conventions="B2B AI infrastructure sold through direct enterprise sales with usage-based or subscription pricing, security/compliance reviews, and pilot deployments.",
)

PRODUCT_COMPETITION_DATA = CompetitionExtraction(
    competitors=[
        Competitor(name="MiroMind", description="Open-weight reasoning models with verifiable audit trails.", website="https://www.miromind.ai"),
        Competitor(name="OptimaAI", description="Enterprise agentic platform with workflow governance.", website="https://www.optimaai.example"),
        Competitor(name="Infinitus", description="Healthcare AI agent product studio.", website="https://infinitus.ai"),
    ],
    strengths=["On-premise, fixed-cost model"],
    weaknesses=["Undocumented hardware efficiency"],
    opportunities=["Infrastructure sovereignty in Africa"],
    differentiators=["Storage-shaped lateral reasoning"],
)

SERVICE_GTM_SPECIALIST = DomainSpecialist(
    domain="gtm",
    name="Amara Diallo",
    role_title="Consumer Services Growth Lead",
    background=("Amara launches on-demand consumer services across the Gulf and East Africa — tailoring, home services, and care platforms. She knows how to turn a reliable local supply network into growth, and which customer segments book and rebook fast."),
    focus=("Crafting StitchUp's go-to-market in the UAE and Saudi Arabia — which household and SME segments to target first, the trust and convenience angles that close bookings, and how to win against incumbent tailoring apps and ateliers."),
    region="Gulf Cooperation Council; East Africa",
    language="English (UAE/Saudi market idiom)",
    operating_context="Grew on-demand home-care and tailoring marketplace platforms from Dubai to Nairobi, building repeat-booking cohorts and supply-side retention",
    distinct_lens="Judges every target by the booking decision — who is already searching for tailoring at home, trusts an app enough to book, and will rebook.",
)

SERVICE_MARKET_DATA = MarketExtraction(
    buyer_type="b2c",
    category="service",
    target_audience="Households and style-conscious professionals in the UAE and Saudi Arabia booking alterations, fittings, and custom garments, who value convenience, trust, and quality guarantees.",
    target_geo=["UAE", "Saudi Arabia"],
    pricing=[{"tier": "Per-service", "monthly_sub": "AED 50–250 per order", "features": ["Fittings", "Alterations", "Custom garments"]}],
    market_fit="strong",
    category_conventions="On-demand home services bought through mobile apps with in-app discovery, reviews, and delivery guarantees; trust and vetted supply are the decisive factors.",
)

SERVICE_COMPETITION_DATA = CompetitionExtraction(
    competitors=[
        Competitor(name="Urban Company", description="On-demand home services marketplace covering tailoring and more.", website="https://www.urbancompany.com"),
        Competitor(name="Tailor4Sure", description="Custom tailoring ordering platform for the Gulf.", website="https://tailor4sure.example"),
        Competitor(name="Atlars", description="UAE tailoring services booking app.", website="https://atlars.example"),
    ],
    strengths=["Vetted local tailor network"],
    weaknesses=["Nascent brand trust"],
    opportunities=["Fragmented atelier market"],
    differentiators=["Delivery + quality guarantees on every order"],
)


def _specialist_for(offer_type: str) -> DomainSpecialist:
    return SERVICE_GTM_SPECIALIST if offer_type == "service" else GTM_SPECIALIST


def _market_data_for(offer_type: str) -> MarketExtraction:
    return SERVICE_MARKET_DATA if offer_type == "service" else PRODUCT_MARKET_DATA


def _competition_data_for(offer_type: str) -> CompetitionExtraction:
    return SERVICE_COMPETITION_DATA if offer_type == "service" else PRODUCT_COMPETITION_DATA


def main():
    """Run the determine-ICP subgraph: draft -> refine -> finalized ICP."""

    print("🚀Starting Determine-ICP Agent\n")

    offer_type = sys.argv[1] if len(sys.argv) > 1 else "product"
    specialist = _specialist_for(offer_type)
    offer_name = "StitchUp" if offer_type == "service" else "MirosVB"
    offer_description = (
        "StitchUp is an on-demand tailoring service connecting customers with vetted local tailors for fittings, alterations, and custom garments, with delivery and quality guarantees."
        if offer_type == "service"
        else "MirosVB is a reasoning paradigm that enhances AI systems with intuition, creativity, and lateral thinking capabilities by leveraging storage-shaped intelligence rather than relying on massive computational power."
    )

    initial_state: DetermineIcpState = {
        "specialist": specialist,
        "offer_type": offer_type,
        "offer_snapshot": OfferDataSnapshot(
            offer_name=offer_name,
            offer_description=offer_description,
            target_geo=["UAE", "Saudi Arabia"] if offer_type == "service" else ["Nigeria", "Kenya", "Ghana", "United States"],
            features=[
                {"name": "Real-time booking", "description": "Book a vetted local tailor for fittings and alterations"}
            ] if offer_type == "service" else [
                {"name": "Lateral reasoning", "description": "Enhances AI with intuition and creative reasoning"}
            ],
            service_uniqueness=[
                {"name": "Vetted tailor network", "description": "Pre-vetted, quality-scored tailors per city with delivery and quality guarantees"}
            ] if offer_type == "service" else [],
        ),
        "market_data": _market_data_for(offer_type),
        "competition_data": _competition_data_for(offer_type),
    }

    try:
        session_id = str(uuid.uuid4())
        config = {"configurable": {"thread_id": session_id}}

        print("🏃Agent Running\n")
        agent = build_icp_graph()
        result = agent.invoke(initial_state, config)

        print("\n🛑 Agent Completed\n")
        print(f"INPUT {offer_type.upper()}:")
        print(f"  name       : {offer_name}")
        print(f"  description: {offer_description}")
        print(f"Strategist  : {specialist.name} ({specialist.role_title})\n")

        icp = result.get("icp")
        if icp:
            print(f"\nFINALIZED ICP:")
            print(icp.model_dump_json(indent=2, exclude_none=True))

        complete = bool(icp and result.get("icp_complete"))
        print("\n" + ("✅ ICP finalized." if complete else "❌ ICP incomplete."))
        print(f"ICP complete: {result.get('icp_complete')}")

    except KeyboardInterrupt:
        print("\n⌨️ Cancelled.")
    except Exception as e:
        print(f"❌❌\n> Error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()