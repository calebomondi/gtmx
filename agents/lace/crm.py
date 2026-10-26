"""A CRM's deals, summed up in code so the model quotes the numbers instead
of working them out: deals and value by stage, what is open, won and lost,
the open deals nobody touched lately, and those due to close soon."""

from datetime import date, datetime, timedelta

# An open deal untouched this long is stale; one closing within this many days is close.
STALE_DAYS = 30
CLOSING_DAYS = 30
NAMES_SHOWN = 10


def _day(value) -> date | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00")).date()
    except ValueError:
        return None


def _total(deals: list[dict]) -> float:
    return round(sum(d.get("amount") or 0 for d in deals), 2)


def summarise_deals(deals: list[dict], today: date) -> dict:
    """{deals, open, won, lost, by_stage, stale, closing_soon}: counts and
    values, and the names of the deals worth a look."""
    open_ = [d for d in deals if not d.get("closed")]
    won = [d for d in deals if d.get("closed") and d.get("won")]
    stages: dict[str, list[dict]] = {}
    for deal in deals:
        stages.setdefault(deal.get("stage") or "No stage", []).append(deal)
    stale = [d for d in open_ if (u := _day(d.get("updated"))) and u < today - timedelta(days=STALE_DAYS)]
    closing = sorted((d for d in open_ if (c := _day(d.get("close_date"))) and c <= today + timedelta(days=CLOSING_DAYS)),
                     key=lambda d: _day(d.get("close_date")))
    return {
        "deals": len(deals),
        "open": {"count": len(open_), "value": _total(open_)},
        "won": {"count": len(won), "value": _total(won)},
        "lost": len(deals) - len(open_) - len(won),
        "by_stage": {stage: {"count": len(rows), "value": _total(rows)}
                     for stage, rows in sorted(stages.items(), key=lambda kv: -len(kv[1]))},
        "stale": {"count": len(stale), "days": STALE_DAYS, "names": [d.get("name") for d in stale[:NAMES_SHOWN]]},
        "closing_soon": [{"name": d.get("name"), "close_date": d.get("close_date"),
                          "overdue": _day(d.get("close_date")) < today} for d in closing[:NAMES_SHOWN]],
    }
