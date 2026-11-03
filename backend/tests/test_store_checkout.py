"""Buying from a Store: the public storefront shows what's on sale and never
the delivery link; an order gets a one-time address quoted for exactly the
price; the watcher marks it paid when the deposit lands, records the sale on
the ledger and the Feed, and says so when a payment is refunded instead."""

import psycopg
import pytest

from backend.app.services import store_checkout, store_signing
from backend.tests.test_lace_jobs import lace  # noqa: F401 -- fixture
from backend.tests.test_laces_api import API, lace_runtime  # noqa: F401 -- fixture
from config import settings
from data_sources.near.agent_api import AgentApiError, Operation, Token

USDC_NEAR = settings.store_pay_assets[0]
USDC_BASE = settings.store_pay_assets[2]
OFFER = {"title": "Pitch deck template", "price_cents": 2950, "delivery": "link",
         "delivery_url": "https://acme.test/dl/secret", "status": "active"}


class FakeAgentApi:
    def __init__(self):
        self.deposits: list[dict] = []
        self.statuses: dict[str, Operation] = {}
        self.refuse_deposit = False

    async def tokens(self):
        return [Token(USDC_NEAR, "USDC", 6, "near", 1.0), Token(USDC_BASE, "USDC", 6, "base", 1.0),
                Token("nep141:wrap.near", "wNEAR", 24, "near", 3.1)]

    async def deposit(self, agent_id, *, origin_asset, amount, destination_asset, idempotency_key):
        if self.refuse_deposit:
            raise AgentApiError("deposit_quota_exceeded", status=429)
        n = len(self.deposits) + 1
        self.deposits.append({"agent_id": agent_id, "origin_asset": origin_asset, "amount": amount,
                              "destination_asset": destination_asset})
        return Operation(f"op_{n}", "deposit", "PENDING_DEPOSIT",
                         details={"deposit_address": f"addr{n}", "expires_at": "2026-11-04T12:00:00Z"})

    async def status(self, correlation_id, *, wait_ms=0):
        return self.statuses.get(correlation_id, Operation(correlation_id, "deposit", "PENDING_DEPOSIT"))


@pytest.fixture
def agent_api(monkeypatch):
    fake = FakeAgentApi()
    monkeypatch.setattr(store_signing, "agent_api", lambda: fake)
    monkeypatch.setattr(store_checkout, "_tokens", (0.0, {}))
    return fake


def _live_store(client, lace_id):  # noqa: F811
    slug = client.put(f"{API}/laces/{lace_id}/store/shown", json={"shown": True}).json()["slug"]
    offer = client.post(f"{API}/laces/{lace_id}/store/offers", json=OFFER).json()
    with psycopg.connect(settings.database_url, autocommit=True) as conn:
        conn.execute("UPDATE lace_stores SET status = 'live', agent_id = %s WHERE lace_id = %s", ("a" * 64, lace_id))
    return slug, offer["id"]


def _order(client, slug, offer_id, pay_asset=USDC_BASE):
    return client.post(f"{API}/storefront/{slug}/orders",
                       json={"offer_id": offer_id, "email": "buyer@example.com", "pay_asset": pay_asset})


def _sql(query, *args):
    with psycopg.connect(settings.database_url) as conn:
        return conn.execute(query, args or None).fetchall()


def test_the_storefront_shows_offers_and_never_the_delivery_link(client, lace, agent_api):  # noqa: F811
    slug, offer_id = _live_store(client, lace)
    front = client.get(f"{API}/storefront/{slug}")
    assert front.status_code == 200
    body = front.json()
    assert body["selling"] is True
    assert [o["id"] for o in body["offers"]] == [offer_id]
    assert "secret" not in front.text and "delivery_url" not in front.text
    # Only the coins the Store takes, not everything NEAR Intents lists.
    assert [c["chain"] for c in body["pay_with"]] == ["near", "base"]


def test_a_store_being_set_up_is_not_public(client, lace, agent_api):  # noqa: F811
    slug = client.put(f"{API}/laces/{lace}/store/shown", json={"shown": True}).json()["slug"]
    assert client.get(f"{API}/storefront/{slug}").status_code == 404


