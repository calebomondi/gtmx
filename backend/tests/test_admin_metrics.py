"""Admin metrics: run outcomes and estimated spend over a window, with
unpriced usage surfaced rather than counted as free."""

import uuid
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import psycopg
import pytest

from backend.app.services import admin as admin_service
from backend.tests.helpers import make_user
from config import settings
from utils import usage

API = "/api/v1/admin/metrics"


@pytest.fixture
def admin_client(client, monkeypatch):
    client.sign_in(make_user("Boss", is_admin=True))

    async def three_users():
        return [SimpleNamespace(id=str(uuid.uuid4()), email=None, created_at=None) for _ in range(3)]
    monkeypatch.setattr(admin_service, "list_all_users", three_users)
    return client


def _seed(user_id):
    now = datetime.now(UTC)
    with psycopg.connect(settings.database_url, autocommit=True) as conn:
        runs = []
        for status, minutes, age_days in [("completed", 2, 0), ("completed", 4, 0), ("failed", 1, 1), ("completed", 9, 40)]:
            created = now - timedelta(days=age_days)
            run_id = uuid.uuid4()
            conn.execute(
                "INSERT INTO runs (id, user_id, kind, status, created_at, started_at, finished_at)"
                " VALUES (%s, %s, 'discovery', %s, %s, %s, %s)",
                (run_id, user_id, status, created, created, created + timedelta(minutes=minutes)),
            )
            runs.append(run_id)
        conn.execute(
            "INSERT INTO llm_calls (run_id, log_label, provider, model, input_tokens, output_tokens, seconds, ok)"
            " VALUES (%s, 'x', 'qwen', 'qwen3.7-plus', 1000000, 500000, 1, true),"
            " (%s, 'x', 'qwen', 'mystery-model', 10, 10, 1, false)",
            (runs[0], runs[1]),
        )
        conn.execute(
            "INSERT INTO api_calls (run_id, provider, operation, seconds, ok)"
            " VALUES (%s, 'exa', 'search', 1, true), (%s, 'brightdata', 'x.profiles', 30, true)",
            (runs[0], runs[0]),
        )


def test_metrics_window_success_rate_and_spend(admin_client, monkeypatch):
    monkeypatch.setattr(settings, "llm_prices", {"qwen3.7-plus": [0.4, 1.2]})
    monkeypatch.setattr(settings, "api_call_prices", {"exa.search": 0.01, "brightdata": 0.002})
    _seed(uuid.uuid4())

    m = admin_client.get(API, params={"days": 30}).json()
    assert m["total_users"] == 3 and m["active_users"] == 1
    assert m["runs_by_status"] == {"completed": 2, "failed": 1}  # the 40-day-old run is outside
    assert m["success_rate"] == 0.667 and m["avg_duration_s"] == 180.0
    assert m["llm_cost_usd"] == 1.0  # 1M in * 0.4 + 0.5M out * 1.2
    assert m["api_cost_usd"] == 0.012
    assert m["unpriced"] == ["mystery-model"]
    mystery = next(line for line in m["llm_costs"] if line["name"] == "mystery-model")
    assert mystery["cost_usd"] is None and mystery["failed_calls"] == 1
    assert len(m["series"]) == 30 and m["series"][-1]["runs_started"] == 2 and m["series"][-1]["llm_cost_usd"] == 1.0


def test_metrics_need_admin_and_bounded_window(client, admin_client):
    assert admin_client.get(API, params={"days": 365}).status_code == 422
    client.sign_in(make_user("Pleb"))
    assert client.get(API).status_code == 403


def test_usage_track_reports_failures_and_reraises():
    seen = []
    usage.set_sink(seen.append)
    try:
        with usage.track("exa", "search"):
            pass
        with pytest.raises(RuntimeError), usage.track("brightdata", "x.profiles"):
            raise RuntimeError("boom")
    finally:
        usage.set_sink(None)
    assert [(r["provider"], r["ok"]) for r in seen] == [("exa", True), ("brightdata", False)]
