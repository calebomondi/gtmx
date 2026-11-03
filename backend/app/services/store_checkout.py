"""Buying from a Store: the public storefront, placing an order, and the
watcher that sees each payment arrive.

A buyer picks an offer and a stablecoin to pay with. The Store's wallet
gives a one-time deposit address quoted for exactly the price in that coin,
credited as the Store's settlement asset. A late, short or failed payment
is refunded by NEAR Intents into the Store's own wallet, never lost, and
the order says so."""

import secrets
import time
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.database.connect import AsyncSessionLocal
from backend.app.database.store_models import LaceStore, StoreLedgerEntry, StoreOffer, StoreOrder
from backend.app.services import lace_activity, store_signing
from backend.app.services.errors import ConflictError, InvalidInputError, NotFoundError, RateLimitedError
from config import settings
from data_sources.near.agent_api import AgentApiError, Operation, Token, new_idempotency_key
from utils.log import logger

_RATE_WINDOW = timedelta(hours=1)
# Orders the watcher reads per round; older unpaid ones wait for the next.
WATCH_BATCH = 100
_tokens: tuple[float, dict[str, Token]] = (0.0, {})


async def pay_options() -> list[Token]:
    """The coins a buyer may pay with, as NEAR Intents lists them now."""
    global _tokens
    read_at, by_id = _tokens
    if time.monotonic() - read_at > settings.store_tokens_cache_s or not by_id:
        try:
            by_id = {t.asset_id: t for t in await store_signing.agent_api().tokens()}
        except AgentApiError as exc:
            if not by_id:
                raise ConflictError("Payment options can't be read right now. Try again in a minute.") from exc
            logger.warning("Token list not refreshed, using the last one: %s", exc.code)
        else:
            _tokens = (time.monotonic(), by_id)
    return [by_id[a] for a in settings.store_pay_assets if a in by_id]


def atomic_price(price_cents: int, decimals: int) -> Decimal:
    """A USD price as atomic units of a dollar stablecoin: $29.50 in a
    6-decimal coin is 29_500_000."""
    if decimals < 2:
        raise InvalidInputError("That coin can't express cents.")
    return Decimal(price_cents) * Decimal(10) ** (decimals - 2)


async def _open_store(db: AsyncSession, slug: str) -> LaceStore:
    store = await db.scalar(select(LaceStore).where(LaceStore.slug == slug))
    # A Store still being set up isn't there for the public yet.
    if store is None or store.status == "setup":
        raise NotFoundError("No such store.")
    return store


@dataclass(frozen=True)
class Storefront:
    store: LaceStore
    offers: list[StoreOffer]
    pay_with: list[Token]

    @property
    def selling(self) -> bool:
        return self.store.status == "live" and self.store.frozen_at is None


async def storefront(db: AsyncSession, slug: str) -> Storefront:
    store = await _open_store(db, slug)
    offers = list((await db.scalars(select(StoreOffer).where(StoreOffer.store_id == store.id,
                                                             StoreOffer.status == "active")
                                    .order_by(StoreOffer.position, StoreOffer.created_at))).all())
    return Storefront(store=store, offers=offers, pay_with=await pay_options())


async def _check_rate(db: AsyncSession, ip_hash: str | None) -> None:
    if ip_hash is None:
        return
    recent = await db.scalar(select(func.count()).where(StoreOrder.ip_hash == ip_hash,
                                                        StoreOrder.created_at >= datetime.now(UTC) - _RATE_WINDOW))
    if (recent or 0) >= settings.store_orders_per_ip_per_hour:
        raise RateLimitedError("Too many orders from this network. Try again in an hour.",
                               retry_after_s=int(_RATE_WINDOW.total_seconds()))


def _parse_time(value: str | None) -> datetime | None:
    return datetime.fromisoformat(value.replace("Z", "+00:00")) if value else None


