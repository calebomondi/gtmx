"""Limits: a daily cap per run kind (an admin can override it per user), and
a per-user request rate on the API."""

import uuid

import pytest

from agents.lace.store import JobRefused
from backend.app.runs import manager
from backend.tests.helpers import make_user
from backend.tests.test_lace_jobs import lace  # noqa: F401 -- fixture
from backend.tests.test_laces_api import lace_runtime  # noqa: F401 -- fixture
from config import settings


def test_a_lace_job_past_the_daily_cap_is_refused(client, lace, user, monkeypatch):  # noqa: F811
    monkeypatch.setattr(settings, "max_account_runs_per_day", 0)
    with pytest.raises(JobRefused, match="today's limit of 0 lace_contacts runs"):
        client.portal.call(manager.start_lace_job, "lace_contacts", user.id, uuid.UUID(lace), {})


def test_request_rate_limit(client, monkeypatch):
    monkeypatch.setattr(settings, "max_reads_per_minute", 3)
    client.sign_in(make_user("Chatty"))
    codes = [client.get("/api/v1/runs/active").status_code for _ in range(4)]
    assert codes == [200, 200, 200, 429]
    assert int(client.get("/api/v1/runs/active").headers["Retry-After"]) > 0


def test_reads_writes_and_telemetry_have_their_own_budgets(client, monkeypatch):
    monkeypatch.setattr(settings, "max_reads_per_minute", 2)
    monkeypatch.setattr(settings, "max_requests_per_minute", 1)
    monkeypatch.setattr(settings, "max_telemetry_per_minute", 1)
    client.sign_in(make_user("Busy page"))
    assert [client.get("/api/v1/runs/active").status_code for _ in range(3)] == [200, 200, 429]
    # Reads used up, a write still goes through, then its own budget runs out.
    assert client.post("/api/v1/activity/heartbeat").status_code == 200
    assert client.post("/api/v1/feedback", json={"text": "Loving it"}).status_code < 300
    assert client.post("/api/v1/feedback", json={"text": "Again"}).status_code == 429
    assert client.post("/api/v1/activity/heartbeat").status_code == 429
