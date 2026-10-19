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
    monkeypatch.setattr(settings, "max_requests_per_minute", 3)
    client.sign_in(make_user("Chatty"))
    codes = [client.get("/api/v1/runs/active").status_code for _ in range(4)]
    assert codes == [200, 200, 200, 429]
