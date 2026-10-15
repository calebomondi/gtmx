"""A competitor's named clients become *suggested* accounts the user accepts
or dismisses; the target list and the team's context hold targets only."""

import asyncio
import json
import uuid

import psycopg
import pytest

from agents.schemas.accounts import AccountFit, CompetitorClient
from agents.schemas.monitor import CompetitorChange
from backend.app.runs import background, manager
from backend.tests.test_runs import _wait_for_status
from config import settings

API = "/api/v1/workspaces"


async def _drain():
    if manager._tasks:
        await asyncio.gather(*manager._tasks.values(), return_exceptions=True)


def _client(name, country="Kenya", website=None):
    return CompetitorClient(name=name, website=website, country=country, relationship="case_study",
                            evidence=f"{name} cut fuel costs with Rival", source_url="https://rival.example/stories")


@pytest.fixture
def b2b_offer(owned):
    insights = {"icp": {"buyer_type": "b2b", "geo": ["Kenya"], "industries": ["Logistics"]}}
    with psycopg.connect(settings.database_url, autocommit=True) as conn:
        conn.execute("INSERT INTO product_profiles (id, workspace_id, target_geo, insights) VALUES (%s, %s, '[]', %s)",
                     (uuid.uuid4(), owned["workspace"], json.dumps(insights)))
        conn.execute("UPDATE competitors SET weaknesses = %s WHERE workspace_id = %s",
                     (json.dumps([{"text": "Locks fleets into its own hardware", "evidence": "..."}]), owned["workspace"]))
    return owned


@pytest.fixture
def run_accounts(client, b2b_offer, monkeypatch):
    found = {"clients": [_client("Swift Haulage"), _client("Global Freight", country="Germany"),
                         _client("Seeded Account")]}

    async def discovery(workspace_id, run_id):
        return {"found": 0}
    monkeypatch.setattr(background, "run_account_discovery_for_workspace", discovery)
    monkeypatch.setattr(background.competitor_clients, "find", lambda name, website, known: found["clients"])
    monkeypatch.setattr(background.account_fit, "assess", lambda offer, account, seller: AccountFit(
        need="Fleet visibility without new hardware", capability="Hardware-agnostic tracking",
        payoff="Keeps their existing trackers, so switching costs nothing in devices", angle="Keep your trackers."))

    def run():
        started = client.post(f"{API}/{b2b_offer['workspace']}/accounts/runs").json()["run"]
        client.portal.call(_wait_for_status, uuid.UUID(started["id"]), {"completed"})
        client.portal.call(_drain)  # feed items are written after the run completes
        return client.get(f"{API}/{b2b_offer['workspace']}/accounts").json()["accounts"]
    return run


def _seed_account_name(owned):
    with psycopg.connect(settings.database_url, autocommit=True) as conn:
        conn.execute("UPDATE accounts SET name = 'Seeded Account' WHERE id = %s", (owned["account"],))


def test_clients_in_the_icp_countries_are_suggested_with_a_switching_case(run_accounts, b2b_offer, client):
    _seed_account_name(b2b_offer)
    accounts = {a["name"]: a for a in run_accounts()}
    swift = accounts["Swift Haulage"]
    assert swift["review_status"] == "suggested" and swift["via_competitor_name"] == "rival.example"
    assert swift["why_reach_out"] == ["rival.example's weakness: Locks fleets into its own hardware"]
    assert swift["trigger_event"]["source"] == "https://rival.example/stories"
    assert swift["fit"]["payoff"].startswith("Keeps their existing trackers")
    assert "Global Freight" not in accounts  # outside the ICP's countries
    assert accounts["Seeded Account"]["review_status"] == "target"  # an existing account is left alone

    feed = client.get("/api/v1/signals").json()
    assert any(s["title"] == "Uses rival.example: Swift Haulage" for s in feed)


def test_a_suggestion_is_accepted_or_dismissed_but_never_re_suggested_by_hand(run_accounts, b2b_offer, client):
    swift = next(a for a in run_accounts() if a["name"] == "Swift Haulage")
    path = f"{API}/{b2b_offer['workspace']}/accounts/{swift['id']}"
    assert client.patch(path, json={"review_status": "target"}).json()["review_status"] == "target"
    assert client.patch(path, json={"review_status": "dismissed"}).json()["review_status"] == "dismissed"
    assert client.patch(path, json={"review_status": "suggested"}).status_code == 422


def test_running_again_does_not_duplicate_a_suggestion(run_accounts):
    run_accounts()
    assert [a["name"] for a in run_accounts()].count("Swift Haulage") == 1


@pytest.mark.parametrize("country, local, expected", [
    ("Kenya", False, True), ("Nairobi, Kenya", False, True), ("Germany", True, False),
    (None, True, True), (None, False, False),
])
def test_clients_count_in_the_icp_countries(country, local, expected):
    assert background._in_geos(country, ["Kenya"], local) is expected


def test_a_client_move_monitoring_spots_becomes_a_suggestion(client, b2b_offer, monkeypatch):
    win = CompetitorChange(kind="client", title="Signed Kilimo Co-op", summary="Rival announced Kilimo Co-op as a client.",
                           client_name="Kilimo Co-op", client_country="Kenya", source_url="https://rival.example/news",
                           importance="high", implication="Kilimo now runs on Rival's hardware.",
                           counter_move="Offer Kilimo a no-new-hardware pilot.")
    minor = CompetitorChange(kind="client", title="Blog mention", summary="...", client_name="Tiny Shop",
                             client_country="Kenya", importance="low")
    abroad = CompetitorChange(kind="client", title="Signed Berlin Freight", summary="...", client_name="Berlin Freight",
                              client_country="Germany", importance="high")
    monkeypatch.setattr(background.check_competitor, "check",
                        lambda *a, posts=None, offer_detail="": ({"site_hash": "h"}, [win, minor, abroad]))
    monkeypatch.setattr(background.competitor_socials, "refresh", lambda *a: None)
    monkeypatch.setattr(background.account_fit, "assess", lambda offer, account, seller: AccountFit(
        need="n", capability="c", payoff="Keeps their trackers", angle="a"))

    run = client.post(f"{API}/{b2b_offer['workspace']}/competitors/monitor").json()
    client.portal.call(_wait_for_status, uuid.UUID(run["id"]), {"completed"})
    client.portal.call(_drain)

    accounts = {a["name"]: a for a in client.get(f"{API}/{b2b_offer['workspace']}/accounts").json()["accounts"]}
    kilimo = accounts["Kilimo Co-op"]
    assert kilimo["review_status"] == "suggested" and kilimo["fit"]["payoff"] == "Keeps their trackers"
    assert kilimo["trigger_event"]["source"] == "https://rival.example/news"
    assert "Tiny Shop" not in accounts and "Berlin Freight" not in accounts  # immaterial, and abroad
    titles = [s["title"] for s in client.get("/api/v1/signals").json()]
    assert "Uses rival.example: Kilimo Co-op" in titles and "rival.example: Signed Kilimo Co-op" in titles
