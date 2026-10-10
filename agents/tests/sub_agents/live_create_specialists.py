"""Harness for the create-specialists sub-agent.
Run: python agents/tests/sub_agents/live_create_specialists.py <offer_type> <offer_name> <offer_description> [target_geo_csv]
"""
import sys
from pathlib import Path

# Walk up from cwd to find repo root (has pyproject.toml).
root = Path.cwd()
while root != root.parent:
    if (root / "pyproject.toml").exists():
        break
    root = root.parent
sys.path.insert(0, str(root))

from agents.sub_agents.discover.create_specialists import build_specialist_graph
from agents.sub_agents.schema_states import OfferSessionState


def main():
    offer_type = sys.argv[1] if len(sys.argv) > 1 else "product"
    offer_name = sys.argv[2] if len(sys.argv) > 2 else "HeatherDB"
    offer_description = sys.argv[3] if len(sys.argv) > 3 else (
        "A self-organizing intelligent database."
    )
    target_geo = sys.argv[4].split(",") if len(sys.argv) > 4 else []

    initial: OfferSessionState = {
        "offer_type": offer_type,
        "offer_name": offer_name,
        "offer_description": offer_description,
        "target_market": target_geo,
        "specialists": [],
        "specialist_generation_complete": False,
    }

    graph = build_specialist_graph()
    result = graph.invoke(initial)

    team = result.get("specialists") or []
    complete = len(team) == 4
    print(f"  complete={complete}, gen_complete={result.get('specialist_generation_complete')}")
    for s in team:
        print(f"  domain={s.domain} name={s.name} role={s.role} affiliation={s.affiliation} desc={s.description}")

    assert complete, f"Expected 4 specialists, got {len(team)}"
    assert result.get("specialist_generation_complete") is True, "specialist_generation_complete not set"
    print("✅ Create specialists passed")


if __name__ == "__main__":
    main()
