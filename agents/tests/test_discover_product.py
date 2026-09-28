"""
Interactive driver for the offer discovery subgraph.
Run: python agents/tests/test_discover_product.py [offer_name] [website_url]
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

import uuid
from langgraph.types import Command

from agents.states import OfferSessionState, OfferDataSnapshot
from agents.sub_graphs.discover_product_service import build_discovery_agent
from agents.helpers import as_follow_up


def main():
    """Run the discovery agent to see how it works"""

    print(f"🚀Starting Offer Discovery Agent\n")

    # Optional command-line offer info; otherwise the agent asks for it.
    offer_name = sys.argv[1] if len(sys.argv) > 1 else None
    website_url = sys.argv[2] if len(sys.argv) > 2 else None

    # Initial state
    initial_state: OfferSessionState = {
        "offer_snapshot": OfferDataSnapshot(
            offer_name=offer_name,
            website_url=website_url,
            target_geo=['Kenya']
        ),
        # "competition_info": {"competitors": []},
        # "product_complete": False,
        # "competition_complete": False,
        # "market_complete": False,
        # "gtm_complete": False,
    }

    try:
        # Create session id & config
        session_id = str(uuid.uuid4())
        config = {"configurable": {"thread_id": session_id}}

        # Build agent then invoke
        print(f"🏃‍♂️Agent Running\n")
        agent = build_discovery_agent()
        result = agent.invoke(initial_state, config)

        # Loop through agent questions (draft confirmation / initial info)
        while result.get("__interrupt__"):
            payload = result["__interrupt__"][0].value
            interrupt_type = payload.get("type")
            question = payload.get("question")
            draft = payload.get("draft")
            lean = payload.get("lean")

            print(f"\n🤖 __Agent__\n>> Question:\n{question}\n------")
            if draft:
                print(f"   Draft:\n>>> {draft}\n------")
            if lean:
                print(f"   Best guess (uncertain): {lean}\n------")

            candidates = payload.get("product_candidates")
            if candidates:
                numbered = "\n".join(f"   {i}. {c}" for i, c in enumerate(candidates, 1))
                print(f"\n   Products found on the page:\n{numbered}\n------")

            # Get user input
            user_input = input("🧔‍♂️ Answer >> ")
            if not user_input.strip():
                print("❌ No user input was provided!")
                return

            # Agent processes user input
            print(f"\n🏃‍♂️Agent Running")
            result = agent.invoke(Command(resume=user_input), config)

        # Agent finishes
        print(f"\n🛑 Agent Completed\n")
        print(f"✅ Offer confirmed: {result.get('confirmed')}")
        print(f"   Offer type     : {result.get('offer')}")
        snapshot = result.get("offer_snapshot")
        if snapshot:
            print(f"\nFINAL CAPTURED OFFER:")
            print(f"  name         : {snapshot.offer_name}")
            print(f"  url          : {snapshot.website_url}")
            print(f"  description  : {snapshot.offer_description}")
            print(f"  intent       : {snapshot.intent}")
            print(f"  target_geo   : {snapshot.target_geo}")
            print(f"  problem_solved: {snapshot.problem_solved}")
            print(f"  how_it_works : {snapshot.how_it_works}")
            features = snapshot.features
            if features:
                print(f"  features     :")
                for f in features:
                    print(f"    - {f.name}: {f.description or ''}{' (differentiator: ' + f.differentiator + ')' if f.differentiator else ''}")
            service_uniqueness = snapshot.service_uniqueness
            if service_uniqueness:
                print(f"  service_uniqueness:")
                for f in service_uniqueness:
                    print(f"    - {f.name}: {f.description or ''}{' (differentiator: ' + f.differentiator + ')' if f.differentiator else ''}")
        follow_up = as_follow_up(result.get("follow_up"))
        replies = follow_up.user_replies
        if replies:
            print(f"\nYour raw replies ({len(replies)}):")
            for i, r in enumerate(replies, 1):
                print(f"  {i}. {r}")

    except KeyboardInterrupt:
        print("\n⌨️ Cancelled.")
    except Exception as e:
        print(f"❌❌\n> Error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()