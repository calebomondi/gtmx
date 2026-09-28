"""
Interactive driver for the create specialists subgraph.
Run: python agents/tests/test_create_specialists.py [offer_type] [offer_name] [offer_description] [target_geo_csv]
"""
import sys
from pathlib import Path

# Walk up from cwd to find project root (has pyproject.toml)
root = Path.cwd()
while root != root.parent:
    if (root / "pyproject.toml").exists():
        break
    root = root.parent

sys.path.insert(0, str(root))

from agents.states import OfferSessionState, OfferDataSnapshot
from agents.sub_graphs.create_specialists import build_specialist_graph


def main():
    """Run the specialist team builder to see how it works"""

    print(f"🚀Starting Create Specialists Agent\n")

    # Optional command-line offer info.
    offer_type = sys.argv[1] if len(sys.argv) > 1 else "product"
    offer_name = sys.argv[2] if len(sys.argv) > 2 else None
    offer_description = sys.argv[3] if len(sys.argv) > 3 else None
    target_geo = sys.argv[4].split(",") if len(sys.argv) > 4 else []

    # Initial state
    initial_state: OfferSessionState = {
        "offer": offer_type,
        "offer_snapshot": OfferDataSnapshot(
            offer_name=offer_name,
            offer_description=offer_description,
            target_geo=target_geo,
        ),
    }

    try:
        # Build agent then invoke
        print(f"🏃‍♂️Agent Running\n")
        agent = build_specialist_graph()
        result = agent.invoke(initial_state)

        # Agent finishes
        print(f"\n🛑 Agent Completed\n")
        print(f"INPUT OFFER ({offer_type}):")
        print(f"  name       : {offer_name}")
        print(f"  description: {offer_description}")
        print(f"  target_geo : {target_geo}")

        team = result.get("specialist_team")
        if team is None:
            print("❌ No specialist team was produced.")
            return

        print(f"\nSPECIALIST TEAM:")
        for specialist in (team.product_or_service_specialist, team.market_specialist, team.competition_specialist, team.gtm_specialist):
            print("  " + "-" * 40)
            print(f"  domain    : {specialist.domain}")
            print(f"  name      : {specialist.name}")
            print(f"  role      : {specialist.role_title}")
            print(f"  background: {specialist.background}")
            print(f"  focus     : {specialist.focus}")
            print(f"  region    : {specialist.region}")
            print(f"  language  : {specialist.language}")
            print(f"  operating : {specialist.operating_context}")
            print(f"  lens      : {specialist.distinct_lens}")

        complete = all(
            getattr(team, attr) is not None
            for attr in ("product_or_service_specialist", "market_specialist", "competition_specialist", "gtm_specialist")
        )
        expected_first = "service" if offer_type == "service" else "product"
        first_matches = team.product_or_service_specialist.domain == expected_first
        print("\n" + ("✅ Team complete." if complete else "❌ Team incomplete."))
        print(("✅ First specialist domain matches offer type." if first_matches
               else f"❌ First specialist domain is '{team.product_or_service_specialist.domain}', expected '{expected_first}'."))
        print(f"\nSpecialist generation complete: {result.get('specilist_generation_complete')}")

    except KeyboardInterrupt:
        print("\n⌨️ Cancelled.")
    except Exception as e:
        print(f"❌❌\n> Error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()