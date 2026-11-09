"""Which of a Lace's leads are already in the founder's CRM, from its copy of
it (lace_crm_records, crm_sync): matched by the company's domain, its name, or
the email of someone there. A match sets the lead's crm_status and crm_stage,
so it is shown as "in your CRM", and moves its temperature (a customer there
is a customer here; an open deal is at least warm). A lead the CRM no longer
has loses its label but keeps its temperature."""

import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from agents.helpers import name_key
from backend.app.database.lace_models import LaceAccount, LaceContact, LaceCrmRecord
from backend.app.services import lead_temperature
from backend.app.services.crm import STATUS_RANK
from backend.app.services.competitors import domain_key


# Mail providers anyone can sign up to: an address there says nothing about
# which company the person is at.
FREE_MAIL_DOMAINS = frozenset({
    "gmail.com", "googlemail.com", "yahoo.com", "ymail.com", "outlook.com", "hotmail.com", "live.com", "msn.com",
    "icloud.com", "me.com", "aol.com", "proton.me", "protonmail.com", "gmx.com", "zoho.com", "yandex.com",
})


def site_domain(website: str | None) -> str | None:
    """A website (with or without its scheme) as the domain it stands for."""
    if not website or not website.strip():
        return None
    site = website.strip()
    return domain_key(site if "://" in site else f"https://{site}") or None


def email_domain(email: str | None) -> str | None:
    """The company domain an address belongs to; None for free mail."""
    if not email or "@" not in email:
        return None
    domain = email.rsplit("@", 1)[1].strip().lower()
    return None if domain in FREE_MAIL_DOMAINS else domain or None


def _domains(account: LaceAccount) -> set[str]:
    """The domains a lead goes by: its key (a domain, unless it has no site)
    and its website's."""
    return {d for d in (site_domain(account.website), account.key if "." in account.key else None) if d}


async def match_accounts(db: AsyncSession, lace_id: uuid.UUID, account_ids: list[uuid.UUID] | None = None,
                         now: datetime | None = None) -> int:
    """Match the Lace's leads (or only these) against its CRM copy. The
    caller commits. Returns how many are in the CRM."""
    now = now or datetime.now(UTC)
    query = select(LaceAccount).where(LaceAccount.lace_id == lace_id)
    if account_ids is not None:
        query = query.where(LaceAccount.id.in_(account_ids))
    accounts = list((await db.scalars(query)).all())
    if not accounts:
        return 0
    records = (await db.scalars(select(LaceCrmRecord).where(LaceCrmRecord.lace_id == lace_id))).all()
    by_domain: dict[str, list[LaceCrmRecord]] = {}
    by_name: dict[str, list[LaceCrmRecord]] = {}
    by_email: dict[str, list[LaceCrmRecord]] = {}
    for r in records:
        for index, key in ((by_domain, r.domain), (by_name, r.company_key), (by_email, r.email)):
            if key:
                index.setdefault(key, []).append(r)
    emails: dict[uuid.UUID, set[str]] = {}
    for account_id, email in (await db.execute(select(LaceContact.account_id, LaceContact.email).where(
            LaceContact.account_id.in_([a.id for a in accounts]), LaceContact.email.is_not(None)))).all():
        emails.setdefault(account_id, set()).add(email.strip().lower())

    matched = 0
    for account in accounts:
        found = [r for d in _domains(account) for r in by_domain.get(d, [])]
        found += by_name.get(name_key(account.name), [])
        found += [r for e in emails.get(account.id, ()) for r in by_email.get(e, [])]
        if not found:
            account.crm_status = account.crm_stage = None
            continue
        best = max(found, key=lambda r: STATUS_RANK[r.status])
        account.crm_status, account.crm_stage = best.status, best.stage
        await lead_temperature.on_crm(db, account, best.status, best.stage, now)
        matched += 1
    return matched
