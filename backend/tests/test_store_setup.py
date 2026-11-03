"""Setting up a Lace's Store: turning it on makes it, named after the startup;
members see it and admins change it; offers and the revenue split are
checked; and once it's live, its rules change only with a new signature."""

import uuid

import psycopg

from backend.tests.helpers import make_user
from backend.tests.test_lace_jobs import lace  # noqa: F401 -- fixture
from backend.tests.test_lace_members import _join
from backend.tests.test_laces_api import API, lace_runtime  # noqa: F401 -- fixture
from config import settings

LINK_OFFER = {"title": "Pitch deck template", "price_cents": 2900, "delivery": "link",
              "delivery_url": "https://acme.test/dl/deck", "delivery_note": "Duplicate it to your drive."}


def _store(client, lace_id):  # noqa: F811
    return client.put(f"{API}/laces/{lace_id}/store/shown", json={"shown": True})


def _go_live(lace_id):
    with psycopg.connect(settings.database_url, autocommit=True) as conn:
        conn.execute("UPDATE lace_stores SET status = 'live', agent_id = %s WHERE lace_id = %s",
                     ("a" * 64, lace_id))


def test_no_store_until_someone_turns_it_on(client, lace):  # noqa: F811
    assert client.get(f"{API}/laces/{lace}/store").json() is None

    made = _store(client, lace)
    assert made.status_code == 200
    body = made.json()
    assert (body["status"], body["shown"], body["daily_budget_usd"]) == ("setup", True, "50.00")
    assert body["settlement_asset"] == settings.store_settlement_asset
    assert "grant_token_enc" not in body and "grant_id" not in body

    hidden = client.put(f"{API}/laces/{lace}/store/shown", json={"shown": False}).json()
    assert (hidden["id"], hidden["shown"]) == (body["id"], False)


def test_members_see_the_store_and_admins_change_it(client, lace):  # noqa: F811
    _store(client, lace)
    member, admin = make_user("Member"), make_user("Admin")
    _join(lace, member)
    _join(lace, admin, role="admin")

    client.sign_in(member)
    assert client.get(f"{API}/laces/{lace}/store").json()["shown"] is True
    assert client.put(f"{API}/laces/{lace}/store/shown", json={"shown": False}).status_code == 403
    assert client.post(f"{API}/laces/{lace}/store/offers", json=LINK_OFFER).status_code == 403

    client.sign_in(admin)
    assert client.patch(f"{API}/laces/{lace}/store", json={"tagline": "Templates for founders"}).status_code == 200


def test_a_stranger_sees_no_store(client, lace):  # noqa: F811
    _store(client, lace)
    client.sign_in(make_user("Stranger"))
    assert client.get(f"{API}/laces/{lace}/store").status_code == 404


def test_offers_are_drafts_until_put_on_sale(client, lace):  # noqa: F811
    _store(client, lace)
    offer = client.post(f"{API}/laces/{lace}/store/offers", json=LINK_OFFER).json()
    assert (offer["status"], offer["drafted_by_lace"]) == ("draft", False)

    active = client.patch(f"{API}/laces/{lace}/store/offers/{offer['id']}", json={"status": "active"}).json()
    assert active["status"] == "active"
    assert [o["id"] for o in client.get(f"{API}/laces/{lace}/store/offers").json()] == [offer["id"]]


def test_a_link_offer_needs_its_link(client, lace):  # noqa: F811
    _store(client, lace)
    response = client.post(f"{API}/laces/{lace}/store/offers", json={**LINK_OFFER, "delivery_url": None})
    assert response.status_code == 422
    service = client.post(f"{API}/laces/{lace}/store/offers",
                          json={**LINK_OFFER, "delivery": "service", "delivery_url": None}).json()
    assert client.patch(f"{API}/laces/{lace}/store/offers/{service['id']}",
                        json={"delivery": "link"}).status_code == 422


def test_an_offer_of_another_store_is_not_found(client, lace):  # noqa: F811
    _store(client, lace)
    assert client.patch(f"{API}/laces/{lace}/store/offers/{uuid.uuid4()}",
                        json={"status": "active"}).status_code == 404


def test_the_split_cannot_pay_out_more_than_the_sale(client, lace):  # noqa: F811
    _store(client, lace)
    split = [{"label": "Treasury", "route": "transfer", "address": "acme.near", "share_bps": 7000},
             {"label": "Ada", "route": "withdraw", "chain": "base",
              "address": "0xAbC0000000000000000000000000000000000001", "share_bps": 3000}]
    saved = client.put(f"{API}/laces/{lace}/store/payees", json={"payees": split})
    assert saved.status_code == 200
    assert [p["share_bps"] for p in saved.json()] == [7000, 3000]
    # EVM addresses are compared, and kept, in lowercase.
    assert saved.json()[1]["address"] == "0xabc0000000000000000000000000000000000001"

    too_much = [{**split[0], "share_bps": 8000}, split[1]]
    assert client.put(f"{API}/laces/{lace}/store/payees", json={"payees": too_much}).status_code == 422
    twice = [{**split[0], "share_bps": 100}, {**split[0], "label": "Again", "share_bps": 100}]
    assert client.put(f"{API}/laces/{lace}/store/payees", json={"payees": twice}).status_code == 422
    no_chain = [{**split[1], "chain": None}]
    assert client.put(f"{API}/laces/{lace}/store/payees", json={"payees": no_chain}).status_code == 422


def test_a_live_store_keeps_its_rules_and_address(client, lace):  # noqa: F811
    _store(client, lace)
    _go_live(lace)
    split = [{"label": "Treasury", "route": "transfer", "address": "acme.near", "share_bps": 5000}]
    assert client.put(f"{API}/laces/{lace}/store/payees", json={"payees": split}).status_code == 409
    assert client.patch(f"{API}/laces/{lace}/store", json={"daily_budget_usd": "500"}).status_code == 409
    assert client.patch(f"{API}/laces/{lace}/store", json={"slug": "new-address"}).status_code == 409
    # What the storefront says can still change.
    assert client.patch(f"{API}/laces/{lace}/store", json={"tagline": "Now open"}).json()["tagline"] == "Now open"


def test_two_stores_never_share_an_address(client, lace):  # noqa: F811
    first = _store(client, lace).json()
    made = client.post(f"{API}/laces", json={"name": "Ada", "website": "beta.test"})
    assert made.status_code == 201, made.text
    other = made.json()["lace"]["id"]
    second = _store(client, other).json()
    assert first["slug"] != second["slug"]
    assert client.patch(f"{API}/laces/{other}/store", json={"slug": first["slug"]}).status_code == 409
