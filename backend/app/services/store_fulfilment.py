"""After a sale: the buyer gets what they paid for, and each payee gets their
share, both on their own as the watcher goes round.

Delivery is an email: the offer's private link and note, or for a service,
what happens next (and the team is told to do it). Payouts go out of the
Store's wallet under its grant, one at a time per wallet as NEAR Intents
requires, each written to the ledger as pending with its idempotency key
before it's sent, so a crash or retry never pays twice. The wallet's
signed policy refuses any destination but the payees and anything past the
daily cap, whatever this code asks."""

from datetime import UTC, datetime
from decimal import ROUND_DOWN, Decimal
from html import escape

from sqlalchemy import exists, select
from sqlalchemy.ext.asyncio import AsyncSession

from agents.schemas.store import FULL_SHARE_BPS
from backend.app.database.connect import AsyncSessionLocal
from backend.app.database.store_models import LaceStore, StoreLedgerEntry, StoreOffer, StoreOrder, StorePayee
from backend.app.services import email, lace_activity, store_signing
from backend.app.services.errors import ConflictError
from backend.app.services.store_checkout import atomic_price, pay_options
from config import settings
from data_sources.near.agent_api import AgentApi, AgentApiError, new_idempotency_key
from utils.log import logger

# Orders delivered, or payouts sent or read, per round.
FULFIL_BATCH = 50
# Refusals that pass with time or the owner's action: the payout stays
# pending and is sent again, under the same key, on a later round.
WAIT_CODES = frozenset({"wallet_busy", "spend_budget_exceeded", "policy_limit_exceeded",
                        "policy_action_limit_exceeded", "policy_schedule_denied", "wallet_frozen", "policy_not_ready"})
SETTLEMENT_DECIMALS = 6


def order_url(order: StoreOrder, store: LaceStore) -> str:
    return f"{settings.frontend_base_url.rstrip('/')}/s/{store.slug}/orders/{order.public_token}"


def delivery_email(order: StoreOrder, offer: StoreOffer, store: LaceStore) -> tuple[str, str, str]:
    """(subject, text, html) sent to the buyer once their payment landed."""
    lines = [f"Thanks for buying {offer.title} from {store.name}. Your payment arrived."]
    if offer.delivery == "link":
        lines.append(f"Here it is: {offer.delivery_url}")
        if offer.delivery_note:
            lines.append(offer.delivery_note)
    else:
        lines.append(offer.delivery_note or f"The {store.name} team will be in touch about it soon.")
    lines.append(f"Your order: {order_url(order, store)}")
    body = "".join(f'<p style="margin:0 0 14px;line-height:1.6">{escape(line)}</p>' for line in lines)
    return (f"Your {offer.title} from {store.name}", "\n\n".join(lines),
            email.branded_html(body, f"Sold by {store.name} on Thalace. Reply to reach them."))


async def deliver_paid() -> int:
    """Email each paid order's buyer. Returns how many were delivered."""
    if not email.configured():
        return 0
    delivered = 0
    async with AsyncSessionLocal() as db:
        rows = (await db.execute(
            select(StoreOrder, StoreOffer, LaceStore).join(StoreOffer, StoreOffer.id == StoreOrder.offer_id)
            .join(LaceStore, LaceStore.id == StoreOrder.store_id)
            .where(StoreOrder.status == "paid").order_by(StoreOrder.paid_at).limit(FULFIL_BATCH))).all()
        for order, offer, store in rows:
            if not await email.send(order.buyer_email, *delivery_email(order, offer, store)):
                continue
            order.status, order.delivered_at = "delivered", datetime.now(UTC)
            if offer.delivery == "service":
                await lace_activity.add(db, store.lace_id, "store_status", f"Deliver {offer.title} to {order.buyer_email}",
                                        summary="They paid and were told your team will be in touch.",
                                        ref=("store_order", order.id))
            await db.commit()
            delivered += 1
    return delivered


async def _settlement_decimals() -> int:
    by_id = {t.asset_id: t.decimals for t in await pay_options()}
    return by_id.get(settings.store_settlement_asset, SETTLEMENT_DECIMALS)


def payout_base(order: StoreOrder, decimals: int) -> Decimal:
    """What a sale is split from, in the settlement asset: what was credited,
    or, when the payment was converted on arrival and the exact amount isn't
    reported, the price less an allowance for the conversion."""
    if order.credited_raw is not None:
        return order.credited_raw
    kept = Decimal(FULL_SHARE_BPS - settings.store_conversion_allowance_bps) / FULL_SHARE_BPS
    return (atomic_price(order.price_cents, decimals) * kept).to_integral_value(ROUND_DOWN)


