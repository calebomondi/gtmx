"""The people at a Lace's target accounts, as rows the founder's Contacts
can list, filter and sort. Synced from an account's record whenever the
record's people are saved: by an account search or a contact search."""

import uuid
from collections.abc import Iterable
from datetime import UTC, datetime

from sqlalchemy import delete, func, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from agents.schemas.accounts import PERSON_SOCIALS, ContactRecord, social_profile_url
from agents.schemas.lace import ContactSource, NewContact, OutreachChannel
from backend.app.database.lace_models import LaceAccount, LaceContact
from backend.app.services.errors import InvalidInputError, NotFoundError


# What "there's no ... for this person" names, per channel.
_ADDRESS_LABEL: dict[str, str] = {"email": "email address", "linkedin": "LinkedIn profile", "x": "X account",
                                  "instagram": "Instagram account", "facebook": "Facebook profile",
                                  "tiktok": "TikTok account"}


def _clean(value: str | None) -> str:
    return (value or "").strip()


def contact_key(contact: ContactRecord) -> str | None:
    """Who the contact is, for dedup: their email, else their LinkedIn URL
    (no trailing slash), else their name; lowercased. None for a contact with
    none of these. Mirrored in SQL by migration 20261019_0927_backfill_lace_contacts:
    keep the two in step."""
    key = _clean(contact.email) or _clean(contact.linkedin).rstrip("/") or _clean(contact.name)
    return key.lower()[:320] or None


async def sync(db: AsyncSession, lace_id: uuid.UUID, account_id: uuid.UUID, contacts: Iterable[ContactRecord],
               source: ContactSource) -> None:
    """Upsert an account's people. A person already on file keeps what they
    had where the new sighting is blank, and moves to this account."""
    now = datetime.now(UTC)
    for contact in contacts:
        key = contact_key(contact)
        if key is None:
            continue
        values = {"name": _clean(contact.name)[:200] or None, "title": _clean(contact.title)[:200] or None,
                  "email": _clean(contact.email)[:320] or None, "linkedin": _clean(contact.linkedin) or None,
                  # Again here: a record built with model_copy skipped the schema's check.
                  **{p: social_profile_url(p, getattr(contact, p)) for p in PERSON_SOCIALS}}
        stmt = insert(LaceContact).values(id=uuid.uuid4(), lace_id=lace_id, account_id=account_id, key=key,
                                          source=source, last_seen_at=now, **values)
        await db.execute(stmt.on_conflict_do_update(
            constraint="uq_lace_contacts_lace_id_key",
            set_={**{c: func.coalesce(stmt.excluded[c], getattr(LaceContact, c)) for c in values},
                  "account_id": stmt.excluded.account_id, "last_seen_at": now},
        ))


async def approved_keys(db: AsyncSession, account_ids: Iterable[uuid.UUID]) -> dict[uuid.UUID, set[str]]:
    """Per account, the keys of the people the founder cleared for outreach."""
    rows = await db.execute(select(LaceContact.account_id, LaceContact.key).where(
        LaceContact.account_id.in_(list(account_ids)), LaceContact.approved_at.is_not(None)))
    keys: dict[uuid.UUID, set[str]] = {}
    for account_id, key in rows.all():
        keys.setdefault(account_id, set()).add(key)
    return keys


async def set_approved(db: AsyncSession, lace_id: uuid.UUID, contact_id: uuid.UUID, approved: bool) -> LaceContact:
    """404 for a contact that is not this Lace's."""
    contact = await db.scalar(select(LaceContact).where(LaceContact.id == contact_id, LaceContact.lace_id == lace_id))
    if contact is None:
        raise NotFoundError("Contact not found")
    contact.approved_at = datetime.now(UTC) if approved else None
    await db.commit()
    return contact


