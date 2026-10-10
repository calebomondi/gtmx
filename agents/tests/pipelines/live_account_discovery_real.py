"""Account discovery against REAL offers.

Run:
    PYTHONPATH=/home/mokuaxv/gtmx2/gtmx .venv/bin/python \
        agents/tests/pipelines/live_account_discovery_real.py
"""
import sys
from pathlib import Path

root = Path.cwd()
while root != root.parent:
    if (root / "pyproject.toml").exists():
        break
    root = root.parent
sys.path.insert(0, str(root))

from agents.pipelines.accounts.account_discovery import run_account_discovery
from agents.pipelines.discover.build_icp import build_icp_graph
from agents.pipelines.schema_states import IcpSessionState

REAL_OFFERS = {
    "aphorion (HeatherDB)": {
        "offer_type": "product",
        "offer_name": "HeatherDB",
        "offer_description": (
            "HeatherDB is a self-organizing, natively intelligent database that functions as a "
            "memory substrate where data itself becomes the model, eliminating the need for "
            "weights, retraining, or GPU acceleration."
        ),
        "target_market": ["Africa", "Middle East"],
        "problem": "Compute cost and GPU dependence of AI, requiring continuous expensive retraining.",
        "solution": "Data-as-the-model memory substrate with no retraining or GPU dependence.",
        "target_users": ["AI product teams in emerging markets"],
        "features": [],
        "service_uniqueness": [],
        "how_it_works": None,
    },
    "shanga": {
        "offer_type": "service",
        "offer_name": "Shanga Labs",
        "offer_description": (
            "Shanga Labs designs, manufactures and deploys electronics and IoT systems for "
            "consumer, automotive and industrial markets in emerging markets, from concept "
            "through production."
        ),
        "target_market": ["Kenya", "East Africa"],
        "problem": "Emerging-market companies lack local electronics/IoT design-manufacture capacity.",
        "solution": "End-to-end hardware engineering, manufacturing and deployment from Nairobi.",
        "target_users": ["Consumer brands", "automotive OEMs", "industrial firms"],
        "features": [],
        "service_uniqueness": [],
        "how_it_works": None,
    },
    "notion": {
        "offer_type": "service",
        "offer_name": "Notion",
        "offer_description": (
            "Notion is an AI-powered workspace that serves as a centralized system of record, "
            "enabling teams to capture context, retrieve cited answers, and automate workflows."
        ),
        "target_market": ["United States", "Europe"],
        "problem": "Fragmented knowledge and manual workflows slow collaboration.",
        "solution": "Centralized AI workspace with cited search and custom agent automations.",
        "target_users": ["Knowledge workers", "operations teams"],
        "features": [],
        "service_uniqueness": [],
        "how_it_works": None,
    },
}


def main():
    for label, offer in REAL_OFFERS.items():
        print(f"\n######################## {label} ########################")
        state: IcpSessionState = {**offer, "specialists": []}
        try:
            icp_result = build_icp_graph().invoke(state)
        except Exception as e:
            print(f"ICP stage failed: {e}")
            continue
        icp_data = icp_result.get("icp_data")
        print("icp_data:", (icp_data.model_dump_json(indent=2)[:600] if icp_data else None))

        ad_state: IcpSessionState = {
            **state,
            "icp_data": icp_data,
            "icp_findings": icp_result.get("icp_findings") or "",
            "icp_understanding": icp_result.get("icp_understanding") or "",
            "icp_complete": icp_result.get("icp_complete") is True,
            "market_data": icp_result.get("market_data"),
            "competition_data": icp_result.get("competition_data"),
            "ideal_competitor_profile": icp_result.get("ideal_competitor_profile"),
        }
        result = run_account_discovery(ad_state)
        accounts = result.get("accounts")
        print("Account list length:", len(accounts.accounts) if accounts else 0)
        if accounts:
            for acc in accounts.accounts:
                t = acc.trigger_event
                t_str = f"{t.signal_type}: {t.event}" if t else "none"
                print(f" - {acc.name} | {acc.website} | geo={acc.geo} | score={acc.score}")
                print(f"     trigger: {t_str} | source: {t.source if t else None}")
            docs = result.get("account_discovery_docs") or []
            doc_urls = {d.get("url") for d in docs}
            total = max(len(accounts.accounts), 1)
            v = sum(1 for a in accounts.accounts if a.trigger_event and a.trigger_event.source in doc_urls)
            with_site = sum(1 for a in accounts.accounts if a.website)
            with_contacts = sum(1 for a in accounts.accounts if a.key_contacts)
            print(f"rubric: trigger-source in docs {v}/{total}, website {with_site}/{total}, contacts {with_contacts}/{total}, docs {len(docs)}, queries {len(result.get('account_discovery_queries') or [])}")


if __name__ == "__main__":
    main()
