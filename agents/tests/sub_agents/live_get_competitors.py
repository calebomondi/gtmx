"""Standalone competitor-hunting harness using real cases.

This is a dry-run style script that *really* runs the competitor graph against
real offers from Aphorion, Shanga and Notion.

Run:
    PYTHONPATH=/home/mokuaxv/gtmx2/gtmx .venv/bin/python \
        agents/tests/sub_agents/live_get_competitors.py
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

from agents.sub_agents.competitors.get_competitors import build_competitors_graph, state_from_workspace

OFFERS = [
    {
        "offer_name": "HeatherDB",
        "offer_type": "product",
        "offer_description": (
            "HeatherDB is a self-organizing, natively intelligent database that functions as a memory substrate "
            "where data itself becomes the model, eliminating the need for model weights, retraining, or GPUs."
        ),
        "problem": "General-purpose LLMs need enormous compute for reasoning that a storage-shaped design could do far more cheaply.",
        "solution": "A storage-shaped reasoning paradigm: an episodic knowledge index paired with a compact reasoning core.",
        "features": ["Self-organizing memory substrate", "Model ingestion", "Commodity hardware compatibility"],
        "own_website": "https://aphorion.co/",
        "target_market": ["Kenya", "Nigeria", "South Africa"],
        "ideal_competitor_profile": {
            "category_definition": "databases that run AI reasoning on commodity hardware",
            "archetypes": [
                {"label": "open-source edge RAG frameworks", "geography_scope": "global"},
                {"label": "regional AI integrators", "geography_scope": "regional"},
                {"label": "sovereign cloud inference providers", "geography_scope": "global"},
            ],
            "confidence": "high",
        },
    },
    {
        "offer_name": "Engineering and Innovation Consultancy",
        "offer_type": "service",
        "offer_description": (
            "Engineering and Innovation Consultancy provides end-to-end R&D services that guide hardware and software "
            "projects from initial concept and feasibility studies through prototyping, pilot deployment, mass "
            "manufacturing, and ongoing aftermarket support."
        ),
        "problem": "The complexity and fragmentation of bringing hardware products to market, specifically the need for integrated R&D, prototyping, manufacturing, and support that accounts for the operating realities of emerging markets.",
        "solution": "A structured hardware/software engineering lifecycle from consultancy to manufacturing.",
        "features": [],
        "own_website": "https://shangalabs.com/",
        "target_market": ["Kenya"],
        "ideal_competitor_profile": {
            "category_definition": "engineering consultancies that help hardware startups integrate design and manufacturing",
            "archetypes": [
                {"label": "Boutique hardware engineering firms", "geography_scope": "local"},
                {"label": "Global low-cost design houses", "geography_scope": "global"},
                {"label": "OEM resellers with product development armies", "geography_scope": "global"},
            ],
            "confidence": "high",
        },
    },
    {
        "offer_name": "Notion",
        "offer_type": "product",
        "offer_description": (
            "Notion is an AI workspace that works for you. Capture context, find answers, and automate tasks with AI built for your team."
        ),
        "problem": "Knowledge is scattered and slow to find.",
        "solution": "One workspace for docs, wikis, and project tracking with AI built in.",
        "features": ["AI Workspace", "System of Record", "Notion Custom Agents"],
        "own_website": "https://www.notion.so/",
        "target_market": ["United States", "Germany", "Japan"],
        "ideal_competitor_profile": {
            "category_definition": "AI-enhanced productivity and knowledge management software",
            "archetypes": [
                {"label": "Horizontal productivity suites", "geography_scope": "global"},
                {"label": "Vertical knowledge-base platforms", "geography_scope": "regional"},
                {"label": "Notetaking and documentation tools", "geography_scope": "global"},
            ],
            "confidence": "high",
        },
    },
]


def main():
    graph = build_competitors_graph()
    for offer in OFFERS:
        state = state_from_workspace(**offer)
        result = graph.invoke(state)
        profiles = result.get("competitor_profiles") or []
        print(f"\n=== {offer['offer_name']} ===")
        print(f"Total candidates profiled: {len(profiles)}")
        for p in profiles[:10]:
            print(f"  - {p.name} | {p.website} | archetype={p.matched_archetype}")
        # Cap at 10 for now
        if len(profiles) > 10:
            print(f"  ... truncated to 10 out of {len(profiles)}")


if __name__ == "__main__":
    main()
