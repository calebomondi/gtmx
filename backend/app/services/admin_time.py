"""Time windows shared by the admin metrics modules."""

from datetime import UTC, date, datetime, timedelta

from sqlalchemy import Date, cast, func, literal_column


def utc_day(column):
    # A literal, not a bound parameter: Postgres only matches the GROUP BY to
    # the SELECT expression when both are textually identical.
    return cast(func.timezone(literal_column("'UTC'"), column), Date)


def window(days: int) -> tuple[datetime, list[date]]:
    """The last `days` UTC days, today included: their start and the dates."""
    first = datetime.now(UTC).date() - timedelta(days=days - 1)
    return datetime.combine(first, datetime.min.time(), tzinfo=UTC), [first + timedelta(days=i) for i in range(days)]
