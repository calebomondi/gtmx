"""What every one of a founder's Laces has saved, for Home: the open
opportunities, target customers and tracked competitors of each live Lace,
each with its Lace, and how many finds wait for review. Each list keeps its
Lace's own filters and order."""

import uuid
from dataclasses import dataclass, field

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.database.lace_models import Lace, LaceAccount, LaceCompetitor, LaceOpportunity
from backend.app.services import lace_accounts, lace_competitors, lace_opportunities


@dataclass
class Saved:
    # (Lace, row) pairs, Laces in sidebar order.
    opportunities: list = field(default_factory=list)
    accounts: list = field(default_factory=list)
    competitors: list = field(default_factory=list)
    to_review: dict[str, int] = field(default_factory=lambda: {"opportunities": 0, "accounts": 0, "competitors": 0})


async def _suggested(db: AsyncSession, model, lace_ids: list[uuid.UUID]) -> int:
    return await db.scalar(select(func.count()).select_from(model).where(
        model.lace_id.in_(lace_ids), model.status == "suggested")) or 0


async def saved(db: AsyncSession, user_id: uuid.UUID, per_lace: int) -> Saved:
    laces = list((await db.scalars(select(Lace).where(Lace.user_id == user_id, Lace.status != "archived")
                                   .order_by(Lace.pinned.desc(), Lace.created_at))).all())
    out = Saved()
    for lace in laces:
        out.opportunities += [(lace, r) for r in await lace_opportunities.list_for_lace(db, lace.id, "open", per_lace)]
        out.accounts += [(lace, r) for r in await lace_accounts.list_for_lace(db, lace.id, "target", per_lace)]
        out.competitors += [(lace, r) for r in await lace_competitors.list_for_lace(db, lace.id, "tracked", per_lace)]
    ids = [lace.id for lace in laces]
    if ids:
        out.to_review = {"opportunities": await _suggested(db, LaceOpportunity, ids),
                         "accounts": await _suggested(db, LaceAccount, ids),
                         "competitors": await _suggested(db, LaceCompetitor, ids)}
    return out
