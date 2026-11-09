"""Earlier mail with a lead, in the founder's own mailbox (Gmail): checked
before a first email is drafted. A lead the founder has written to, or heard
from, before was never cold: it starts warm (lead_temperature.on_history),
and its draft is written as a follow-on, not a cold introduction.

Only the Lace owner's own Gmail is searched, and only in their runs (see
DbLaceApps._personal); otherwise there is simply no history to use.
"""

import asyncio
import uuid
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from agents.lace.apps import AppError
from agents.schemas.accounts import AccountRecord
from backend.app.database.connect import AsyncSessionLocal
from backend.app.database.lace_models import LaceAccount
from backend.app.services import lead_temperature
from backend.app.services.crm_match import site_domain
from backend.app.services.lace_apps import DbLaceApps
from config import settings
from utils.log import logger

# The earlier mails named in the drafting note: enough to set the tone.
NOTE_MAILS = 3


def _domain(record: AccountRecord) -> str | None:
    return site_domain(record.website) or (record.domain or "").strip().lower() or None


async def _search(apps: DbLaceApps, domain: str) -> list[dict]:
    try:
        return await apps.email_search(f"(from:{domain} OR to:{domain})", settings.email_history_days) or []
    except AppError as exc:
        logger.info("No mail history read for %s: %s", domain, exc)
        return []


async def earlier_mail(lace_id: uuid.UUID, reader_id: uuid.UUID,
                       accounts: list[tuple[uuid.UUID, AccountRecord]]) -> dict[uuid.UUID, list[dict]]:
    """account id -> the founder's earlier mail with people at its domain,
    newest first; accounts with none are left out."""
    apps = DbLaceApps(AsyncSessionLocal, lace_id, reader_id)
    domains = [(account_id, d) for account_id, record in accounts if (d := _domain(record))]
    found = await asyncio.gather(*(_search(apps, d) for _, d in domains))
    return {account_id: mails for (account_id, _), mails in zip(domains, found, strict=True) if mails}


def follow_on_note(company: str, mails: list[dict]) -> str:
    """What the writer is told: this isn't a first contact."""
    shown = "; ".join(f"\"{m.get('subject') or '(no subject)'}\"" for m in mails[:NOTE_MAILS])
    return (f"The founder has emailed people at {company} before ({len(mails)} earlier "
            f"{'email' if len(mails) == 1 else 'emails'}, e.g. {shown}). Write a warm follow-on that picks up "
            "from that contact, not a cold introduction, and never pretend it's the first time.")


async def warm(db: AsyncSession, history: dict[uuid.UUID, list[dict]], now: datetime | None = None) -> None:
    """Each lead with earlier mail starts warm. The caller commits."""
    now = now or datetime.now(UTC)
    for account_id, mails in history.items():
        if (account := await db.get(LaceAccount, account_id)) is not None:
            await lead_temperature.on_history(db, account, len(mails), now)
