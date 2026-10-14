"""A workspace's specialist team and each specialist's own research, as the
agents read them. Outreach and chat both speak through these specialists:
the GTM specialist owns outreach and consults the others; chat routes each
question to the specialist whose research answers it.
"""

import json
import uuid
from dataclasses import dataclass
from urllib.parse import urlparse

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.database import models

# Per-domain research budget: enough for depth, small enough that a
# specialist's whole slice fits beside the conversation in one call.
DOMAIN_CHARS = 16_000
_COMPETITORS = 12
_ACCOUNTS = 10


@dataclass
class SpecialistContext:
    offer_name: str
    # The offer in a few lines: what every specialist shares.
    offer: str
    # domain -> {name, role, description, affiliation}; domains are "gtm",
    # "product" or "service", "market", "competition".
    team: dict[str, dict]
    # domain -> that specialist's research, as text.
    research: dict[str, str]
    # The company selling the offer, when discovery found one.
    company_name: str = ""


def block(title: str, value, limit: int = DOMAIN_CHARS // 3) -> str:
    """One titled, clipped section of a prompt; empty values drop out."""
    if not value:
        return ""
    text = value if isinstance(value, str) else json.dumps(value, ensure_ascii=False, default=str)
    return f"### {title}\n{text[:limit]}\n"


def _join(*parts: str) -> str:
    return "\n".join(p for p in parts if p)[:DOMAIN_CHARS] or "(no research on file yet)"


def seller_name(offer: dict) -> str:
    """Who is selling: the company discovery found, else the offer's website
    host ("shangalabs.com"), which the writer turns into the spoken name."""
    if offer.get("company_name"):
        return offer["company_name"]
    host = urlparse(offer.get("website_url") or "").hostname or ""
    return host.removeprefix("www.")


def _offer_text(offer: dict) -> str:
    keys = ("offer_name", "company_name", "website_url", "offer_description", "problem_solved", "how_it_works",
            "features", "service_uniqueness", "target_geo")
    return block("OFFER", {k: offer.get(k) for k in keys if offer.get(k)}, DOMAIN_CHARS)


async def load(db: AsyncSession, workspace_id: uuid.UUID) -> SpecialistContext:
    insights = await db.scalar(
        select(models.ProductProfile.insights).where(models.ProductProfile.workspace_id == workspace_id)
    ) or {}
    offer = insights.get("offer_snapshot") or {}
    competitors = (await db.execute(
        select(models.Competitor).where(models.Competitor.workspace_id == workspace_id)
        .order_by(models.Competitor.first_seen_at.desc()).limit(_COMPETITORS)
    )).scalars().all()
    accounts = (await db.execute(
        select(models.Account).where(models.Account.workspace_id == workspace_id)
        .order_by(models.Account.selected.desc(), models.Account.score.desc().nulls_last()).limit(_ACCOUNTS)
    )).scalars().all()

    research = insights.get("research") or {}
    offer_text = _offer_text(offer)
    product = _join(
        offer_text, block("DOMAIN AND POSITIONING UNDERSTANDING", insights.get("domain_understanding")),
        block("MY RESEARCH NOTES (with sources)", research.get("offer"), DOMAIN_CHARS // 2),
    )
    market = _join(
        block("PRODUCT-MARKET FIT", insights.get("market_fit_understanding")),
        block("MARKET DATA (buyers, demand, pricing norms, channels, barriers)", insights.get("market_data")),
        block("MY RESEARCH NOTES (with sources)", research.get("market"), DOMAIN_CHARS // 2),
    )
    competition = _join(
        block("MY RESEARCH NOTES (with sources)", research.get("competition"), DOMAIN_CHARS // 3),
        block("OFFER VS THE CATEGORY STANDARD (strengths, weaknesses, opportunities, differentiators)",
              insights.get("competition_data")),
        block("COMPETITOR ARCHETYPES", insights.get("ideal_competitor_profile")),
        block("TRACKED COMPETITORS", [
            {"name": c.name, "website": c.website, "positioning": c.positioning, "pricing": c.pricing,
             "target_customers": c.target_customers, "strengths": (c.strengths or [])[:3],
             "weaknesses": (c.weaknesses or [])[:3], "pain_signals": (c.pain_signals or [])[:3]}
            for c in competitors
        ], DOMAIN_CHARS // 2),
    )
    gtm = _join(
        block("IDEAL CUSTOMER PROFILE (segments, titles, channels, messaging angles, beachhead)", insights.get("icp"),
              DOMAIN_CHARS // 3),
        block("MY GTM NOTES", research.get("icp"), DOMAIN_CHARS // 3),
        block("TARGET ACCOUNTS", [
            {"name": a.name, "summary": a.summary, "industry": a.industry, "selected": a.selected,
             "why_reach_out": (a.why_reach_out or [])[:2]}
            for a in accounts
        ]),
    )
    team = {s["domain"]: s for s in insights.get("specialists") or [] if isinstance(s, dict) and s.get("domain")}
    own = "service" if "service" in team else "product"
    return SpecialistContext(
        offer_name=offer.get("offer_name") or "",
        offer=offer_text or "(no offer on file)",
        team=team,
        research={own: product, "product": product, "market": market, "competition": competition, "gtm": gtm},
        company_name=seller_name(offer),
    )
