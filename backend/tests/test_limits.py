"""Per-user usage limits: one discovery at a time, daily run caps, and the
REST request rate limit."""

import pytest

from backend.app.runs import discovery, manager
from backend.app.services.errors import RateLimitedError
from backend.tests.helpers import make_user
from backend.tests.test_runs import REQUEST, FakeAgent, _wait_for_status
from config import settings


@pytest.fixture
def agent(monkeypatch):
    fake = FakeAgent()
    monkeypatch.setattr(discovery, "get_agent", lambda: fake)
    return fake


async def test_one_discovery_at_a_time(agent):
    owner = make_user("Owner")
    first = await manager.start_discovery(owner.id, REQUEST)
    await _wait_for_status(first.id, {"awaiting_input"})
    with pytest.raises(RateLimitedError, match="already have a discovery run"):
        await manager.start_discovery(owner.id, REQUEST)
    # Another user is unaffected.
    other = await manager.start_discovery(make_user("Other").id, REQUEST)
    await _wait_for_status(other.id, {"awaiting_input"})
    # Once the first finishes (here: cancelled), the owner may start again.
    await manager.cancel(owner.id, first.id)
    again = await manager.start_discovery(owner.id, REQUEST)
    await _wait_for_status(again.id, {"awaiting_input"})


async def test_daily_discovery_cap(agent, monkeypatch):
    monkeypatch.setattr(settings, "max_discovery_runs_per_day", 1)
    owner = make_user("Owner")
    run = await manager.start_discovery(owner.id, REQUEST)
    await _wait_for_status(run.id, {"awaiting_input"})
    await manager.cancel(owner.id, run.id)
    with pytest.raises(RateLimitedError, match="today's limit of 1 discovery"):
        await manager.start_discovery(owner.id, REQUEST)


def test_competitor_and_account_run_caps(client, owned, monkeypatch):
    monkeypatch.setattr(settings, "max_competitor_runs_per_day", 0)
    monkeypatch.setattr(settings, "max_account_runs_per_day", 0)
    for kind in ("competitors", "accounts"):
        response = client.post(f"/api/v1/workspaces/{owned['workspace']}/{kind}/runs")
        assert response.status_code == 429, response.text
        assert response.headers["Retry-After"] == "3600"


def test_request_rate_limit(client, monkeypatch):
    monkeypatch.setattr(settings, "max_requests_per_minute", 3)
    client.sign_in(make_user("Chatty"))
    codes = [client.get("/api/v1/runs/active").status_code for _ in range(4)]
    assert codes == [200, 200, 200, 429]
