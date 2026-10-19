"""A Lace's target accounts: what its searches found, one per domain or name."""

import uuid
from datetime import UTC, datetime

from sqlalchemy import case, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from agents.schemas.accounts import AccountFit, AccountRecord
from agents.lace.contacts import contact_status
from agents.schemas.lace import AccountSummary
from backend.app.database.lace_models import LaceAccount
from backend.app.services import lace_contacts
from backend.app.services.competitors import domain_key
from backend.app.services.errors import NotFoundError

# Strongest case first, then discovery's own score.
BY_FIT = case({"strong": 0, "moderate": 1, "weak": 2}, value=LaceAccount.fit_strength, else_=3)


def account_key(record: AccountRecord) -> str:
    """The account's identity for dedup: its domain, else its name."""
    site = record.domain or record.website
    return (domain_key(site) if site else record.name.strip().lower())[:255]


def _people(record: dict) -> list[dict]:
    return [{k: v for k, v in c.items() if v} for c in record.get("key_contacts") or []]


def summary(row: LaceAccount) -> AccountSummary:
    record = row.record or {}
    trigger = record.get("trigger_event") or {}
    fit = row.fit or {}
    return AccountSummary(id=str(row.id), name=row.name, account_type=row.account_type, website=row.website,
                          geo=row.geo, trigger=trigger.get("event"), need=fit.get("need"), angle=fit.get("angle"),
                          fit_strength=row.fit_strength, contact_status=row.contact_status,
                          contacts=_people(record), channels=record.get("socials") or {})


def response(row: LaceAccount) -> dict:
    """The account as the API returns it."""
    record, fit = row.record or {}, row.fit
    return {"id": row.id, "name": row.name, "account_type": row.account_type, "website": row.website,
            "geo": row.geo, "summary": record.get("summary"), "trigger": record.get("trigger_event"),
            "case": fit, "status": row.status, "contact_status": row.contact_status, "contacts": _people(record),
            "channels": record.get("socials") or {}, "contacts_checked_at": row.contacts_checked_at,
            "first_seen_at": row.first_seen_at, "last_seen_at": row.last_seen_at}


async def list_for_lace(db: AsyncSession, lace_id: uuid.UUID, status: str, limit: int) -> list[LaceAccount]:
    rows = await db.scalars(
        select(LaceAccount).where(LaceAccount.lace_id == lace_id, LaceAccount.status == status)
        .order_by(BY_FIT, LaceAccount.score.desc().nulls_last(), LaceAccount.last_seen_at.desc()).limit(limit)
    )
    return list(rows.all())


async def get_in_lace(db: AsyncSession, lace_id: uuid.UUID, account_id: uuid.UUID) -> LaceAccount:
    """404 for an account that is not this Lace's."""
    row = await db.scalar(select(LaceAccount).where(LaceAccount.id == account_id, LaceAccount.lace_id == lace_id))
    if row is None:
        raise NotFoundError("Account not found")
    return row


async def set_status(db: AsyncSession, lace_id: uuid.UUID, account_id: uuid.UUID, status: str) -> LaceAccount:
    row = await get_in_lace(db, lace_id, account_id)
    row.status = status
    await db.commit()
    return row


def _merged(found: AccountRecord, stored: dict | None) -> AccountRecord:
    """A re-found account's fresh record, keeping the people and pages already
    on file (a contact search may have filled them in since)."""
    if not stored:
        return found
    before = AccountRecord.model_validate(stored)
    seen = {(c.email or "").lower() or (c.linkedin or "").lower() for c in found.key_contacts}
    kept = [c for c in before.key_contacts if ((c.email or "").lower() or (c.linkedin or "").lower()) not in seen]
    return found.model_copy(update={"key_contacts": [*found.key_contacts, *kept],
                                    "socials": {**before.socials, **found.socials}})


async def upsert_found(db: AsyncSession, lace_id: uuid.UUID, run_id: uuid.UUID,
                       found: list[tuple[AccountRecord, AccountFit | None]]) -> tuple[int, int]:
    """Save a search's accounts. One already on file gets the fresh record and
    case, keeping its contacts and its status, so an account the founder
    dismissed stays dismissed. Returns (new, refreshed)."""
    keys = [account_key(r) for r, _ in found]
    stored = dict((await db.execute(select(LaceAccount.key, LaceAccount.record).where(
        LaceAccount.lace_id == lace_id, LaceAccount.key.in_(keys)))).all())
    now = datetime.now(UTC)
    for (found_record, fit), key in zip(found, keys):
        record = _merged(found_record, stored.get(key))
        stmt = insert(LaceAccount).values(
            id=uuid.uuid4(), lace_id=lace_id, key=key, name=record.name[:255],
            account_type=record.account_type, website=record.website, geo=(record.geo or None) and record.geo[:120],
            score=record.score, fit_strength=fit.strength if fit else None, contact_status=contact_status(record),
            record=record.model_dump(mode="json"), fit=fit.model_dump(mode="json") if fit else None,
            found_by_run_id=run_id, last_seen_at=now,
        )
        refresh = {c: stmt.excluded[c] for c in (
            "name", "account_type", "website", "geo", "score", "fit_strength", "contact_status", "record", "fit",
            "found_by_run_id", "last_seen_at")}
        account_id = await db.scalar(stmt.on_conflict_do_update(
            constraint="uq_lace_accounts_lace_id_key", set_=refresh).returning(LaceAccount.id))
        await lace_contacts.sync(db, lace_id, account_id, found_record.key_contacts, "discovery")
    refreshed = len(set(keys) & set(stored))
    return len(set(keys)) - refreshed, refreshed


async def due_for_contacts(db: AsyncSession, lace_id: uuid.UUID, ids: list[uuid.UUID] | None,
                           limit: int) -> list[LaceAccount]:
    """The accounts to search contacts for: the ones named, else every target
    whose contacts were never searched, strongest fit first."""
    query = select(LaceAccount).where(LaceAccount.lace_id == lace_id, LaceAccount.status == "target")
    if ids:
        query = query.where(LaceAccount.id.in_(ids))
    else:
        query = query.where(LaceAccount.contacts_checked_at.is_(None))
    return list((await db.scalars(query.order_by(BY_FIT, LaceAccount.score.desc().nulls_last()).limit(limit))).all())


async def save_contacts(db: AsyncSession, account_id: uuid.UUID, record: AccountRecord) -> None:
    row = await db.get(LaceAccount, account_id)
    if row is not None:
        row.record = record.model_dump(mode="json")
        row.contact_status = contact_status(record)
        row.contacts_checked_at = datetime.now(UTC)
        await lace_contacts.sync(db, row.lace_id, account_id, record.key_contacts, "contact_search")
