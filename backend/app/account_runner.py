"""The database-facing half of the account-discovery agent.

Mirrors competitor_runner: the agent graph itself does no persistence, so this
module hydrates its state from the workspace's persisted insights, invokes the
graph, upserts the resulting `accounts`, and reports progress on the run row.

Dedup matches on `(workspace_id, name)` — a firm matched by two different query
blobs refreshes instead of doubling. `selected` is the user's and is never
clobbered by a re-run.
"""

import asyncio
import uuid
from datetime import UTC, datetime
from typing import Optional

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from agents.schemas.competition import IdealCompetitorProfile
from agents.schemas.icp import ICP
from agents.pipelines.accounts.account_discovery import (
    build_account_discovery_graph,
)

from backend.app.database.connect import AsyncSessionLocal
from backend.app.database.models import Account, ProductProfile

_PRESERVED_ON_REFRESH = ("id", "source", "selected", "run_id")


def _hydrate(profile: Optional[ProductProfile]) -> dict:
    insights = (profile.insights or {}) if profile else {}
    snapshot = insights.get("offer_snapshot") or {}
    icp = None
    if isinstance(insights.get("icp"), dict):
        try:
            icp = ICP(**insights["icp"])
        except Exception:
            icp = None
    profile_obj = None
    if isinstance(insights.get("ideal_competitor_profile"), dict):
        try:
            profile_obj = IdealCompetitorProfile(**insights["ideal_competitor_profile"])
        except Exception:
            profile_obj = None
    return {
        "offer_name": snapshot.get("offer_name"),
        "offer_type": insights.get("offer_type"),
        "target_market": snapshot.get("target_geo") or [],
        "icp_data": icp,
        "ideal_competitor_profile": profile_obj,
        "offer_findings": (insights.get("research") or {}).get("offer") or insights.get("domain_understanding"),
        "market_findings": (insights.get("research") or {}).get("market"),
        "competition_findings": (insights.get("research") or {}).get("competition"),
        "offer_domain_fit_understanding": insights.get("domain_understanding"),
        "product_market_fit_understanding": insights.get("market_fit_understanding"),
        "market_data": insights.get("market_data"),
        "competition_data": insights.get("competition_data"),
        "messages": [],
    }


def _account_values(account) -> dict:
    return {
        "name": account.name,
        "account_type": account.account_type or "company",
        "website": account.website,
        "domain": account.domain,
        "platform": account.platform,
        "venue": account.venue,
        "event_date": account.event_date,
        "member_size": account.member_size,
        "summary": account.summary,
        "industry": account.industry,
        "size": account.size,
        "geo": account.geo,
        "tech_stack": list(account.tech_stack or []),
        "recent_news": list(account.recent_news or []),
        "key_contacts": [c.model_dump(mode="json") for c in (account.key_contacts or [])],
        "socials": dict(account.socials or {}),
        "pain_signals": list(account.pain_signals or []),
        "hiring_signals": list(account.hiring_signals or []),
        "sources": [s.model_dump(mode="json") for s in (account.sources or [])],
        "source_queries": list(account.source_queries or []),
        "score": account.score,
        "score_breakdown": account.score_breakdown,
        "why_selected": list(account.why_selected or []),
        "why_reach_out": list(account.why_reach_out or []),
        "trigger_event": account.trigger_event.model_dump(mode="json") if account.trigger_event else None,
    }


async def _upsert_accounts(
    workspace_id: uuid.UUID,
    run_id: Optional[uuid.UUID],
    rows: list[dict],
) -> tuple[int, int]:
    async with AsyncSessionLocal() as db:
        inserted = 0
        refreshed = 0
        for values in rows:
            clobbered = [f for f in _PRESERVED_ON_REFRESH if f in values]
            if clobbered:
                raise ValueError(f"account refresh would overwrite {clobbered}")
            existing = await db.execute(
                select(Account).where(
                    Account.workspace_id == workspace_id,
                    Account.name == values["name"],
                )
            )
            account = existing.scalar_one_or_none()
            if account is None:
                account = Account(
                    workspace_id=workspace_id,
                    run_id=run_id,
                    created_at=datetime.now(UTC),
                    **values,
                )
                db.add(account)
                inserted += 1
                continue
            for field, value in values.items():
                setattr(account, field, value)
            if run_id is not None:
                account.run_id = run_id
            refreshed += 1
        try:
            await db.commit()
        except IntegrityError:
            await db.rollback()
        return inserted, refreshed


async def run_account_discovery_for_workspace(
    workspace_id: uuid.UUID,
    run_id: Optional[uuid.UUID] = None,
) -> dict:
    async with AsyncSessionLocal() as db:
        profile = (
            await db.execute(
                select(ProductProfile).where(ProductProfile.workspace_id == workspace_id)
            )
        ).scalar_one_or_none()

    if profile is None:
        raise RuntimeError("No product profile for this workspace — run discovery first.")

    state = _hydrate(profile)
    if not state.get("icp_data"):
        raise RuntimeError(
            "No ICP found for this workspace — finish the Offer run first."
        )

    graph = build_account_discovery_graph(checkpointer=False)
    # Node fns are sync and I/O-heavy; run the whole graph off the event loop
    # so a long search run doesn't block unrelated requests.
    final = await asyncio.to_thread(graph.invoke, state)
    accounts = (final.get("accounts") or {}).get("accounts") if isinstance(final.get("accounts"), dict) else (getattr(final.get("accounts"), "accounts", None) or [])

    rows = []
    for a in accounts or []:
        try:
            rows.append(_account_values(a))
        except Exception:
            continue

    inserted, refreshed = await _upsert_accounts(workspace_id, run_id, rows)
    return {
        "candidates_seen": len(final.get("account_discovery_docs") or []),
        "found": len(rows),
        "inserted": inserted,
        "refreshed": refreshed,
    }