def test_an_order_is_quoted_for_exactly_the_price(client, lace, agent_api):  # noqa: F811
    slug, offer_id = _live_store(client, lace)
    placed = _order(client, slug, offer_id)
    assert placed.status_code == 201, placed.text
    order = placed.json()
    assert (order["status"], order["pay_amount"], order["deposit_address"]) == ("awaiting_payment", "29.5", "addr1")
    assert order["pay_coin"] == {"asset_id": USDC_BASE, "symbol": "USDC", "chain": "base"}
    assert agent_api.deposits == [{"agent_id": "a" * 64, "origin_asset": USDC_BASE, "amount": "29500000",
                                   "destination_asset": settings.store_settlement_asset}]
    assert client.get(f"{API}/storefront/orders/{order['token']}").json()["deposit_address"] == "addr1"


def test_only_the_coins_the_store_takes(client, lace, agent_api):  # noqa: F811
    slug, offer_id = _live_store(client, lace)
    assert _order(client, slug, offer_id, pay_asset="nep141:wrap.near").status_code == 422


def test_a_paused_store_takes_no_orders(client, lace, agent_api):  # noqa: F811
    slug, offer_id = _live_store(client, lace)
    with psycopg.connect(settings.database_url, autocommit=True) as conn:
        conn.execute("UPDATE lace_stores SET status = 'paused' WHERE slug = %s", (slug,))
    assert client.get(f"{API}/storefront/{slug}").json()["selling"] is False
    assert _order(client, slug, offer_id).status_code == 409


def test_no_address_means_a_failed_order_not_a_silent_one(client, lace, agent_api):  # noqa: F811
    slug, offer_id = _live_store(client, lace)
    agent_api.refuse_deposit = True
    assert _order(client, slug, offer_id).status_code == 409
    assert _sql("SELECT status, failure_code FROM store_orders") == [("failed", "deposit_quota_exceeded")]


def test_checkouts_are_rate_limited_per_network(client, lace, agent_api, monkeypatch):  # noqa: F811
    monkeypatch.setattr(settings, "store_orders_per_ip_per_hour", 2)
    slug, offer_id = _live_store(client, lace)
    assert [_order(client, slug, offer_id).status_code for _ in range(3)] == [201, 201, 429]


def test_a_landed_payment_is_a_sale(client, lace, agent_api):  # noqa: F811
    slug, offer_id = _live_store(client, lace)
    token = _order(client, slug, offer_id, pay_asset=USDC_NEAR).json()["token"]
    assert client.portal.call(store_checkout.watch_orders) == 0

    agent_api.statuses["op_1"] = Operation("op_1", "deposit", "SUCCESS")
    assert client.portal.call(store_checkout.watch_orders) == 1
    assert client.get(f"{API}/storefront/orders/{token}").json()["status"] == "paid"
    # Paid in the settlement coin itself: credited exactly.
    assert _sql("SELECT credited_raw FROM store_orders") == [(29_500_000,)]
    assert _sql("SELECT kind, status, amount_raw, amount_usd FROM store_ledger") == [("sale", "done", 29_500_000, 29.5)]
    assert _sql("SELECT kind, title FROM lace_activity WHERE kind LIKE 'store%'") == [
        ("store_sale", "Sold Pitch deck template for $29.50")]
    # A paid order is not read again.
    agent_api.statuses["op_1"] = Operation("op_1", "deposit", "REFUNDED")
    client.portal.call(store_checkout.watch_orders)
    assert client.get(f"{API}/storefront/orders/{token}").json()["status"] == "paid"


def test_a_refunded_payment_tells_the_team(client, lace, agent_api):  # noqa: F811
    slug, offer_id = _live_store(client, lace)
    _order(client, slug, offer_id)
    agent_api.statuses["op_1"] = Operation("op_1", "deposit", "REFUNDED", details={"failure_reason": "amount_too_low"})
    client.portal.call(store_checkout.watch_orders)
    assert _sql("SELECT status, failure_code FROM store_orders") == [("refunded", "amount_too_low")]
    assert _sql("SELECT count(*) FROM store_ledger") == [(0,)]
    assert _sql("SELECT kind FROM lace_activity WHERE kind LIKE 'store%'") == [("store_status",)]


def test_an_unpaid_address_expires(client, lace, agent_api):  # noqa: F811
    slug, offer_id = _live_store(client, lace)
    _order(client, slug, offer_id)
    agent_api.statuses["op_1"] = Operation("op_1", "deposit", "FAILED", failure_code="deposit_expired")
    client.portal.call(store_checkout.watch_orders)
    assert _sql("SELECT status FROM store_orders") == [("expired",)]


def test_an_unknown_order_token_is_not_found(client, agent_api):
    assert client.get(f"{API}/storefront/orders/nope").status_code == 404
