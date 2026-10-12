"""Competitor monitoring: the first check records a baseline silently, later
checks turn material changes into feed signals, social stats refresh on their
own slower cadence, and the scheduler only picks stale, live workspaces."""

import asyncio
import uuid
from datetime import UTC, datetime, timedelta

import psycopg
import pytest

from agents.schemas.monitor import CompetitorChange
from backend.app.runs import background, manager, scheduler
from backend.tests.test_runs import _wait_for_status
from config import settings

API = "/api/v1/workspaces"


async def _drain():
    if manager._tasks:
        await asyncio.gather(*manager._tasks.values(), return_exceptions=True)


@pytest.fixture(autouse=True)
def socials_calls(monkeypatch):
    calls = []

    def fake_refresh(name, website, tracking, previous):
        calls.append(name)
        return {"x": {"platform": "x", "url": "https://x.com/rival", "followers": 1200}}, {"x": "https://x.com/rival"}
    monkeypatch.setattr(background.competitor_socials, "refresh", fake_refresh)
    return calls


def _run_monitor(client, workspace):
    run = client.post(f"{API}/{workspace}/competitors/monitor").json()
    client.portal.call(_wait_for_status, uuid.UUID(run["id"]), {"completed"})
    client.portal.call(_drain)


def test_baseline_then_changes_become_signals(client, owned, monkeypatch):
    seen_previous = []

    def fake_check(name, website, previous, offer, posts=None):
        seen_previous.append(previous)
        state = {"site_hash": "h1", "site_text": "Pro $10/seat", "news_urls": []}
        if previous is None:
            return state, []
        return state, [
            CompetitorChange(kind="pricing", title="Cut Pro to $8/seat", summary="Undercuts us.", importance="high"),
            CompetitorChange(kind="news", title="Blog redesign", summary="Cosmetic.", importance="low"),
        ]
    monkeypatch.setattr(background.check_competitor, "check", fake_check)

    _run_monitor(client, owned["workspace"])  # baseline: tracking starts, no changes yet
    assert [s["title"] for s in client.get("/api/v1/signals").json()] == ["Now monitoring 1 competitor"]
    competitors = client.get(f"{API}/{owned['workspace']}/competitors").json()["competitors"]
    assert competitors[0]["last_checked_at"] is not None

    _run_monitor(client, owned["workspace"])  # second check sees the baseline
    assert seen_previous[-1] == {"site_hash": "h1", "site_text": "Pro $10/seat", "news_urls": []}
    feed = client.get("/api/v1/signals").json()
    assert [(s["title"], s["hot"]) for s in feed if s["entity"] != "Competitor monitoring"] == [
        ("rival.example: Cut Pro to $8/seat", True),
    ]


def test_check_now_needs_competitors(client, user, seed_workspace):
    empty = seed_workspace(user.id, "Empty")
    assert client.post(f"{API}/{empty}/competitors/monitor").status_code == 409


async def test_scheduler_picks_only_stale_live_workspaces(owned, monkeypatch):
    started = []

    async def fake_start(kind, user_id, workspace_id, **kw):
        started.append(str(workspace_id))
    monkeypatch.setattr(manager, "start_background", fake_start)
    assert await scheduler.sweep() == 1 and started == [owned["workspace"]]  # never checked

    with psycopg.connect(settings.database_url, autocommit=True) as conn:
        conn.execute("UPDATE competitors SET last_checked_at = %s", (datetime.now(UTC),))
    started.clear()
    assert await scheduler.sweep() == 0  # fresh

    with psycopg.connect(settings.database_url, autocommit=True) as conn:
        conn.execute("UPDATE competitors SET last_checked_at = %s", (datetime.now(UTC) - timedelta(hours=30),))
        conn.execute("UPDATE workspaces SET archived = true")
    assert await scheduler.sweep() == 0  # archived workspaces are left alone


def test_socials_refresh_weekly_and_record_found_handles(client, owned, monkeypatch, socials_calls):
    checked_posts = []
    monkeypatch.setattr(background.check_competitor, "check",
                        lambda *a, posts=None: checked_posts.append(posts) or ({}, []))
    _run_monitor(client, owned["workspace"])
    competitor = client.get(f"{API}/{owned['workspace']}/competitors").json()["competitors"][0]
    assert competitor["social_profiles"]["x"]["followers"] == 1200 and competitor["socials_checked_at"]
    assert {"kind": "x", "value": "https://x.com/rival", "confidence": "high"} in competitor["tracking_sources"]

    _run_monitor(client, owned["workspace"])  # stats are fresh: no second paid scrape
    assert len(socials_calls) == 1 and checked_posts == [[], []]


def test_finished_competitor_run_starts_monitoring(client, owned, monkeypatch):
    monkeypatch.setattr(settings, "monitor_enabled", True)
    started = []

    async def fake_start(kind, user_id, workspace_id, **kw):
        started.append(kind)
    monkeypatch.setattr(manager, "start_background", fake_start)
    client.portal.call(background._start_monitoring, uuid.UUID(owned["competitor_run"]), uuid.UUID(owned["workspace"]))
    assert started == ["monitor"]
