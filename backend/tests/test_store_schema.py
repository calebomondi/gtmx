"""The Store's tables keep the money rules in the database itself: a Store
only sells once its wallet exists, shares stay in range, a payout names who
it paid, and the same share of an order is never paid twice."""

import uuid
from decimal import Decimal

import pytest
from sqlalchemy.exc import IntegrityError

from backend.app.database.connect import AsyncSessionLocal
from backend.app.database.lace_models import Lace
from backend.app.database.store_models import LaceStore, StoreLedgerEntry, StoreOffer, StoreOrder, StorePayee

USDC = "nep141:17208628f84f5d6ad33f0da3bbbeb27ffcb398eac501a31bd6ad2011e36133a1"


async def _store(**fields) -> uuid.UUID:
    async with AsyncSessionLocal() as db:
        lace = Lace(user_id=uuid.uuid4(), name="Ada", website="https://acme.test", operates_in=[])
        db.add(lace)
        await db.flush()
        store = LaceStore(lace_id=lace.id, slug=f"acme-{uuid.uuid4().hex[:6]}", name="Acme",
                          settlement_asset=USDC, daily_budget_usd=Decimal("50"), **fields)
        db.add(store)
        await db.commit()
        return store.id


async def _add(*rows) -> None:
    async with AsyncSessionLocal() as db:
        db.add_all(rows)
        await db.commit()


async def _order(store_id: uuid.UUID) -> tuple[uuid.UUID, uuid.UUID]:
    offer = StoreOffer(id=uuid.uuid4(), store_id=store_id, title="Template pack", price_cents=2900,
                       delivery="link", delivery_url="https://acme.test/dl/abc")
    payee = StorePayee(id=uuid.uuid4(), store_id=store_id, label="Treasury", route="transfer",
                       address="acme.near", share_bps=7000)
    await _add(offer, payee)
    order = StoreOrder(id=uuid.uuid4(), store_id=store_id, offer_id=offer.id, public_token=uuid.uuid4().hex,
                       buyer_email="buyer@example.com", price_cents=2900, pay_asset=USDC,
                       pay_amount_raw=Decimal("29000000"), deposit_idempotency_key=f"order:{uuid.uuid4().hex}")
    await _add(order)
    return order.id, payee.id


async def test_a_store_sells_only_once_its_wallet_exists():
    with pytest.raises(IntegrityError, match="live_has_agent"):
        await _store(status="live")
    await _store(status="live", agent_id="a" * 64)


@pytest.mark.parametrize("slug", ["-acme", "Acme", "a", "acme store"])
async def test_a_store_address_is_a_plain_slug(slug):
    async with AsyncSessionLocal() as db:
        lace = Lace(user_id=uuid.uuid4(), name="Ada", website="https://acme.test", operates_in=[])
        db.add(lace)
        await db.flush()
        db.add(LaceStore(lace_id=lace.id, slug=slug, name="Acme", settlement_asset=USDC,
                         daily_budget_usd=Decimal("50")))
        with pytest.raises(IntegrityError, match="slug_format"):
            await db.commit()


@pytest.mark.parametrize("share_bps", [0, 10_001])
async def test_a_share_is_between_nothing_and_everything(share_bps):
    store_id = await _store()
    with pytest.raises(IntegrityError, match="share_range"):
        await _add(StorePayee(store_id=store_id, label="Cofounder", route="transfer", address="ada.near",
                              share_bps=share_bps))


async def test_a_withdrawal_payee_names_its_chain():
    store_id = await _store()
    with pytest.raises(IntegrityError, match="withdraw_has_chain"):
        await _add(StorePayee(store_id=store_id, label="Ops", route="withdraw", address="0xabc", share_bps=100))


async def test_a_link_offer_has_its_link():
    store_id = await _store()
    with pytest.raises(IntegrityError, match="link_has_url"):
        await _add(StoreOffer(store_id=store_id, title="Course", price_cents=100, delivery="link"))


async def test_an_order_share_is_paid_once():
    store_id = await _store()
    order_id, payee_id = await _order(store_id)

    def payout(key: str) -> StoreLedgerEntry:
        return StoreLedgerEntry(store_id=store_id, order_id=order_id, payee_id=payee_id, kind="payout", asset=USDC,
                                amount_raw=Decimal("20300000"), idempotency_key=key)

    await _add(payout("payout:1:aaaaaaaa"))
    with pytest.raises(IntegrityError, match="uq_store_ledger_order_id_kind_payee_id"):
        await _add(payout("payout:1:bbbbbbbb"))


async def test_a_payout_names_its_payee_and_order():
    store_id = await _store()
    with pytest.raises(IntegrityError, match="payout_has_payee"):
        await _add(StoreLedgerEntry(store_id=store_id, kind="payout", asset=USDC, amount_raw=Decimal("1")))
