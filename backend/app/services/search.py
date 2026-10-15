"""Search Anything: one query over everything the user owns, by name.

Every query is scoped to the user: their own workspaces and projects, and
competitors, accounts and signals reached only through their workspaces.
Case-insensitive substring matching; names that start with the query rank
first. Research text (insights) is not searched.
"""

import uuid

from sqlalchemy import case, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.database import models
from backend.app.schemas.search import SearchHit

MIN_QUERY_LEN = 2
MAX_QUERY_LEN = 100


def _escape(term: str) -> str:
    return term.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def _contains(column, term: str):
    return column.ilike(f"%{_escape(term)}%", escape="\\")


def _prefix_first(column, term: str):
    return case((column.ilike(f"{_escape(term)}%", escape="\\"), 0), else_=1)


async def _workspaces(db: AsyncSession, user_id: uuid.UUID, term: str, limit: int) -> list[SearchHit]:
    W, P = models.Workspace, models.ProductProfile
    rows = await db.execute(
        select(W, P.product_name, P.product_url)
        .outerjoin(P, P.workspace_id == W.id)
        .where(W.user_id == user_id, or_(_contains(W.name, term), _contains(P.product_name, term), _contains(P.product_url, term)))
        .order_by(_prefix_first(W.name, term), W.archived, W.last_activity.desc())
        .limit(limit)
    )
    return [
        SearchHit(
            kind="workspace", id=w.id, title=w.name or product_name or "Untitled workspace", subtitle=url,
            workspace_id=w.id, archived=w.archived, offer_type=w.offer_type,
        )
        for w, product_name, url in rows
    ]


async def _projects(db: AsyncSession, user_id: uuid.UUID, term: str, limit: int) -> list[SearchHit]:
    P = models.Project
    rows = await db.scalars(
        select(P).where(P.user_id == user_id, _contains(P.name, term))
        .order_by(_prefix_first(P.name, term), P.archived, P.last_activity.desc())
        .limit(limit)
    )
    return [SearchHit(kind="project", id=p.id, title=p.name, archived=p.archived) for p in rows]


async def _in_workspaces(db: AsyncSession, user_id: uuid.UUID, term: str, limit: int, model, kind, subtitle_col):
    """Competitors and accounts: rows that belong to one of the user's workspaces."""
    W = models.Workspace
    rows = await db.execute(
        select(model.id, model.name, subtitle_col, W.id, W.name, W.archived)
        .join(W, W.id == model.workspace_id)
        .where(W.user_id == user_id, or_(_contains(model.name, term), _contains(subtitle_col, term)))
        .order_by(_prefix_first(model.name, term), W.archived, model.name)
        .limit(limit)
    )
    return [
        SearchHit(
            kind=kind, id=row_id, title=name, subtitle=" · ".join(filter(None, [where, ws_name])) or None,
            workspace_id=ws_id, archived=archived,
        )
        for row_id, name, where, ws_id, ws_name, archived in rows
    ]


async def _signals(db: AsyncSession, user_id: uuid.UUID, term: str, limit: int) -> list[SearchHit]:
    S, W = models.Signal, models.Workspace
    rows = await db.execute(
        select(S.id, S.title, S.workspace_id, W.name, W.archived)
        .join(W, W.id == S.workspace_id)
        .where(S.user_id == user_id, W.user_id == user_id, S.dismissed.is_(False),
               or_(_contains(S.title, term), _contains(S.entity, term)))
        .order_by(S.created_at.desc())
        .limit(limit)
    )
    return [
        SearchHit(kind="signal", id=sid, title=title, subtitle=ws_name, workspace_id=ws_id, archived=archived)
        for sid, title, ws_id, ws_name, archived in rows
    ]


async def search(db: AsyncSession, user_id: uuid.UUID, query: str, limit: int) -> list[SearchHit]:
    """Up to `limit` hits of each kind, grouped by kind."""
    term = query.strip()
    if len(term) < MIN_QUERY_LEN:
        return []
    return [
        *await _workspaces(db, user_id, term, limit),
        *await _projects(db, user_id, term, limit),
        *await _in_workspaces(db, user_id, term, limit, models.Competitor, "competitor", models.Competitor.website),
        *await _in_workspaces(db, user_id, term, limit, models.Account, "account", models.Account.domain),
        *await _signals(db, user_id, term, limit),
    ]
