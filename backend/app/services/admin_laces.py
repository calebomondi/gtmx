"""Admin views of Laces across every user: who owns each, how far it has
got, and what its runs have cost."""

import uuid

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.database import models
from backend.app.database.lace_models import (
    Lace,
    LaceAccount,
    LaceCompetitor,
    LaceContact,
    LaceFact,
    LaceOpportunity,
    LaceOutreach,
)
from backend.app.schemas.admin import AdminLaceDetail, AdminLaceHolder, AdminLaceRow, Page
from backend.app.services import admin_runs, lace_members
from backend.app.services.competitors import domain_key
from backend.app.services.admin_directory import emails_by_id
from backend.app.services.admin_metrics import api_cost, llm_cost
from backend.app.services.errors import NotFoundError

RECENT_RUNS = 20


def _count(model, *where):
    return select(func.count()).select_from(model).where(*where).scalar_subquery()


async def lace_costs(db: AsyncSession, lace_ids: list[uuid.UUID]) -> dict[uuid.UUID, float | None]:
    """Per Lace, what all its runs cost; None when any of it is unpriced."""
    totals: dict[uuid.UUID, float | None] = {lace_id: 0.0 for lace_id in lace_ids}
    if not lace_ids:
        return totals
    r, c, a = models.Run, models.LlmCall, models.ApiCall

    def add(lace_id: uuid.UUID, cost: float | None) -> None:
        current = totals[lace_id]
        totals[lace_id] = None if cost is None or current is None else current + cost

    for lace_id, model, tin, tout in (await db.execute(
        select(r.lace_id, c.model, func.sum(c.input_tokens), func.sum(c.output_tokens))
        .join(r, r.id == c.run_id).where(r.lace_id.in_(lace_ids)).group_by(r.lace_id, c.model)
    )).all():
        add(lace_id, llm_cost(model, tin or 0, tout or 0))
    for lace_id, provider, operation, calls in (await db.execute(
        select(r.lace_id, a.provider, a.operation, func.count())
        .join(r, r.id == a.run_id).where(r.lace_id.in_(lace_ids)).group_by(r.lace_id, a.provider, a.operation)
    )).all():
        add(lace_id, api_cost(provider, operation, calls))
    return {lace_id: None if cost is None else round(cost, 4) for lace_id, cost in totals.items()}


def _columns():
    """The Lace and the counts every admin row shows, as one select."""
    last_run = select(func.max(models.Run.created_at)).where(models.Run.lace_id == Lace.id).scalar_subquery()
    return select(
        Lace,
        func.coalesce(last_run, Lace.created_at).label("last_active_at"),
        _count(LaceFact, LaceFact.lace_id == Lace.id, LaceFact.superseded_by_id.is_(None),
               LaceFact.retracted_at.is_(None)),
        _count(LaceCompetitor, LaceCompetitor.lace_id == Lace.id, LaceCompetitor.status == "tracked"),
        _count(LaceAccount, LaceAccount.lace_id == Lace.id, LaceAccount.status == "target"),
        _count(LaceContact, LaceContact.lace_id == Lace.id),
        _count(LaceOutreach, LaceOutreach.lace_id == Lace.id, LaceOutreach.status == "sent"),
        _count(models.Run, models.Run.lace_id == Lace.id),
    )


def _row(found, emails: dict, costs: dict) -> dict:
    lace, last_active, facts, competitors, accounts, contacts, sent, runs = found
    return dict(id=lace.id, name=lace.name, website=lace.website, startup_name=lace.startup_name, status=lace.status,
                user_id=lace.user_id, user_email=emails.get(lace.user_id), created_at=lace.created_at,
                last_active_at=last_active, facts=facts, competitors=competitors, accounts=accounts,
                contacts=contacts, sent=sent, runs=runs, cost_usd=costs.get(lace.id), domain_clash=lace.domain is None)


async def list_laces(db: AsyncSession, page: int, per_page: int, q: str | None = None,
                     user_id: uuid.UUID | None = None, clash: bool | None = None) -> Page[AdminLaceRow]:
    """Every Lace (archived ones too), most recently active first; `clash`
    keeps only the duplicates (or only the others)."""
    filters = []
    if clash is not None:
        filters.append(Lace.domain.is_(None) if clash else Lace.domain.is_not(None))
    if q and q.strip():
        needle = f"%{q.strip()}%"
        filters.append(or_(Lace.name.ilike(needle), Lace.website.ilike(needle), Lace.startup_name.ilike(needle)))
    if user_id:
        filters.append(Lace.user_id == user_id)
    total = await db.scalar(select(func.count()).select_from(Lace).where(*filters))
    query = _columns().where(*filters)
    rows = (await db.execute(query.order_by(query.selected_columns.last_active_at.desc())
                             .offset((page - 1) * per_page).limit(per_page))).all()
    costs = await lace_costs(db, [row[0].id for row in rows])
    emails = await emails_by_id() if rows else {}
    return Page(items=[AdminLaceRow(**_row(row, emails, costs)) for row in rows],
                total=total or 0, page=page, per_page=per_page)


async def holder_of(db: AsyncSession, lace: Lace) -> Lace | None:
    """For a duplicate (no domain of its own), the Lace holding its website's domain."""
    if lace.domain is not None:
        return None
    return await lace_members.lace_for_domain(db, domain_key(lace.website))


async def get_lace(db: AsyncSession, lace_id: uuid.UUID) -> AdminLaceDetail:
    found = (await db.execute(_columns().where(Lace.id == lace_id))).first()
    if found is None:
        raise NotFoundError("Lace not found.")
    lace = found[0]
    suggestions = 0
    for model in (LaceCompetitor, LaceAccount, LaceOpportunity):
        suggestions += await db.scalar(select(func.count()).select_from(model).where(
            model.lace_id == lace_id, model.status == "suggested")) or 0
    drafts = await db.scalar(select(func.count()).select_from(LaceOutreach).where(
        LaceOutreach.lace_id == lace_id, LaceOutreach.direction == "outbound", LaceOutreach.status == "draft"))
    replies = await db.scalar(select(func.count()).select_from(LaceOutreach).where(
        LaceOutreach.lace_id == lace_id, LaceOutreach.direction == "inbound"))
    opportunities = await db.scalar(select(func.count()).select_from(LaceOpportunity).where(
        LaceOpportunity.lace_id == lace_id, LaceOpportunity.status == "open"))
    emails = await emails_by_id()
    row = _row(found, emails, await lace_costs(db, [lace_id]))
    holder = await holder_of(db, lace)
    return AdminLaceDetail(
        **row, suggestions=suggestions, drafts_waiting=drafts or 0, replies=replies or 0,
        opportunities=opportunities or 0, brief_frequency=lace.brief_frequency, brief_email=lace.brief_email,
        recent_runs=(await admin_runs.list_runs(db, 1, RECENT_RUNS, lace_id=lace_id)).items,
        domain=lace.domain,
        clashes_with=holder and AdminLaceHolder(id=holder.id, name=holder.name, status=holder.status,
                                                user_id=holder.user_id, user_email=emails.get(holder.user_id),
                                                created_at=holder.created_at),
    )
