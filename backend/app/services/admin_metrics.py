"""Platform metrics for the admin overview: users, runs and spend over a
window of days. Spend is estimated from list prices in settings; usage with
no configured price is reported as unpriced rather than counted as free."""

from datetime import UTC, date, datetime, timedelta

from sqlalchemy import Date, cast, distinct, func, literal_column, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.database import models
from backend.app.schemas.admin import AdminMetrics, CostLine, DayMetrics, KindMetrics
from backend.app.services import admin as admin_service
from config import settings

MAX_DAYS = 90


def llm_cost(model: str, input_tokens: int, output_tokens: int) -> float | None:
    price = settings.llm_prices.get(model)
    if not price:
        return None
    return (input_tokens * price[0] + output_tokens * price[1]) / 1_000_000


def api_cost(provider: str, operation: str, calls: int) -> float | None:
    price = settings.api_call_prices.get(f"{provider}.{operation}", settings.api_call_prices.get(provider))
    return None if price is None else price * calls


def _day(column):
    # A literal, not a bound parameter: Postgres only matches the GROUP BY to
    # the SELECT expression when both are textually identical.
    return cast(func.timezone(literal_column("'UTC'"), column), Date)


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
        select(_day(models.Run.created_at), func.count(), func.count().filter(models.Run.status == "failed"),
               func.count(distinct(models.Run.user_id)))
        .where(models.Run.created_at >= since).group_by(_day(models.Run.created_at))
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
        select(_day(c.created_at), c.model, func.count(), func.count().filter(c.ok.is_(False)),
               func.sum(c.input_tokens), func.sum(c.output_tokens))
        .where(c.created_at >= since).group_by(_day(c.created_at), c.model)
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
        select(_day(c.created_at), c.provider, c.operation, func.count(), func.count().filter(c.ok.is_(False)))
        .where(c.created_at >= since).group_by(_day(c.created_at), c.provider, c.operation)
    )).all():
        cost = api_cost(provider, operation, calls)
        _add(lines, unpriced, f"{provider}.{operation}", calls, failed, cost)
        if cost is not None and day in series:
            series[day].api_cost_usd += cost
    return list(lines.values())


def _total(lines: list[CostLine]) -> float:
    return round(sum(line.cost_usd or 0 for line in lines), 4)


async def overview(db: AsyncSession, days: int) -> AdminMetrics:
    today = datetime.now(UTC).date()
    first = today - timedelta(days=days - 1)
    since = datetime.combine(first, datetime.min.time(), tzinfo=UTC)
    series = {first + timedelta(days=i): DayMetrics(day=first + timedelta(days=i)) for i in range(days)}
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
    )
