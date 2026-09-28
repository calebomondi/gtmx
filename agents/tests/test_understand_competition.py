"""
Interactive driver for the understand competition subgraph.
Run: python agents/tests/test_understand_competition.py [offer_name] [offer_description] [offer_type]
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

from agents.states import (
    InterviewState,
    DomainSpecialist,
    OfferDataSnapshot,
    MarketExtraction,
    Pricing,
)
from agents.sub_graphs.understand_competition import build_competition_graph


COMPETITION_SPECIALIST = DomainSpecialist(
    domain="competition",
    name="Ken Osei",
    role_title="Competitive Landscape Analyst",
    background=("Ken tracks the fragmentation of the AI ecosystem, focusing on efficient inference engines and specialized reasoning tools. He maps how smaller, efficient models compete against dominant general-purpose platforms by targeting performance and cost gaps."),
    focus=("Mapping the competitive space for MirosVB — identifying efficient, reasoning-focused AI providers using retrieval-augmented generation (RAG) or hybrid approaches, and assessing where MirosVB's storage-shaped approach to creativity differentiates it from standard optimization strategies."),
    region="West Africa; East Africa; United States",
    language="English",
    operating_context="Led competitive-intelligence work for deep-tech firms across Lagos, Nairobi, and San Francisco, tracking inference-engine and platform rivals",
    distinct_lens="Judges competitors by the unit economics and performance curves buyers actually compare — cost per inference, efficiency, and where incumbent platforms force lock-in.",
)

PRODUCT_MARKET_DATA = MarketExtraction(
    buyer_type="b2b",
    category="saas",
    target_audience="Enterprises scaling agentic/reasoning AI workloads that are constraining compute spend — COO/CIO-tier operators and platform teams in finance, healthcare, and critical infrastructure seeking reasoning without GPU-cluster dependency.",
    target_geo=["Nigeria", "Kenya", "Ghana", "United States"],
    pricing=[Pricing(tier="Enterprise", monthly_sub="$8,000", features=["On-premise deployment", "Unlimited reasoning calls"])],
    market_fit="strong",
    category_conventions="B2B AI infrastructure sold through direct enterprise sales with usage-based or subscription pricing, security/compliance reviews, and pilot deployments.",
)

SERVICE_COMPETITION_SPECIALIST = DomainSpecialist(
    domain="competition",
    name="Layla Haddad",
    role_title="On-Demand Services Competitive Analyst",
    background=("Layla maps the on-demand home-services landscape across the Gulf and East Africa — tailoring, alterations, and custom-garment platforms, their pricing, and how they win vetted local supply. She studies how platforms acquire customers and retain quality tailors."),
    focus=("Mapping StitchUp's competitors in the UAE and Saudi Arabia — tailoring and alterations platforms, bespoke ateliers, and adjacent home-services apps — and where StitchUp's vetted local tailor network with delivery and quality guarantees differentiates."),
    region="Gulf Cooperation Council; East Africa",
    language="English (UAE/Saudi market idiom)",
    operating_context="Ran competitive analysis for home-services and on-demand platforms from Dubai to Nairobi, tracking pricing tiers, supply acquisition, and churn",
    distinct_lens="Judges the competitive set through the customer's booking decision — who captures discovery, trust, and repeat bookings for tailoring services in these cities.",
)

SERVICE_MARKET_DATA = MarketExtraction(
    buyer_type="b2c",
    category="service",
    target_audience="Households and style-conscious professionals in the UAE and Saudi Arabia booking alterations, fittings, and custom garments, who value convenience, trust, and quality guarantees.",
    target_geo=["UAE", "Saudi Arabia"],
    pricing=[Pricing(tier="Per-service", monthly_sub="AED 50–250 per order", features=["Fittings", "Alterations", "Custom garments"])],
    market_fit="strong",
    category_conventions="On-demand home services bought through mobile apps with in-app discovery, reviews, and delivery guarantees; trust and vetted supply are the decisive factors.",
)


def _specialist_for(offer_type: str) -> DomainSpecialist:
    return SERVICE_COMPETITION_SPECIALIST if offer_type == "service" else COMPETITION_SPECIALIST


def _market_data_for(offer_type: str) -> MarketExtraction:
    return SERVICE_MARKET_DATA if offer_type == "service" else PRODUCT_MARKET_DATA


def main():
    """Run the competition-specialist interview subgraph to see how it works"""

    print(f"🚀Starting Understand Competition Agent\n")

    # Optional command-line offer info.
    offer_name = sys.argv[1] if len(sys.argv) > 1 else "MirosVB"
    offer_description = sys.argv[2] if len(sys.argv) > 2 else "MirosVB is a reasoning paradigm that enhances AI systems with intuition, creativity, and lateral thinking capabilities by leveraging storage-shaped intelligence rather than relying on massive computational power."
    offer_type = sys.argv[3] if len(sys.argv) > 3 else "product"
    specialist = _specialist_for(offer_type)
    offer_name = offer_name if offer_type != "service" else "StitchUp"
    offer_description = offer_description if offer_type != "service" else "StitchUp is an on-demand tailoring service connecting customers with vetted local tailors for fittings, alterations, and custom garments, with delivery and quality guarantees."

    # Initial state
    initial_state: InterviewState = {
        "specialist": specialist,
        "max_num_turns": 5,
        "messages": [],
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
        "section_word_count": 500,
    }

    try:
        # Create session id & config
        session_id = str(uuid.uuid4())
        config = {"configurable": {"thread_id": session_id}}

        # Build agent then invoke
        print(f"🏃‍♂️Agent Running\n")
        agent = build_competition_graph()
        result = agent.invoke(initial_state, config)

        # Agent finishes
        print(f"\n🛑 Agent Completed\n")
        print(f"INPUT {offer_type.upper()}:")
        print(f"  name       : {offer_name}")
        print(f"  description: {offer_description}")
        print(f"Interviewer : {specialist.name} ({specialist.role_title})\n")

        messages = result.get("messages") or []
        print(f"TRANSCRIPT ({len(messages)} messages):")
        print("  " + "=" * 50)
        for m in messages:
            who = m.name if getattr(m, "name", None) else ("assistant" if m.type == "ai" else m.type)
            print(f"  [{who}] {m.content}\n")

        competition_data = result.get("competition_data")
        if competition_data:
            print(f"\nEXTRACTED COMPETITION DATA:")
            print(competition_data.model_dump_json(indent=2, exclude_none=True))

        findings = result.get("competition_findings") or ""
        if findings:
            print(f"\nRESEARCH NOTES:\n{findings}")

        positioning_understanding = result.get("competitive_positioning_understanding")
        if positioning_understanding:
            print(f"\nCOMPETITIVE POSITIONING UNDERSTANDING:\n{positioning_understanding}")

        expert_answers = sum(1 for m in messages if getattr(m, "name", None) == "expert")
        n_competitors = len(competition_data.competitors) if competition_data else 0
        complete = (
            expert_answers > 0
            and competition_data is not None
            and 3 <= n_competitors <= 5
            and bool(findings.strip())
            and bool((positioning_understanding or "").strip())
        )
        print("\n" + ("✅ Competition interview + extraction (3-5 competitors) + notes + positioning synthesis complete." if complete else "❌ Interview, extraction, notes, or synthesis incomplete."))

    except KeyboardInterrupt:
        print("\n⌨️ Cancelled.")
    except Exception as e:
        print(f"❌❌\n> Error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()