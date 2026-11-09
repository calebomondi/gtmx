"""Which of the startup's real customers a Lace still has to learn about:
CRM customers (lace_crm_records) and leads the founder marked as customers,
each with a website, less those already on file as a customer fact from that
site. The customer job (runs/customer_jobs.py) reads them, and the ideal
customer profile is then reworked from them."""

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.database.lace_models import LaceAccount, LaceCrmRecord, LaceFact
from backend.app.services.crm_match import site_domain

# What the ideal customer profile is reworked with, once customers are learned.
ICP_GUIDANCE = ("Base the ideal customer profile on the startup's real customers (the facts under customers): "
                "what they have in common (industry, size, location, need). Where the website's picture differs, "
                "the real customers win.")


async def to_learn(db: AsyncSession, lace_id: uuid.UUID, limit: int) -> list[tuple[str, str]]:
    """(name, website) of customers not learned yet, CRM customers first,
    one per domain, bounded."""
    learned = {site_domain(url) for url in (await db.scalars(select(LaceFact.source_url).where(
        LaceFact.lace_id == lace_id, LaceFact.topic == "customers", LaceFact.superseded_by_id.is_(None),
        LaceFact.retracted_at.is_(None), LaceFact.source_url.is_not(None)))).all()}
    found: list[tuple[str, str]] = []
    seen: set[str] = set()
    crm = (await db.execute(select(LaceCrmRecord.company, LaceCrmRecord.domain).where(
        LaceCrmRecord.lace_id == lace_id, LaceCrmRecord.kind == "company", LaceCrmRecord.status == "customer",
        LaceCrmRecord.domain.is_not(None)))).all()
    marked = (await db.execute(select(LaceAccount.name, LaceAccount.website).where(
        LaceAccount.lace_id == lace_id, LaceAccount.temperature == "customer",
        LaceAccount.website.is_not(None)))).all()
    for name, site in [*crm, *marked]:
        domain = site_domain(site)
        if not domain or domain in learned or domain in seen:
            continue
        seen.add(domain)
        found.append((name or domain, site if "://" in site else f"https://{site}"))
        if len(found) >= limit:
            break
    return found
