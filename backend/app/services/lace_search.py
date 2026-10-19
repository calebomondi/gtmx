"""Search across a founder's Laces: one query over what each Lace knows and
has found, by name or text.

Every query is scoped to the user's own Laces (archived ones left out).
Case-insensitive substring matching; matches that start with the query rank
first. Dismissed competitors, accounts and opportunities are left out.
"""

import uuid
from collections.abc import Sequence

from sqlalchemy import case, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.database.lace_models import (
    Lace,
    LaceAccount,
    LaceCompetitor,
    LaceContact,
    LaceFact,
    LaceOpportunity,
    LaceOutreach,
)
from backend.app.schemas.laces import LaceSearchHit, LaceSearchKind

MIN_QUERY_LEN = 2
MAX_QUERY_LEN = 100


def _escape(term: str) -> str:
    return term.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def _contains(column, term: str):
    return column.ilike(f"%{_escape(term)}%", escape="\\")


def _prefix_first(column, term: str):
    return case((column.ilike(f"{_escape(term)}%", escape="\\"), 0), else_=1)


async def _hits(db: AsyncSession, user_id: uuid.UUID, term: str, limit: int, kind: LaceSearchKind, model,
                title, subtitle, matched: Sequence, *where) -> list[LaceSearchHit]:
    """Rows of `model` in the user's live Laces matching `term` in any of
    `matched`, best first."""
    rows = await db.execute(
        select(model.id, title, subtitle, Lace.id, Lace.name)
        .join(Lace, Lace.id == model.lace_id)
        .where(Lace.user_id == user_id, Lace.status != "archived", or_(*(_contains(c, term) for c in matched)), *where)
        .order_by(_prefix_first(title, term), title).limit(limit)
    )
    return [LaceSearchHit(kind=kind, id=row_id, title=row_title or "", subtitle=row_subtitle or None, lace_id=lace_id,
                          lace_name=lace_name)
            for row_id, row_title, row_subtitle, lace_id, lace_name in rows]


async def search(db: AsyncSession, user_id: uuid.UUID, term: str, per_kind: int) -> list[LaceSearchHit]:
    """Hits grouped by kind (Laces first), best matches first in each."""
    term = term.strip()[:MAX_QUERY_LEN]
    laces = await db.execute(
        select(Lace).where(Lace.user_id == user_id, Lace.status != "archived",
                           or_(_contains(Lace.name, term), _contains(Lace.startup_name, term),
                               _contains(Lace.website, term)))
        .order_by(_prefix_first(Lace.name, term), Lace.name).limit(per_kind))
    hits = [LaceSearchHit(kind="lace", id=lace.id, title=lace.name, subtitle=lace.startup_name or lace.website,
                          lace_id=lace.id, lace_name=lace.name) for lace in laces.scalars()]
    hits += await _hits(db, user_id, term, per_kind, "fact", LaceFact, LaceFact.claim, LaceFact.topic,
                        [LaceFact.claim], LaceFact.superseded_by_id.is_(None), LaceFact.retracted_at.is_(None))
    hits += await _hits(db, user_id, term, per_kind, "competitor", LaceCompetitor, LaceCompetitor.name,
                        LaceCompetitor.website, [LaceCompetitor.name, LaceCompetitor.website, LaceCompetitor.summary],
                        LaceCompetitor.status != "dismissed")
    hits += await _hits(db, user_id, term, per_kind, "account", LaceAccount, LaceAccount.name,
                        func.concat_ws(" · ", LaceAccount.geo, LaceAccount.website),
                        [LaceAccount.name, LaceAccount.website, LaceAccount.geo], LaceAccount.status != "dismissed")
    hits += await _hits(db, user_id, term, per_kind, "contact", LaceContact,
                        func.coalesce(LaceContact.name, LaceContact.email, LaceContact.linkedin),
                        func.concat_ws(" · ", LaceContact.title, LaceContact.email),
                        [LaceContact.name, LaceContact.email, LaceContact.title])
    hits += await _hits(db, user_id, term, per_kind, "opportunity", LaceOpportunity, LaceOpportunity.title,
                        func.concat_ws(" · ", LaceOpportunity.kind, LaceOpportunity.organiser),
                        [LaceOpportunity.title, LaceOpportunity.organiser], LaceOpportunity.status != "dismissed")
    hits += await _hits(db, user_id, term, per_kind, "conversation", LaceOutreach,
                        func.coalesce(LaceOutreach.recipient_name, LaceOutreach.recipient_address,
                                      LaceOutreach.recipient_company),
                        func.concat_ws(" · ", LaceOutreach.recipient_company, LaceOutreach.subject),
                        [LaceOutreach.recipient_name, LaceOutreach.recipient_company, LaceOutreach.subject,
                         LaceOutreach.body])
    return hits
