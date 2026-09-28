"""
Interactive driver for the understand market subgraph.
Run: python agents/tests/test_understand_market.py [offer_name] [offer_description] [offer_type]
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

from agents.states import InterviewState, DomainSpecialist, OfferDataSnapshot
from agents.sub_graphs.understand_market import build_market_graph


MARKET_SPECIALIST = DomainSpecialist(
    domain="market",
    name="Ivy Sinclair",
    role_title="Emerging Tech Market Strategist",
    background="Ivy maps who actually buys emerging AI infrastructure, with a decade of market-research work across enterprises carrying high compute and data-privacy costs. She reads demand signals, willingness to pay, and buyer hesitation as they show up in real procurement, not vendor press releases.",
    focus="Defining the market for MirosVB's reasoning paradigm — which buyer segments are bottlenecked by compute costs and seeking creative reasoning without GPU clusters, what they will pay, and whether the offer matches their buying habits.",
    region="West Africa; East Africa; global enterprise markets",
    language="English",
    operating_context="Advised go-to-market teams for deep-tech firms across Lagos, Nairobi, and London on pricing and ICP across cloud-economics and enterprise AI buyers",
    distinct_lens="Judges the market by where the money actually is — who is already spending on AI infrastructure, what budget lines would fund a paradigm like this, and how hard the switch is.",
)


SERVICE_MARKET_SPECIALIST = DomainSpecialist(
    domain="market",
    name="Nadia El-Khoury",
    role_title="Consumer Services Market Strategist",
    background="Nadia studies how on-demand consumer services are adopted across the Gulf and East Africa — what households and SMEs pay for convenience, and how trust, pricing, and delivery expectations form in fragmented service markets.",
    focus="Defining the market for StitchUp's on-demand tailoring model — who books alterations and custom garments in the UAE and Saudi Arabia, the category's demand and pricing norms, and whether the promise of vetted local tailors matches how these buyers already shop for services.",
    region="Gulf Cooperation Council; East Africa",
    language="English (UAE/Saudi market idiom)",
    operating_context="Ran consumer-market research for home-services and on-demand platforms from Dubai to Nairobi, tracking adoption, pricing benchmarks, and churn across fragmented local supply",
    distinct_lens="Teststhe market through the customer's booking decision — how people discover, trust, pay for, and repeat service bookings in these cities, and the price points that close a sale.",
)


def _specialist_for(offer_type: str) -> DomainSpecialist:
    return SERVICE_MARKET_SPECIALIST if offer_type == "service" else MARKET_SPECIALIST


def main():
    """Run the market-specialist interview subgraph to see how it works"""

    print(f"🚀Starting Understand Market Agent\n")

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
            target_geo=["UAE", "Saudi Arabia"] if offer_type == "service" else ["Nigeria", "Kenya", "Ghana"],
            service_uniqueness=[
                {"name": "Vetted tailor network", "description": "Pre-vetted, quality-scored tailors per city"}
            ] if offer_type == "service" else [],
        ),
        "section_word_count": 500,
    }

    try:
        # Create session id & config
        session_id = str(uuid.uuid4())
        config = {"configurable": {"thread_id": session_id}}

        # Build agent then invoke
        print(f"🏃‍♂️Agent Running\n")
        agent = build_market_graph()
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

        market_data = result.get("market_data")
        if market_data:
            print(f"\nEXTRACTED MARKET DATA:")
            print(market_data.model_dump_json(indent=2, exclude_none=True))

        findings = result.get("market_findings") or ""
        if findings:
            print(f"\nRESEARCH NOTES:\n{findings}")

        pmi_understanding = result.get("product_market_fit_understanding")
        if pmi_understanding:
            print(f"\nPRODUCT-MARKET FIT UNDERSTANDING:\n{pmi_understanding}")

        expert_answers = sum(1 for m in messages if getattr(m, "name", None) == "expert")
        complete = (
            expert_answers > 0
            and market_data is not None
            and findings.strip()
        )
        print("\n" + ("✅ Market interview + extraction + notes complete." if complete else "❌ Interview, extraction, or notes incomplete."))

    except KeyboardInterrupt:
        print("\n⌨️ Cancelled.")
    except Exception as e:
        print(f"❌❌\n> Error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()