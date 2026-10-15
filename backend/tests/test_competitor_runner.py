"""Competitor rows earlier runs stored with nothing researched are repaired:
re-profiled when possible, removed when not (unless the user wrote notes)."""

import uuid

from sqlalchemy import select

from agents.pipelines.competitors.get_competitors import PROFILE_FIELDS
from agents.schemas.competition import CompetitorProfile
from backend.app import competitor_runner
from backend.app.database.connect import AsyncSessionLocal
from backend.app.database.models import Competitor


async def _seed(workspace_id, name, notes=None, unsourced=PROFILE_FIELDS):
    async with AsyncSessionLocal() as db:
        db.add(Competitor(
            workspace_id=workspace_id, name=name, website=f"https://{name.lower()}.example",
            domain_key=f"{name.lower()}.example", source="agent", notes=notes,
            unsourced_fields=list(unsourced), strengths=[], weaknesses=[], opportunities=[],
            notable_customers=[], pain_signals=[], customer_sentiment=[], tracking_sources=[], evidence={},
        ))
        await db.commit()


async def test_empty_rows_are_reprofiled_or_removed(user, seed_workspace, monkeypatch):
    workspace_id = uuid.UUID(seed_workspace(user.id, "WS"))
    await _seed(workspace_id, "Fixable")
    await _seed(workspace_id, "Airline")
    await _seed(workspace_id, "Noted", notes="keep an eye on them")
    await _seed(workspace_id, "Researched", unsourced=["headquarters"])

    async def profile(survivor, _state):
        if survivor["name"] != "Fixable":
            return None
        return CompetitorProfile(name="Fixable", website=survivor["website"], description="Sells widgets.")
    monkeypatch.setattr(competitor_runner, "_profile_one_public", profile)

    assert await competitor_runner._repair_empty_rows(workspace_id, {}, refreshed=set()) == (1, 1)
    async with AsyncSessionLocal() as db:
        rows = {c.name: c for c in (await db.execute(
            select(Competitor).where(Competitor.workspace_id == workspace_id)
        )).scalars()}
    assert set(rows) == {"Fixable", "Noted", "Researched"}
    assert rows["Fixable"].description == "Sells widgets." and rows["Fixable"].deep_researched_at
