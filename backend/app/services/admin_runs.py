"""Admin views of runs (with their event timeline and cost) and signals,
across every user."""

import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.database import models
from backend.app.database.lace_models import Lace
from backend.app.schemas.admin import AdminRunDetail, AdminRunEvent, AdminRunRow, CostLine, Page
from backend.app.services.admin_directory import emails_by_id
from backend.app.services.admin_metrics import api_cost, llm_cost
from backend.app.services.errors import NotFoundError

MAX_EVENTS = 500


async def _cost_lines(db: AsyncSession, run_ids: list[uuid.UUID]) -> dict[uuid.UUID, tuple[list, list]]:
    """Per run: (LLM lines, API lines), each line priced or None if unpriced."""
    out = {rid: ([], []) for rid in run_ids}
    c = models.LlmCall
    for rid, model, calls, failed, tin, tout in (await db.execute(
        select(c.run_id, c.model, func.count(), func.count().filter(c.ok.is_(False)),
               func.sum(c.input_tokens), func.sum(c.output_tokens))
        .where(c.run_id.in_(run_ids)).group_by(c.run_id, c.model)
    )).all():
        cost = llm_cost(model, tin or 0, tout or 0)
        out[rid][0].append(CostLine(name=model, calls=calls, failed_calls=failed, input_tokens=tin or 0,
                                    output_tokens=tout or 0, cost_usd=None if cost is None else round(cost, 4)))
    a = models.ApiCall
    for rid, provider, operation, calls, failed in (await db.execute(
        select(a.run_id, a.provider, a.operation, func.count(), func.count().filter(a.ok.is_(False)))
        .where(a.run_id.in_(run_ids)).group_by(a.run_id, a.provider, a.operation)
    )).all():
        cost = api_cost(provider, operation, calls)
        out[rid][1].append(CostLine(name=f"{provider}.{operation}", calls=calls, failed_calls=failed,
                                    cost_usd=None if cost is None else round(cost, 4)))
    return out


def _total(lines: list[CostLine]) -> float | None:
    if any(line.cost_usd is None for line in lines):
        return None
    return round(sum(line.cost_usd for line in lines), 4)


def _row(run: models.Run, emails: dict, workspace_name: str | None, lace_name: str | None,
         lines: tuple[list, list]) -> dict:
    duration = None
    if run.started_at and run.finished_at:
        duration = round((run.finished_at - run.started_at).total_seconds(), 1)
    return dict(
        id=run.id, kind=run.kind, status=run.status, user_id=run.user_id, user_email=emails.get(run.user_id),
        workspace_id=run.workspace_id, workspace_name=workspace_name, lace_id=run.lace_id, lace_name=lace_name,
        error=run.error,
        created_at=run.created_at, started_at=run.started_at, finished_at=run.finished_at,
        duration_s=duration, cost_usd=_total(lines[0] + lines[1]),
    )


async def list_runs(
    db: AsyncSession, page: int, per_page: int, *, status: str | None = None, kind: str | None = None,
    user_id: uuid.UUID | None = None, workspace_id: uuid.UUID | None = None, lace_id: uuid.UUID | None = None,
) -> Page[AdminRunRow]:
    r = models.Run
    filters = [col == value for col, value in
               ((r.status, status), (r.kind, kind), (r.user_id, user_id), (r.workspace_id, workspace_id),
                (r.lace_id, lace_id))
               if value is not None]
    total = await db.scalar(select(func.count()).select_from(r).where(*filters))
    rows = (await db.execute(
        select(r, models.Workspace.name, Lace.name)
        .outerjoin(models.Workspace, models.Workspace.id == r.workspace_id).outerjoin(Lace, Lace.id == r.lace_id)
        .where(*filters).order_by(r.created_at.desc()).offset((page - 1) * per_page).limit(per_page)
    )).all()
    lines = await _cost_lines(db, [run.id for run, _, _ in rows])
    emails = await emails_by_id() if rows else {}
    return Page(
        items=[AdminRunRow(**_row(run, emails, ws_name, lace_name, lines[run.id])) for run, ws_name, lace_name in rows],
        total=total or 0, page=page, per_page=per_page,
    )


async def get_run(db: AsyncSession, run_id: uuid.UUID) -> AdminRunDetail:
    found = (await db.execute(
        select(models.Run, models.Workspace.name, Lace.name)
        .outerjoin(models.Workspace, models.Workspace.id == models.Run.workspace_id)
        .outerjoin(Lace, Lace.id == models.Run.lace_id)
        .where(models.Run.id == run_id)
    )).first()
    if found is None:
        raise NotFoundError("Run not found.")
    run, workspace_name, lace_name = found
    events = (await db.execute(
        select(models.RunEvent).where(models.RunEvent.run_id == run_id)
        .order_by(models.RunEvent.id).limit(MAX_EVENTS + 1)
    )).scalars().all()
    lines = (await _cost_lines(db, [run_id]))[run_id]
    return AdminRunDetail(
        **_row(run, await emails_by_id(), workspace_name, lace_name, lines),
        input=run.input, progress=run.progress,
        events=[AdminRunEvent(id=e.id, type=e.type, payload=e.payload, created_at=e.created_at)
                for e in events[:MAX_EVENTS]],
        events_truncated=len(events) > MAX_EVENTS,
        llm_costs=lines[0], api_costs=lines[1],
    )


async def user_spend(db: AsyncSession, user_id: uuid.UUID) -> float:
    """Priced spend across a user's runs; unpriced usage is left out here and
    surfaced in the metrics' `unpriced` list instead."""
    run_ids = (await db.execute(select(models.Run.id).where(models.Run.user_id == user_id))).scalars().all()
    lines = await _cost_lines(db, list(run_ids))
    return round(sum(line.cost_usd or 0 for llm, api in lines.values() for line in llm + api), 4)
