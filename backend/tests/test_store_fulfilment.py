"""After a sale: the buyer is emailed the link they paid for; each payee's
share goes out of the Store's wallet under its grant, one at a time, written
to the ledger before it's sent so it's never paid twice; refusals that pass
with time wait, others are recorded and the team told."""

import psycopg
import pytest
from cryptography.fernet import Fernet

from backend.app.services import email, store_checkout, store_fulfilment, store_signing
from backend.tests.test_lace_jobs import lace  # noqa: F401 -- fixture
from backend.tests.test_laces_api import API, lace_runtime  # noqa: F401 -- fixture
from backend.tests.test_store_checkout import OFFER, USDC_BASE, USDC_NEAR, FakeAgentApi, _order, _sql
from config import settings
from data_sources.near.agent_api import AgentApiError, Operation

SPLIT = [{"label": "Treasury", "route": "transfer", "address": "acme.near", "share_bps": 7000},
         {"label": "Ada", "route": "withdraw", "chain": "base", "address": "0xabc1", "share_bps": 2000}]


class PayingAgentApi(FakeAgentApi):
    def __init__(self):
        super().__init__()
        self.sent: list[tuple[str, str, dict]] = []
        self.refuse: AgentApiError | None = None

    async def _out(self, kind, grant, fields):
        if self.refuse:
            raise self.refuse
        self.sent.append((kind, grant, fields))
        return Operation(f"op_pay{len(self.sent)}", kind, "PROCESSING")

    async def transfer(self, agent_id, grant, **fields):
        return await self._out("transfer", grant, fields)

    async def withdraw(self, agent_id, grant, **fields):
        return await self._out("withdraw", grant, fields)


@pytest.fixture
def agent_api(monkeypatch):
    fake = PayingAgentApi()
    monkeypatch.setattr(store_signing, "agent_api", lambda: fake)
    monkeypatch.setattr(store_checkout, "_tokens", (0.0, {}))
    monkeypatch.setattr(settings, "store_grant_key", Fernet.generate_key().decode())
    return fake


@pytest.fixture
def outbox(monkeypatch):
    sent = []

    async def send(to, subject, text, html):
        sent.append((to, subject, text))
        return True

    monkeypatch.setattr(email, "configured", lambda: True)
    monkeypatch.setattr(email, "send", send)
    return sent


def _paid_order(client, lace_id, pay_asset=USDC_NEAR, offer=OFFER):  # noqa: F811
    slug = client.put(f"{API}/laces/{lace_id}/store/shown", json={"shown": True}).json()["slug"]
    offer_id = client.post(f"{API}/laces/{lace_id}/store/offers", json=offer).json()["id"]
    client.put(f"{API}/laces/{lace_id}/store/payees", json={"payees": SPLIT})
    token = store_signing.encrypt_grant("ngt_secret")
    with psycopg.connect(settings.database_url, autocommit=True) as conn:
        conn.execute("UPDATE lace_stores SET status = 'live', agent_id = %s, grant_id = 'g1', grant_token_enc = %s "
                     "WHERE lace_id = %s", ("a" * 64, token, lace_id))
    order = _order(client, slug, offer_id, pay_asset=pay_asset).json()
    client.portal.call(store_checkout.watch_orders)
    return order


def _land(client, agent_api, op="op_1"):
    agent_api.statuses[op] = Operation(op, "deposit", "SUCCESS")
    client.portal.call(store_checkout.watch_orders)


def test_the_buyer_gets_the_link_they_paid_for(client, lace, agent_api, outbox):  # noqa: F811
    order = _paid_order(client, lace)
    _land(client, agent_api)
    client.portal.call(store_fulfilment.deliver_paid)
    [(to, subject, text)] = outbox
    assert to == "buyer@example.com" and subject.startswith("Your Pitch deck template")
    assert "https://acme.test/dl/secret" in text and order["token"] in text
    assert client.get(f"{API}/storefront/orders/{order['token']}").json()["status"] == "delivered"