async def place_order(db: AsyncSession, slug: str, offer_id: uuid.UUID, buyer_email: str, pay_asset: str,
                      ip_hash: str | None) -> StoreOrder:
    """An order and the one-time address its buyer pays into."""
    store = await _open_store(db, slug)
    if store.status != "live" or store.frozen_at is not None:
        raise ConflictError("This store isn't taking orders right now.")
    offer = await db.get(StoreOffer, offer_id)
    if offer is None or offer.store_id != store.id or offer.status != "active":
        raise NotFoundError("That offer isn't on sale.")
    coin = next((t for t in await pay_options() if t.asset_id == pay_asset), None)
    if coin is None:
        raise InvalidInputError("This store doesn't take that coin.")
    await _check_rate(db, ip_hash)
    order = StoreOrder(store_id=store.id, offer_id=offer.id, public_token=secrets.token_urlsafe(24),
                       buyer_email=buyer_email, ip_hash=ip_hash, price_cents=offer.price_cents, pay_asset=pay_asset,
                       pay_amount_raw=atomic_price(offer.price_cents, coin.decimals),
                       deposit_idempotency_key=new_idempotency_key(f"order:{store.id}"))
    db.add(order)
    # Saved with its key first, so a crash before the address comes back
    # can ask for the same address again rather than a second one.
    await db.commit()
    try:
        op = await store_signing.agent_api().deposit(
            store.agent_id, origin_asset=pay_asset, amount=str(order.pay_amount_raw),
            destination_asset=store.settlement_asset, idempotency_key=order.deposit_idempotency_key)
    except AgentApiError as exc:
        order.status, order.failure_code = "failed", exc.code
        await db.commit()
        logger.warning("Store %s: no deposit address for order %s: %s", store.id, order.id, exc.code)
        raise ConflictError("The payment address couldn't be made. Try again in a minute.") from exc
    details = op.details
    if not details.get("deposit_address"):
        order.status, order.failure_code = "failed", "deposit_address_missing"
        await db.commit()
        raise ConflictError("The payment address couldn't be made. Try again in a minute.")
    order.deposit_correlation_id = op.correlation_id
    order.deposit_address, order.deposit_memo = details["deposit_address"], details.get("memo")
    order.deposit_expires_at = _parse_time(details.get("expires_at"))
    await db.commit()
    return order


@dataclass(frozen=True)
class OrderView:
    order: StoreOrder
    offer: StoreOffer
    store: LaceStore


async def order_view(db: AsyncSession, public_token: str) -> OrderView:
    order = await db.scalar(select(StoreOrder).where(StoreOrder.public_token == public_token))
    if order is None:
        raise NotFoundError("No such order.")
    return OrderView(order=order, offer=await db.get(StoreOffer, order.offer_id),
                     store=await db.get(LaceStore, order.store_id))


# -- The watcher --

_FINISHED = {"REFUNDED": "refunded", "FAILED": "failed"}


async def _record_sale(db: AsyncSession, store: LaceStore, order: StoreOrder, offer: StoreOffer) -> None:
    db.add(StoreLedgerEntry(store_id=store.id, order_id=order.id, kind="sale", status="done", asset=order.pay_asset,
                            amount_raw=order.pay_amount_raw, amount_usd=Decimal(order.price_cents) / 100,
                            correlation_id=order.deposit_correlation_id, settled_at=order.paid_at))
    await lace_activity.add(db, store.lace_id, "store_sale", f"Sold {offer.title} for ${order.price_cents / 100:,.2f}",
                            ref=("store_order", order.id))


async def settle_payment(db: AsyncSession, order: StoreOrder, op: Operation) -> None:
    """Move an unpaid order on from its deposit's status."""
    order.checked_at = datetime.now(UTC)
    if not op.final:
        return
    store = await db.get(LaceStore, order.store_id)
    offer = await db.get(StoreOffer, order.offer_id)
    if op.status == "SUCCESS":
        order.status, order.paid_at = "paid", datetime.now(UTC)
        # Paid in the settlement asset itself, nothing was converted.
        order.credited_raw = order.pay_amount_raw if order.pay_asset == store.settlement_asset else None
        await _record_sale(db, store, order, offer)
        return
    order.failure_code = op.failure_code or op.details.get("failure_reason") or op.status.lower()
    order.status = "expired" if op.failure_code == "deposit_expired" else _FINISHED.get(op.status, "failed")
    if order.status == "refunded":
        await lace_activity.add(
            db, store.lace_id, "store_status", f"A payment for {offer.title} was refunded",
            summary="NEAR Intents couldn't credit it as sent (wrong amount, late, or not convertible), so it went "
                    "back into the Store's own wallet. The buyer may write to you about it.",
            ref=("store_order", order.id))


async def watch_orders() -> int:
    """Read the deposit of each unpaid order, oldest checked first. Returns
    how many were paid."""
    async with AsyncSessionLocal() as db:
        orders = list((await db.scalars(
            select(StoreOrder).where(StoreOrder.status == "awaiting_payment",
                                     StoreOrder.deposit_correlation_id.is_not(None))
            .order_by(StoreOrder.checked_at.asc().nulls_first()).limit(WATCH_BATCH))).all())
        if not orders:
            return 0
        api, paid = store_signing.agent_api(), 0
        for order in orders:
            try:
                op = await api.status(order.deposit_correlation_id)
            except AgentApiError as exc:
                logger.warning("Order %s: deposit status not read: %s", order.id, exc.code)
                continue
            await settle_payment(db, order, op)
            paid += order.status == "paid"
            await db.commit()
        return paid
