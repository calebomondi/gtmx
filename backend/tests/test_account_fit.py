"""Account fit: each account gets the case for the offer (need, capability,
payoff, angle), assessed once, shown on the account and in its feed item."""

import asyncio
import uuid

import pytest

from agents.schemas.accounts import AccountFit
from backend.app.runs import background, manager, signals
from backend.tests.helpers import make_user
from backend.tests.test_runs import _wait_for_status

API = "/api/v1/workspaces"

FIT = AccountFit(
    need="Weight capture across 40 remote collection points", capability="Hybrid cellular/LoRa connectivity",
    payoff="Clerks stop re-keying paper slips, so payouts go out days sooner", benefit="time saved",
    angle="Their new commodities mean more sites to sync; we keep every scale reporting.", strength="strong",
)


async def _drain():
    if manager._tasks:
        await asyncio.gather(*manager._tasks.values(), return_exceptions=True)


@pytest.fixture
def assessed(monkeypatch):
    seen = []

    def fake_assess(offer, account, seller):
        seen.append((offer, account, seller))
        return FIT
    monkeypatch.setattr(background.account_fit, "assess", fake_assess)
    return seen


def _assess(client, workspace):
    run = client.post(f"{API}/{workspace}/accounts/fit").json()
    client.portal.call(_wait_for_status, uuid.UUID(run["id"]), {"completed"})
    client.portal.call(_drain)
    return run


def test_fit_is_assessed_once_and_returned_with_the_account(client, owned, assessed):
    _assess(client, owned["workspace"])
    [account] = client.get(f"{API}/{owned['workspace']}/accounts").json()["accounts"]
    assert account["fit"]["payoff"] == FIT.payoff and account["fit"]["strength"] == "strong"
    assert len(assessed) == 1 and "Account:" in assessed[0][1]

    _assess(client, owned["workspace"])  # nothing left to assess
    assert len(assessed) == 1


def test_a_failed_assessment_leaves_the_account_for_next_time(client, owned, monkeypatch):
    def broken(offer, account, seller):
        raise RuntimeError("model down")
    monkeypatch.setattr(background.account_fit, "assess", broken)
    _assess(client, owned["workspace"])
    [account] = client.get(f"{API}/{owned['workspace']}/accounts").json()["accounts"]
    assert account["fit"] is None


def test_an_opportunity_item_leads_with_the_fit():
    fit = FIT.model_dump()
    assert signals._fit_reason(fit) == FIT.need
    assert signals._fit_insight(fit) == {"means": FIT.payoff, "next_move": FIT.angle}
    assert signals._fit_reason(None) == "Matches your ideal customer profile." and signals._fit_insight(None) is None


def test_only_the_owner_can_start_a_fit_run(client, owned):
    client.sign_in(make_user("Intruder"))
    assert client.post(f"{API}/{owned['workspace']}/accounts/fit").status_code == 404
