"""Platform metrics for the admin overview: users, runs and spend over a
window of days. Spend is estimated from list prices in settings; usage with
no configured price is reported as unpriced rather than counted as free."""

from datetime import date, datetime

from sqlalchemy import distinct, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.database import models
from backend.app.schemas.admin import AdminMetrics, CostLine, DayMetrics, KindMetrics, UserSpend
from backend.app.services import admin as admin_service
from backend.app.services.admin_directory import emails_by_id
from backend.app.services.admin_time import utc_day, window
from config import settings

MAX_DAYS = 90
TOP_SPENDERS = 5


def llm_cost(model: str, input_tokens: int, output_tokens: int) -> float | None:
    price = settings.llm_prices.get(model)
    if not price:
        return None
    return (input_tokens * price[0] + output_tokens * price[1]) / 1_000_000


def api_cost(provider: str, operation: str, calls: int) -> float | None:
    price = settings.api_call_prices.get(f"{provider}.{operation}", settings.api_call_prices.get(provider))
    return None if price is None else price * calls


async def _run_metrics(db: AsyncSession, since: datetime, series: dict[date, DayMetrics]):
    by_status = dict((await db.execute(
        select(models.Run.status, func.count()).where(models.Run.created_at >= since).group_by(models.Run.status)
    )).all())
    duration = func.extract("epoch", models.Run.finished_at - models.Run.started_at)
    finished = models.Run.status == "completed"
    by_kind = [
        KindMetrics(kind=kind, runs=runs, failed=failed, avg_duration_s=round(avg, 1) if avg is not None else None)
        for kind, runs, failed, avg in (await db.execute(
            select(models.Run.kind, func.count(), func.count().filter(models.Run.status == "failed"),
                   func.avg(duration).filter(finished))
            .where(models.Run.created_at >= since).group_by(models.Run.kind).order_by(func.count().desc())
        )).all()
    ]
    avg_all = await db.scalar(select(func.avg(duration)).where(models.Run.created_at >= since, finished))
    for day, started, failed, users in (await db.execute(
        select(utc_day(models.Run.created_at), func.count(), func.count().filter(models.Run.status == "failed"),
               func.count(distinct(models.Run.user_id)))
        .where(models.Run.created_at >= since).group_by(utc_day(models.Run.created_at))
    )).all():
        if day in series:
            series[day].runs_started, series[day].runs_failed, series[day].active_users = started, failed, users
    active = await db.scalar(select(func.count(distinct(models.Run.user_id))).where(models.Run.created_at >= since))
    done = by_status.get("completed", 0) + by_status.get("failed", 0)
    return {
        "runs_by_status": by_status,
        "runs_by_kind": by_kind,
        "active_users": active or 0,
        "success_rate": round(by_status.get("completed", 0) / done, 3) if done else None,
        "avg_duration_s": round(avg_all, 1) if avg_all is not None else None,
    }


def _add(lines: dict[str, CostLine], unpriced: set[str], name: str, calls: int, failed: int,
         cost: float | None, input_tokens: int = 0, output_tokens: int = 0) -> None:
    """Fold one (day, name) group into its line; one unpriced group makes the
    whole line unpriced rather than understated."""
    line = lines.setdefault(name, CostLine(name=name, calls=0, cost_usd=0.0))
    line.calls += calls
    line.failed_calls += failed
    line.input_tokens += input_tokens
    line.output_tokens += output_tokens
    if cost is None:
        unpriced.add(name)
        line.cost_usd = None
    elif line.cost_usd is not None:
        line.cost_usd += cost


async def _llm_costs(db: AsyncSession, since: datetime, series: dict[date, DayMetrics], unpriced: set[str]):
    c = models.LlmCall
    lines: dict[str, CostLine] = {}
    for day, model, calls, failed, tin, tout in (await db.execute(
        select(utc_day(c.created_at), c.model, func.count(), func.count().filter(c.ok.is_(False)),
               func.sum(c.input_tokens), func.sum(c.output_tokens))
        .where(c.created_at >= since).group_by(utc_day(c.created_at), c.model)
    )).all():
        cost = llm_cost(model, tin or 0, tout or 0)
        _add(lines, unpriced, model, calls, failed, cost, tin or 0, tout or 0)
        if cost is not None and day in series:
            series[day].llm_cost_usd += cost
    return list(lines.values())


