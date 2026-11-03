"""A Lace's Store while the team sets it up: whether its tab shows, its name
and address, what it sells, and who shares in each sale.

The rules (the daily budget and the payees) can be changed freely until the
Store goes live. After that they are the founder's signed policy, so only a
new signature changes them; nothing here, and nothing the Lace does, can."""

import re
import uuid
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from agents.schemas.store import FULL_SHARE_BPS, STORE_SLUG_MAX_LEN, PayeeRoute
from backend.app.database.lace_models import Lace
from backend.app.database.store_models import LaceStore, StoreOffer, StorePayee
from backend.app.services.errors import ConflictError, InvalidInputError, NotFoundError
from config import settings

# The most offers and payees one Store holds.
MAX_OFFERS = 50
MAX_PAYEES = 10
_NOT_SLUG = re.compile(r"[^a-z0-9]+")
RULES_ARE_SIGNED = "The Store is live, so its rules change only with a new signature from its owner."


def slug_for(name: str) -> str:
    """A storefront address from a name: lowercase letters, digits and dashes."""
    slug = _NOT_SLUG.sub("-", name.lower()).strip("-")[:STORE_SLUG_MAX_LEN - 7].strip("-")
    return slug if len(slug) >= 3 else f"store-{slug}".strip("-")


async def _free_slug(db: AsyncSession, base: str) -> str:
    taken = set((await db.scalars(select(LaceStore.slug).where(LaceStore.slug.like(f"{base}%")))).all())
    if base not in taken:
        return base
    return next(f"{base}-{n}" for n in range(2, len(taken) + 3) if f"{base}-{n}" not in taken)


async def get_store(db: AsyncSession, lace_id: uuid.UUID) -> LaceStore | None:
    return await db.scalar(select(LaceStore).where(LaceStore.lace_id == lace_id))


async def _require(db: AsyncSession, lace_id: uuid.UUID) -> LaceStore:
    store = await get_store(db, lace_id)
    if store is None:
        raise NotFoundError("This Lace has no Store yet.")
    return store


async def set_shown(db: AsyncSession, lace: Lace, shown: bool) -> LaceStore:
    """Show or hide the Store's tab. The first time it's shown, the Store is
    made, named after the startup and not yet selling."""
    store = await get_store(db, lace.id)
    if store is None:
        name = lace.startup_name or lace.name
        store = LaceStore(lace_id=lace.id, name=name[:120], slug=await _free_slug(db, slug_for(name)),
                          settlement_asset=settings.store_settlement_asset,
                          daily_budget_usd=Decimal(settings.store_default_daily_budget_usd))
        db.add(store)
    store.shown = shown
    await db.flush()
    return store


async def update_details(db: AsyncSession, lace_id: uuid.UUID, *, name: str | None = None,
                         tagline: str | None = None, slug: str | None = None,
                         daily_budget_usd: Decimal | None = None) -> LaceStore:
    store = await _require(db, lace_id)
    if daily_budget_usd is not None and daily_budget_usd != store.daily_budget_usd:
        if store.status != "setup":
            raise ConflictError(RULES_ARE_SIGNED)
        store.daily_budget_usd = daily_budget_usd
    if slug is not None and slug != store.slug:
        if store.status != "setup":
            raise ConflictError("A live Store keeps its address, so links to it keep working.")
        if await db.scalar(select(func.count()).where(LaceStore.slug == slug)):
            raise ConflictError("That address is taken.")
        store.slug = slug
    if name is not None:
        store.name = name
    if tagline is not None:
        store.tagline = tagline
    await db.flush()
    return store


# -- Offers --

async def list_offers(db: AsyncSession, lace_id: uuid.UUID) -> list[StoreOffer]:
    store = await _require(db, lace_id)
    return list((await db.scalars(select(StoreOffer).where(StoreOffer.store_id == store.id)
                                  .order_by(StoreOffer.status, StoreOffer.position, StoreOffer.created_at)
                                  .limit(MAX_OFFERS))).all())


def _check_delivery(delivery: str, delivery_url: str | None) -> None:
    if delivery == "link" and not delivery_url:
        raise InvalidInputError("A link offer needs the link the buyer receives.")


async def add_offer(db: AsyncSession, lace_id: uuid.UUID, fields: dict, created_by: uuid.UUID) -> StoreOffer:
    store = await _require(db, lace_id)
    count = await db.scalar(select(func.count()).where(StoreOffer.store_id == store.id,
                                                       StoreOffer.status != "archived"))
    if count >= MAX_OFFERS:
        raise ConflictError(f"A Store holds at most {MAX_OFFERS} offers. Archive one first.")
    _check_delivery(fields["delivery"], fields.get("delivery_url"))
    offer = StoreOffer(store_id=store.id, position=count, created_by=created_by, **fields)
    db.add(offer)
    await db.flush()
    return offer


async def update_offer(db: AsyncSession, lace_id: uuid.UUID, offer_id: uuid.UUID, fields: dict) -> StoreOffer:
    store = await _require(db, lace_id)
    offer = await db.get(StoreOffer, offer_id)
    if offer is None or offer.store_id != store.id:
        raise NotFoundError("No such offer.")
    for key, value in fields.items():
        setattr(offer, key, value)
    _check_delivery(offer.delivery, offer.delivery_url)
    await db.flush()
    return offer


# -- Payees: the revenue split --

async def list_payees(db: AsyncSession, lace_id: uuid.UUID) -> list[StorePayee]:
    store = await _require(db, lace_id)
    return list((await db.scalars(select(StorePayee).where(StorePayee.store_id == store.id)
                                  .order_by(StorePayee.share_bps.desc(), StorePayee.created_at))).all())


def _destination(route: PayeeRoute, chain: str | None, address: str) -> tuple:
    return route, chain if route == "withdraw" else None, address.lower() if route == "withdraw" else address


async def set_payees(db: AsyncSession, lace_id: uuid.UUID, payees: list[dict]) -> list[StorePayee]:
    """Replace the split. Shares are basis points of each sale; what no payee
    takes stays in the Store's wallet."""
    store = await _require(db, lace_id)
    if store.status != "setup":
        raise ConflictError(RULES_ARE_SIGNED)
    if len(payees) > MAX_PAYEES:
        raise InvalidInputError(f"A sale splits between at most {MAX_PAYEES} payees.")
    if sum(p["share_bps"] for p in payees) > FULL_SHARE_BPS:
        raise InvalidInputError("The shares add up to more than the whole sale.")
    destinations = [_destination(p["route"], p.get("chain"), p["address"]) for p in payees]
    if len(set(destinations)) != len(destinations):
        raise InvalidInputError("Each payee needs its own destination.")
    for old in await list_payees(db, lace_id):
        await db.delete(old)
    await db.flush()
    rows = [StorePayee(store_id=store.id, label=p["label"], route=p["route"], chain=chain, address=address,
                       memo=p.get("memo") if p["route"] == "withdraw" else None, share_bps=p["share_bps"])
            for p, (_, chain, address) in zip(payees, destinations)]
    db.add_all(rows)
    await db.flush()
    return rows