async def person_to_draft(db: AsyncSession, lace_id: uuid.UUID, contact_id: uuid.UUID,
                          channel: OutreachChannel) -> tuple[uuid.UUID, dict]:
    """The account and the person to write to on `channel`, approving them:
    asking for a draft to someone is clearing them for it. NotFoundError for
    another Lace's contact; InvalidInputError when they can't be reached there."""
    contact = await db.scalar(select(LaceContact).where(LaceContact.id == contact_id, LaceContact.lace_id == lace_id))
    if contact is None:
        raise NotFoundError("Contact not found")
    address = getattr(contact, channel)
    if not address:
        raise InvalidInputError(f"There's no {_ADDRESS_LABEL[channel]} for this person.")
    if contact.approved_at is None:
        contact.approved_at = datetime.now(UTC)
        await db.commit()
    return contact.account_id, {"channel": channel, "name": contact.name, "title": contact.title, "address": address}


async def approve_account(db: AsyncSession, lace_id: uuid.UUID, account_id: uuid.UUID) -> int:
    """Clear everyone at one account for outreach. Returns how many were waiting."""
    result = await db.execute(update(LaceContact).where(
        LaceContact.lace_id == lace_id, LaceContact.account_id == account_id, LaceContact.approved_at.is_(None),
    ).values(approved_at=datetime.now(UTC)))
    await db.commit()
    return result.rowcount or 0


async def list_for_lace(db: AsyncSession, lace_id: uuid.UUID, limit: int) -> list[tuple[LaceContact, LaceAccount]]:
    """The people at the Lace's target accounts (not dismissed ones), by
    account, then name."""
    rows = await db.execute(
        select(LaceContact, LaceAccount).join(LaceAccount, LaceAccount.id == LaceContact.account_id)
        .where(LaceContact.lace_id == lace_id, LaceAccount.team(), LaceAccount.status == "target")
        .order_by(LaceAccount.name, LaceContact.name.nulls_last()).limit(limit)
    )
    return [(contact, account) for contact, account in rows.all()]


async def add_named(db: AsyncSession, lace_id: uuid.UUID, account: LaceAccount, person: NewContact) -> LaceContact:
    """Add a person the founder named at `account`, approved for outreach,
    and keep them on the account's record too. A person already on file is
    updated and moved there."""
    found = ContactRecord(name=person.name, title=person.title, email=person.email, linkedin=person.linkedin,
                          **{p: getattr(person, p) for p in PERSON_SOCIALS})
    key = contact_key(found)
    record = dict(account.record or {})
    people = [c for c in record.get("key_contacts") or [] if contact_key(ContactRecord.model_validate(c)) != key]
    account.record = {**record, "key_contacts": [*people, found.model_dump(mode="json", exclude_none=True)]}
    await sync(db, lace_id, account.id, [found], "founder")
    contact = await db.scalar(select(LaceContact).where(LaceContact.lace_id == lace_id, LaceContact.key == key))
    contact.approved_at = datetime.now(UTC)
    await db.commit()
    return contact


async def remove(db: AsyncSession, lace_id: uuid.UUID, ids: Iterable[uuid.UUID]) -> list[tuple[uuid.UUID, str]]:
    """Delete these people (only this Lace's), and drop them from their
    account's record. Returns (id, name) of each one removed."""
    rows = (await db.execute(delete(LaceContact).where(LaceContact.lace_id == lace_id, LaceContact.id.in_(list(ids)))
                             .returning(LaceContact.id, LaceContact.key, LaceContact.name, LaceContact.account_id))).all()
    for account_id, keys in _keys_by_account(rows).items():
        account = await db.get(LaceAccount, account_id)
        if account is not None:
            record = dict(account.record or {})
            record["key_contacts"] = [c for c in record.get("key_contacts") or []
                                      if contact_key(ContactRecord.model_validate(c)) not in keys]
            account.record = record
    await db.commit()
    return [(row.id, row.name or row.key) for row in rows]


def _keys_by_account(rows) -> dict[uuid.UUID, set[str]]:
    keys: dict[uuid.UUID, set[str]] = {}
    for row in rows:
        keys.setdefault(row.account_id, set()).add(row.key)
    return keys