async def _api_costs(db: AsyncSession, since: datetime, series: dict[date, DayMetrics], unpriced: set[str]):
    c = models.ApiCall
    lines: dict[str, CostLine] = {}
    for day, provider, operation, calls, failed in (await db.execute(
        select(utc_day(c.created_at), c.provider, c.operation, func.count(), func.count().filter(c.ok.is_(False)))
        .where(c.created_at >= since).group_by(utc_day(c.created_at), c.provider, c.operation)
    )).all():
        cost = api_cost(provider, operation, calls)
        _add(lines, unpriced, f"{provider}.{operation}", calls, failed, cost)
        if cost is not None and day in series:
            series[day].api_cost_usd += cost
    return list(lines.values())


def _total(lines: list[CostLine]) -> float:
    return round(sum(line.cost_usd or 0 for line in lines), 4)


async def _priced_spend_by(db: AsyncSession, key, *run_filters) -> dict:
    """Priced spend of the runs matching `run_filters`, grouped by `key` (a
    Run column). Unpriced usage is left out, as in the per-user totals."""
    spend: dict = {}
    llm, api, run = models.LlmCall, models.ApiCall, models.Run
    for k, model, tin, tout in (await db.execute(
        select(key, llm.model, func.sum(llm.input_tokens), func.sum(llm.output_tokens))
        .join(run, run.id == llm.run_id).where(*run_filters).group_by(key, llm.model)
    )).all():
        spend[k] = spend.get(k, 0.0) + (llm_cost(model, tin or 0, tout or 0) or 0)
    for k, provider, operation, calls in (await db.execute(
        select(key, api.provider, api.operation, func.count())
        .join(run, run.id == api.run_id).where(*run_filters).group_by(key, api.provider, api.operation)
    )).all():
        spend[k] = spend.get(k, 0.0) + (api_cost(provider, operation, calls) or 0)
    return spend


async def _economics(db: AsyncSession, since: datetime, active_users: int) -> dict:
    run = models.Run
    in_window = run.created_at >= since
    by_user = await _priced_spend_by(db, run.user_id, in_window)
    top = sorted(by_user.items(), key=lambda item: -item[1])[:TOP_SPENDERS]
    runs_by_user = dict((await db.execute(
        select(run.user_id, func.count()).where(in_window, run.user_id.in_([u for u, _ in top])).group_by(run.user_id)
    )).all()) if top else {}
    emails = await emails_by_id() if top else {}

    completed = (run.kind == "lace_onboarding", run.status == "completed", in_window)
    n_completed = await db.scalar(select(func.count()).where(*completed)) or 0
    onboarding_spend = sum((await _priced_spend_by(db, run.kind, *completed)).values())
    duration = func.extract("epoch", run.finished_at - run.started_at)
    p50, p90 = (await db.execute(
        select(func.percentile_cont(0.5).within_group(duration), func.percentile_cont(0.9).within_group(duration))
        .where(*completed)
    )).one()
    total = sum(by_user.values())
    return {
        "onboarding_p50_s": round(p50, 1) if p50 is not None else None,
        "onboarding_p90_s": round(p90, 1) if p90 is not None else None,
        "spend_per_active_user_usd": round(total / active_users, 4) if active_users else None,
        "cost_per_onboarded_lace_usd": round(onboarding_spend / n_completed, 4) if n_completed else None,
        "top_spenders": [
            UserSpend(user_id=u, email=emails.get(u), runs=runs_by_user.get(u, 0), cost_usd=round(cost, 4))
            for u, cost in top
        ],
    }


async def overview(db: AsyncSession, days: int) -> AdminMetrics:
    since, dates = window(days)
    series = {d: DayMetrics(day=d) for d in dates}
    unpriced: set[str] = set()

    runs = await _run_metrics(db, since, series)
    llm_lines = await _llm_costs(db, since, series, unpriced)
    api_lines = await _api_costs(db, since, series, unpriced)
    for point in series.values():
        point.llm_cost_usd, point.api_cost_usd = round(point.llm_cost_usd, 4), round(point.api_cost_usd, 4)
    for line in llm_lines + api_lines:
        if line.cost_usd is not None:
            line.cost_usd = round(line.cost_usd, 4)

    return AdminMetrics(
        days=days,
        total_users=len(await admin_service.list_all_users()),
        **runs,
        llm_cost_usd=_total(llm_lines),
        api_cost_usd=_total(api_lines),
        llm_costs=sorted(llm_lines, key=lambda line: -(line.cost_usd or 0)),
        api_costs=sorted(api_lines, key=lambda line: -(line.cost_usd or 0)),
        unpriced=sorted(unpriced),
        series=list(series.values()),
        **await _economics(db, since, runs["active_users"]),
    )