def test_a_service_sale_tells_the_team_to_deliver_it(client, lace, agent_api, outbox):  # noqa: F811
    _paid_order(client, lace, offer={**OFFER, "delivery": "service", "delivery_url": None,
                                      "delivery_note": "We'll book a call within a day."})
    _land(client, agent_api)
    client.portal.call(store_fulfilment.deliver_paid)
    assert "We'll book a call within a day." in outbox[0][2]
    assert ("store_status", "Deliver Pitch deck template to buyer@example.com") in _sql(
        "SELECT kind, title FROM lace_activity WHERE kind LIKE 'store%'")


def test_each_payee_gets_their_share_once(client, lace, agent_api, outbox):  # noqa: F811
    _paid_order(client, lace)
    _land(client, agent_api)
    client.portal.call(store_fulfilment.fulfil)
    # 70% and 20% of the $29.50 credited; 10% stays in the wallet.
    assert sorted(_sql("SELECT counterparty, amount_raw FROM store_ledger WHERE kind = 'payout'")) == [
        ("0xabc1", 5_900_000), ("acme.near", 20_650_000)]
    # One money action per wallet at a time: one sent this round, under the grant.
    [(kind, grant, fields)] = agent_api.sent
    assert grant == "ngt_secret" and fields["asset"] == settings.store_settlement_asset

    for _ in range(3):
        for n in range(1, len(agent_api.sent) + 1):
            agent_api.statuses[f"op_pay{n}"] = Operation(f"op_pay{n}", "transfer", "SUCCESS")
        client.portal.call(store_fulfilment.fulfil)
    assert len(agent_api.sent) == 2
    assert {k for k, _, _ in agent_api.sent} == {"transfer", "withdraw"}
    assert _sql("SELECT status FROM store_ledger WHERE kind = 'payout'") == [("done",), ("done",)]
    assert len(_sql("SELECT 1 FROM lace_activity WHERE kind = 'store_payout'")) == 2


def test_a_converted_payment_is_split_from_the_price_less_an_allowance(client, lace, agent_api, outbox):  # noqa: F811
    _paid_order(client, lace, pay_asset=USDC_BASE)
    _land(client, agent_api)
    client.portal.call(store_fulfilment.fulfil)
    base = 29_500_000 * (10_000 - settings.store_conversion_allowance_bps) // 10_000
    assert sorted(a for (a,) in _sql("SELECT amount_raw FROM store_ledger WHERE kind = 'payout'")) == [
        base * 2000 // 10_000, base * 7000 // 10_000]


def test_a_payout_over_the_daily_cap_waits(client, lace, agent_api, outbox):  # noqa: F811
    _paid_order(client, lace)
    _land(client, agent_api)
    agent_api.refuse = AgentApiError("spend_budget_exceeded", status=403)
    client.portal.call(store_fulfilment.fulfil)
    assert _sql("SELECT status, correlation_id FROM store_ledger WHERE kind = 'payout'") == [
        ("pending", None), ("pending", None)]
    agent_api.refuse = None
    client.portal.call(store_fulfilment.fulfil)
    assert len(agent_api.sent) == 1


def test_a_refused_payout_is_recorded_and_the_team_told(client, lace, agent_api, outbox):  # noqa: F811
    _paid_order(client, lace)
    _land(client, agent_api)
    agent_api.refuse = AgentApiError("policy_destination_denied", status=403)
    client.portal.call(store_fulfilment.fulfil)
    assert ("failed", "policy_destination_denied") in _sql(
        "SELECT status, failure_code FROM store_ledger WHERE kind = 'payout'")
    assert _sql("SELECT count(*) FROM lace_activity WHERE kind = 'store_payout'") == [(1,)]


def test_a_frozen_wallet_sends_nothing(client, lace, agent_api, outbox):  # noqa: F811
    _paid_order(client, lace)
    _land(client, agent_api)
    with psycopg.connect(settings.database_url, autocommit=True) as conn:
        conn.execute("UPDATE lace_stores SET frozen_at = now()")
    client.portal.call(store_fulfilment.fulfil)
    assert agent_api.sent == []
