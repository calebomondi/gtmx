"""
Interactive driver for the understand product subgraph.
Run: python agents/tests/test_understand_product.py [product_name] [product_description]
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
from agents.sub_graphs.understand_product import build_product_graph


PRODUCT_SPECIALIST = DomainSpecialist(
    domain="product",
    name="Dr. Aris Thorne",
    role_title="Principal AI Architect & Cognitive Systems Analyst",
    background="Dr. Thorne specializes in alternative AI architectures that move beyond brute-force scaling, focusing on neuro-symbolic approaches and efficient reasoning models. His career has been dedicated to analyzing how storage-shaped intelligence can replicate human-like intuition without the exponential energy costs of traditional large language models.",
    focus="Evaluating MirosVB's core reasoning paradigm to ensure its 'storage-shaped' approach genuinely delivers lateral thinking and creativity while meeting technical performance standards for next-generation AI systems.",
    region="West Africa; global AI research hubs",
    language="English",
    operating_context="Advised deep-tech teams across Lagos and Nairobi on AI infrastructure choices",
    distinct_lens="Benchmarks these systems against what the most efficient reasoning architectures achieve in practice — does 'storage-shaped' beat brute-force scaling on cost and latency?",
)

SERVICE_SPECIALIST = DomainSpecialist(
    domain="service",
    name="Amara Okafor",
    role_title="Principal On-Demand Services & Operations Analyst",
    background="Amara specializes in on-demand and asset-light service models across emerging markets, from tailoring and repair networks to dispatch and fulfillment operations. Her career has been dedicated to understanding how service businesses deliver consistency and trust at scale across fragmented geographies.",
    focus="Evaluating StitchUp's on-demand tailoring model to ensure its dispatch, quality-control, and fulfilment promise holds up against how modern service marketplaces are expected to operate across the region.",
    region="Gulf Cooperation Council; East & West Africa",
    language="English (British-isle service idiom)",
    operating_context="Scaled service marketplaces from Dubai to Lagos, shaping delivery SLAs and trust mechanisms",
    distinct_lens="Judges the service against what customers in these markets expect from on-demand providers — reliability of fulfilment, quality assurance, and clear service-level promises.",
)


def _specialist_for(offer_type: str) -> DomainSpecialist:
    return SERVICE_SPECIALIST if offer_type == "service" else PRODUCT_SPECIALIST


def main():
    """Run the product-specialist interview subgraph to see how it works"""

    print(f"🚀Starting Understand Product Agent\n")

    # Optional command-line product info.
    offer_name = sys.argv[1] if len(sys.argv) > 1 else "MirosVB"
    offer_description = sys.argv[2] if len(sys.argv) > 2 else "MirosVB is a reasoning paradigm that enhances AI systems with intuition, creativity, and lateral thinking capabilities by leveraging storage-shaped intelligence rather than relying on massive computational power."
    offer_type = sys.argv[3] if len(sys.argv) > 3 else "product"
    specialist = _specialist_for(offer_type)
    offer_name = offer_name if offer_type != "service" else "StitchUp"
    offer_description = offer_description if offer_type != "service" else "StitchUp is an on-demand tailoring service connecting customers with vetted local tailors for fittings, alterations, and custom garments, with delivery and quality guarantees."

    # Initial state
    initial_state: InterviewState = {
        "specialist": specialist,
        "max_num_turns": 4,
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
        agent = build_product_graph()
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

        interview = result.get("interview")
        if interview:
            print(f"\nINTERVIEW STRING:\n{interview}")

        findings = result.get("product_findings") or ""
        if findings:
            print(f"\nRESEARCH NOTES:\n{findings}")
        understanding = result.get("product_domain_understanding") or ""
        if understanding:
            print(f"\nDOMAIN UNDERSTANDING: {understanding}")

        expert_answers = sum(1 for m in messages if getattr(m, "name", None) == "expert")
        complete = expert_answers > 0 and findings.strip()
        print("\n" + ("✅ Interview + notes complete." if complete else "❌ Interview or notes incomplete."))

    except KeyboardInterrupt:
        print("\n⌨️ Cancelled.")
    except Exception as e:
        print(f"❌❌\n> Error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()