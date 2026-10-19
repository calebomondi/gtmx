"""The people at a Lace's target accounts, as rows the founder's Contacts
can list, filter and sort. Synced from an account's record whenever the
record's people are saved: by an account search or a contact search."""

import uuid
from collections.abc import Iterable
from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from agents.schemas.accounts import ContactRecord
from agents.schemas.lace import ContactSource
from backend.app.database.lace_models import LaceAccount, LaceContact


def _clean(value: str | None) -> str:
    return (value or "").strip()


def contact_key(contact: ContactRecord) -> str | None:
    """Who the contact is, for dedup: their email, else their LinkedIn URL
    (no trailing slash), else their name; lowercased. None for a contact with
    none of these. The contacts backfill migration mirrors this in SQL: keep them in step."""
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
                  "email": _clean(contact.email)[:320] or None, "linkedin": _clean(contact.linkedin) or None}
        stmt = insert(LaceContact).values(id=uuid.uuid4(), lace_id=lace_id, account_id=account_id, key=key,
                                          source=source, last_seen_at=now, **values)
        await db.execute(stmt.on_conflict_do_update(
            constraint="uq_lace_contacts_lace_id_key",
            set_={**{c: func.coalesce(stmt.excluded[c], getattr(LaceContact, c)) for c in values},
                  "account_id": stmt.excluded.account_id, "last_seen_at": now},
        ))


async def list_for_lace(db: AsyncSession, lace_id: uuid.UUID, limit: int) -> list[tuple[LaceContact, LaceAccount]]:
    """The people at the Lace's target accounts (not dismissed ones), by
    account, then name."""
    rows = await db.execute(
        select(LaceContact, LaceAccount).join(LaceAccount, LaceAccount.id == LaceContact.account_id)
        .where(LaceContact.lace_id == lace_id, LaceAccount.status == "target")
        .order_by(LaceAccount.name, LaceContact.name.nulls_last()).limit(limit)
    )
    return [(contact, account) for contact, account in rows.all()]