async def plan_payouts(db: AsyncSession) -> int:
    """Write a pending ledger line for each payee's share of each sale that
    has none yet. Returns how many were written."""
    decimals = await _settlement_decimals()
    planned = exists().where(StoreLedgerEntry.order_id == StoreOrder.id, StoreLedgerEntry.kind == "payout")
    orders = list((await db.scalars(
        select(StoreOrder).join(LaceStore, LaceStore.id == StoreOrder.store_id)
        .where(StoreOrder.status.in_(("paid", "delivered")), LaceStore.grant_id.is_not(None), ~planned)
        .order_by(StoreOrder.paid_at).limit(FULFIL_BATCH))).all())
    written = 0
    for order in orders:
        payees = (await db.scalars(select(StorePayee).where(StorePayee.store_id == order.store_id))).all()
        base = payout_base(order, decimals)
        for payee in payees:
            amount = (base * payee.share_bps / FULL_SHARE_BPS).to_integral_value(ROUND_DOWN)
            if amount <= 0:
                continue
            db.add(StoreLedgerEntry(
                store_id=order.store_id, order_id=order.id, payee_id=payee.id, kind="payout",
                asset=settings.store_settlement_asset, amount_raw=amount, amount_usd=amount / Decimal(10) ** decimals,
                counterparty=payee.address, idempotency_key=new_idempotency_key(f"payout:{order.id}")))
            written += 1
    await db.commit()
    return written


async def _send(api: AgentApi, store: LaceStore, line: StoreLedgerEntry, payee: StorePayee) -> None:
    grant = store_signing.decrypt_grant(store.grant_token_enc)
    common = {"asset": line.asset, "amount": str(line.amount_raw), "idempotency_key": line.idempotency_key}
    if payee.route == "transfer":
        op = await api.transfer(store.agent_id, grant, recipient=payee.address, **common)
    else:
        op = await api.withdraw(store.agent_id, grant, chain=payee.chain, recipient=payee.address, memo=payee.memo,
                                **common)
    line.correlation_id = op.correlation_id


async def _payout_failed(db: AsyncSession, store: LaceStore, line: StoreLedgerEntry, code: str) -> None:
    line.status, line.failure_code, line.settled_at = "failed", code, datetime.now(UTC)
    await lace_activity.add(db, store.lace_id, "store_payout", f"A payout to {line.counterparty} didn't go through",
                            summary=f"NEAR Intents refused it ({code}). The money stays in the Store's wallet.")


async def send_payouts(db: AsyncSession) -> int:
    """Send the oldest unsent payout of each Store whose wallet is idle.
    Returns how many were sent."""
    in_flight = select(StoreLedgerEntry.store_id).where(
        StoreLedgerEntry.kind == "payout", StoreLedgerEntry.status == "pending",
        StoreLedgerEntry.correlation_id.is_not(None))
    lines = list((await db.scalars(
        select(StoreLedgerEntry).where(StoreLedgerEntry.kind == "payout", StoreLedgerEntry.status == "pending",
                                       StoreLedgerEntry.correlation_id.is_(None),
                                       StoreLedgerEntry.store_id.not_in(in_flight))
        .order_by(StoreLedgerEntry.created_at).limit(FULFIL_BATCH))).all())
    api, sent, busy = store_signing.agent_api(), 0, set()
    for line in lines:
        if line.store_id in busy:
            continue
        busy.add(line.store_id)
        store, payee = await db.get(LaceStore, line.store_id), await db.get(StorePayee, line.payee_id)
        if store.frozen_at is not None or payee is None:
            continue
        try:
            await _send(api, store, line, payee)
            sent += 1
        except AgentApiError as exc:
            if exc.retryable or exc.code in WAIT_CODES or exc.code == "unreachable":
                logger.info("Store %s payout %s waits: %s", store.id, line.id, exc.code)
            else:
                await _payout_failed(db, store, line, exc.code)
        except ConflictError as exc:
            # The grant can't be read (STORE_GRANT_KEY unset or changed): nothing was sent.
            logger.error("Store %s payout %s not sent: %s", store.id, line.id, exc)
        await db.commit()
    return sent


async def settle_payouts(db: AsyncSession) -> int:
    """Read each sent payout until it settles. Returns how many completed."""
    lines = list((await db.scalars(
        select(StoreLedgerEntry).where(StoreLedgerEntry.kind == "payout", StoreLedgerEntry.status == "pending",
                                       StoreLedgerEntry.correlation_id.is_not(None))
        .order_by(StoreLedgerEntry.created_at).limit(FULFIL_BATCH))).all())
    api, done = store_signing.agent_api(), 0
    for line in lines:
        try:
            op = await api.status(line.correlation_id)
        except AgentApiError as exc:
            logger.warning("Payout %s: status not read: %s", line.id, exc.code)
            continue
        if not op.final:
            continue
        store = await db.get(LaceStore, line.store_id)
        if op.status == "SUCCESS":
            line.status, line.settled_at = "done", datetime.now(UTC)
            line.tx_hash = op.details.get("transaction_hash") or op.details.get("tx_hash")
            await lace_activity.add(db, store.lace_id, "store_payout",
                                    f"Paid ${line.amount_usd:,.2f} to {line.counterparty}")
            done += 1
        else:
            await _payout_failed(db, store, line, op.failure_code or op.status.lower())
        await db.commit()
    return done


async def fulfil() -> int:
    """One round after the payment watcher: deliver, then plan, send and
    settle payouts. Returns how many deliveries and payouts completed."""
    delivered = await deliver_paid()
    async with AsyncSessionLocal() as db:
        await plan_payouts(db)
        await send_payouts(db)
        paid = await settle_payouts(db)
    return delivered + paid
