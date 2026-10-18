"""A Lace's target accounts: what its searches found, one per domain or name."""

import uuid
from datetime import UTC, datetime

from sqlalchemy import case, literal_column, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from agents.schemas.accounts import AccountFit, AccountRecord
from agents.schemas.lace import AccountSummary
from backend.app.database.lace_models import LaceAccount
from backend.app.services.competitors import domain_key
from backend.app.services.errors import NotFoundError

# Strongest case first, then discovery's own score.
_BY_FIT = case({"strong": 0, "moderate": 1, "weak": 2}, value=LaceAccount.fit_strength, else_=3)


def account_key(record: AccountRecord) -> str:
    """The account's identity for dedup: its domain, else its name."""
    site = record.domain or record.website
    return (domain_key(site) if site else record.name.strip().lower())[:255]


def summary(row: LaceAccount) -> AccountSummary:
    trigger = (row.record or {}).get("trigger_event") or {}
    fit = row.fit or {}
    return AccountSummary(id=str(row.id), name=row.name, account_type=row.account_type, website=row.website,
                          geo=row.geo, trigger=trigger.get("event"), need=fit.get("need"), angle=fit.get("angle"),
                          fit_strength=row.fit_strength)


def response(row: LaceAccount) -> dict:
    """The account as the API returns it."""
    record, fit = row.record or {}, row.fit
    return {"id": row.id, "name": row.name, "account_type": row.account_type, "website": row.website,
            "geo": row.geo, "summary": record.get("summary"), "trigger": record.get("trigger_event"),
            "case": fit, "status": row.status, "first_seen_at": row.first_seen_at, "last_seen_at": row.last_seen_at}


async def list_for_lace(db: AsyncSession, lace_id: uuid.UUID, status: str, limit: int) -> list[LaceAccount]:
    rows = await db.scalars(
        select(LaceAccount).where(LaceAccount.lace_id == lace_id, LaceAccount.status == status)
        .order_by(_BY_FIT, LaceAccount.score.desc().nulls_last(), LaceAccount.last_seen_at.desc()).limit(limit)
    )
    return list(rows.all())


async def set_status(db: AsyncSession, lace_id: uuid.UUID, account_id: uuid.UUID, status: str) -> LaceAccount:
    """404 for an account that is not this Lace's."""
    row = await db.scalar(select(LaceAccount).where(LaceAccount.id == account_id, LaceAccount.lace_id == lace_id))
    if row is None:
        raise NotFoundError("Account not found")
    row.status = status
    await db.commit()
    return row


async def upsert_found(db: AsyncSession, lace_id: uuid.UUID, run_id: uuid.UUID,
                       found: list[tuple[AccountRecord, AccountFit | None]]) -> tuple[int, int]:
    """Save a search's accounts. One already on file gets the fresh record and
    case but keeps its status, so an account the founder dismissed stays
    dismissed. Returns (new, refreshed)."""
    new = refreshed = 0
    now = datetime.now(UTC)
    for record, fit in found:
        stmt = insert(LaceAccount).values(
            id=uuid.uuid4(), lace_id=lace_id, key=account_key(record), name=record.name[:255],
            account_type=record.account_type, website=record.website, geo=(record.geo or None) and record.geo[:120],
            score=record.score, fit_strength=fit.strength if fit else None,
            record=record.model_dump(mode="json"), fit=fit.model_dump(mode="json") if fit else None,
            found_by_run_id=run_id, last_seen_at=now,
        )
        refresh = {c: stmt.excluded[c] for c in (
            "name", "account_type", "website", "geo", "score", "fit_strength", "record", "fit",
            "found_by_run_id", "last_seen_at")}
        # Returns whether the row was inserted: xmax is 0 on a row this
        # statement inserted, and set on one it updated.
        stmt = stmt.on_conflict_do_update(constraint="uq_lace_accounts_lace_id_key", set_=refresh) \
            .returning(literal_column("xmax = 0"))
        if await db.scalar(stmt):
            new += 1
        else:
            refreshed += 1
    return new, refreshed
