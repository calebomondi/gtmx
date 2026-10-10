"""Turn run outcomes into feed signals. Called when a run finishes or fails;
best effort -- a signal that cannot be written must never fail the run."""

import uuid

from sqlalchemy import select

from backend.app.database import models
from backend.app.database.connect import AsyncSessionLocal
from backend.app.services import signals as signal_service
from utils.log import logger

_KIND_LABEL = {
    "discovery": "Discovery",
    "competitors": "Competitor research",
    "accounts": "Account discovery",
    "competitor_research": "Competitor profiling",
    "outreach_drafts": "Outreach drafting",
}
_MAX_ACCOUNT_SIGNALS = 5


async def _emit(build) -> None:
    try:
        async with AsyncSessionLocal() as db:
            run_signals = await build(db)
            if run_signals:
                await signal_service.emit(db, run_signals)
    except Exception:  # noqa: BLE001 -- see module docstring
        logger.exception("Could not emit feed signals")


async def discovery_finished(run_id: uuid.UUID, user_id: uuid.UUID, workspace_id: uuid.UUID, values: dict) -> None:
    async def build(_db):
        profile = values.get("ideal_competitor_profile")
        icp = values.get("icp_data")
        parts = []
        if profile is not None and getattr(profile, "archetypes", None):
            parts.append(f"{len(profile.archetypes)} competitor archetypes")
        if icp is not None and getattr(icp, "industries", None):
            parts.append("ICP: " + ", ".join(icp.industries))
        return [signal_service.build(
            user_id=user_id, workspace_id=workspace_id, run_id=run_id, category="product",
            title="Discovery finished", entity=values.get("offer_name") or "",
            summary=" · ".join(parts) or "Offer, market, competition and ICP research are ready.",
            reason="Your research run completed.",
        )]
    await _emit(build)


async def competitors_found(run_id: uuid.UUID) -> None:
    """One signal per competitor this run added to the watch list."""
    async def build(db):
        run = await db.get(models.Run, run_id)
        rows = (await db.execute(
            select(models.Competitor).where(
                models.Competitor.run_id == run_id,
                models.Competitor.first_seen_at >= run.started_at,
            )
        )).scalars().all()
        return [signal_service.build(
            user_id=run.user_id, workspace_id=run.workspace_id, run_id=run_id, category="competitor",
            title=f"New competitor: {c.name}", entity=c.name,
            summary=c.positioning or c.description or c.offering or "",
            reason=f"Matches the '{c.matched_archetype}' archetype." if c.matched_archetype else "Found by the competitor agent.",
            source_url=c.website,
        ) for c in rows]
    await _emit(build)


async def accounts_found(run_id: uuid.UUID) -> None:
    """The best new target accounts (highest score first)."""
    async def build(db):
        run = await db.get(models.Run, run_id)
        rows = (await db.execute(
            select(models.Account)
            .where(models.Account.run_id == run_id, models.Account.created_at >= run.started_at)
            .order_by(models.Account.score.desc().nulls_last())
            .limit(_MAX_ACCOUNT_SIGNALS)
        )).scalars().all()
        return [signal_service.build(
            user_id=run.user_id, workspace_id=run.workspace_id, run_id=run_id, category="opportunity",
            title=f"Target account: {a.name}", entity=a.name,
            summary=(a.why_reach_out or a.why_selected or [a.industry or ""])[0],
            reason="Matches your ideal customer profile.", source_url=a.website,
        ) for a in rows]
    await _emit(build)


async def outreach_drafted(run_id: uuid.UUID, count: int) -> None:
    async def build(db):
        run = await db.get(models.Run, run_id)
        return [signal_service.build(
            user_id=run.user_id, workspace_id=run.workspace_id, run_id=run_id, category="outbound",
            title=f"{count} outreach draft{'s' if count != 1 else ''} ready", entity="Outreach",
            summary="Review, edit and approve them in Reach Out. Nothing is sent without you.",
            reason="You asked the agent to draft outreach.",
        )] if count else []
    await _emit(build)


async def run_failed(run_id: uuid.UUID, message: str) -> None:
    async def build(db):
        run = await db.get(models.Run, run_id)
        if run is None or run.workspace_id is None or run.kind == "chat":
            # No workspace yet (an early discovery failure), or a chat reply,
            # whose failure the chat itself shows -- the feed is not the place.
            return []
        return [signal_service.build(
            user_id=run.user_id, workspace_id=run.workspace_id, run_id=run_id, category="agent",
            title=f"{_KIND_LABEL.get(run.kind, 'Agent run')} failed", entity=_KIND_LABEL.get(run.kind, run.kind),
            summary=message, reason="A run you started stopped before finishing.",
        )]
    await _emit(build)
