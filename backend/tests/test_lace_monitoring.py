"""Lace competitor monitoring: checked on schedule or on request, baselines
saved, and only material changes reach the founder."""

import uuid
from datetime import UTC, datetime, timedelta

import psycopg
import pytest
from langchain_core.messages import AIMessage

from agents.schemas.monitor import CompetitorChange
from backend.app.runs import lace as lace_runs
from backend.app.runs import manager, scheduler
from backend.tests.test_lace_jobs import _runs, _wait_for_turns, lace  # noqa: F401 -- fixture
from backend.tests.test_laces_api import API, lace_runtime  # noqa: F401 -- fixture
from backend.tests.test_runs import _wait_for_status
from config import settings

CUT = CompetitorChange(kind="pricing", title="Cut Pro to $8", summary="Undercuts our Basic plan.",
                       implication="Price-led deals get harder.", counter_move="Lead with migration help.",
                       importance="high", source_url="https://rival.test/pricing")
MEME = CompetitorChange(kind="social", title="Posted a meme", summary="Noise.", importance="low")


def _competitor(lace_id, name, status="tracked", checked=None):
    with psycopg.connect(settings.database_url, autocommit=True) as conn:
        return conn.execute(
            "INSERT INTO lace_competitors (id, lace_id, name, website, domain_key, status, last_checked_at)"
            " VALUES (%s, %s, %s, %s, %s, %s, %s) RETURNING id",
            (uuid.uuid4(), lace_id, name, f"https://{name.lower()}.test", f"{name.lower()}.test", status, checked),
        ).fetchone()[0]


@pytest.fixture
def checks(monkeypatch):
    """What the change detector reports per competitor name."""
    seen: dict[str, dict | None] = {}
    results: dict[str, list] = {}

    def check(name, website, previous, our_offer, posts, offer_detail):
        seen[name] = previous
        return {"site_hash": f"h-{name}"}, results.get(name, [])

    monkeypatch.setattr(lace_runs.check_competitor, "check", check)
    return seen, results


def test_material_changes_reach_the_founder(client, lace, lace_runtime, checks, user):  # noqa: F811
    seen, results = checks
    _competitor(lace, "Rival")
    _competitor(lace, "Quiet")
    _competitor(lace, "Gone", status="dismissed")
    results["Rival"] = [CUT, MEME]
    lace_runtime.append(AIMessage(content="Rival cut its Pro plan to $8."))

    run = client.portal.call(manager.start_lace_job, "lace_monitor", user.id, uuid.UUID(lace), {})
    client.portal.call(_wait_for_status, run.id, {"completed"})
    turns = client.portal.call(_wait_for_turns, lace, 1)

    assert set(seen) == {"Rival", "Quiet"}  # dismissed firms are not checked
    assert run.id and client.portal.call(_runs, lace, "lace_monitor")[0].progress == {"checked": 2, "changes": 1}
    [update] = turns[-1].input["updates"]
    assert "Cut Pro to $8" in update and "Lead with migration help" in update and "meme" not in update
    with psycopg.connect(settings.database_url) as conn:
        states = conn.execute("SELECT name, monitor_state, last_checked_at IS NOT NULL FROM lace_competitors"
                              " WHERE status = 'tracked' ORDER BY name").fetchall()
        facts = conn.execute("SELECT claim, origin, source_url FROM lace_facts WHERE topic = 'competition'").fetchall()
    assert states == [("Quiet", {"site_hash": "h-Quiet"}, True), ("Rival", {"site_hash": "h-Rival"}, True)]
    assert facts == [("Rival: Cut Pro to $8. Undercuts our Basic plan.", "monitor", "https://rival.test/pricing")]
    assert client.get(f"{API}/laces/{lace}/messages").json()[-1]["content"] == "Rival cut its Pro plan to $8."


def test_nothing_material_means_nothing_said(client, lace, lace_runtime, checks, user):  # noqa: F811
    _competitor(lace, "Rival")
    checks[1]["Rival"] = [MEME]
    run = client.portal.call(manager.start_lace_job, "lace_monitor", user.id, uuid.UUID(lace), {})
    client.portal.call(_wait_for_status, run.id, {"completed"})
    assert client.portal.call(_runs, lace, "lace_turn") == []


def test_the_previous_baseline_is_passed_back(client, lace, lace_runtime, checks, user):  # noqa: F811
    rival = _competitor(lace, "Rival")
    with psycopg.connect(settings.database_url, autocommit=True) as conn:
        conn.execute("UPDATE lace_competitors SET monitor_state = '{\"site_hash\": \"old\"}' WHERE id = %s", (rival,))
    run = client.portal.call(manager.start_lace_job, "lace_monitor", user.id, uuid.UUID(lace), {})
    client.portal.call(_wait_for_status, run.id, {"completed"})
    assert checks[0]["Rival"] == {"site_hash": "old"}


def test_scheduler_checks_laces_with_stale_competitors(client, lace, lace_runtime, checks, user):  # noqa: F811
    fresh = datetime.now(UTC) - timedelta(hours=1)
    stale = datetime.now(UTC) - timedelta(hours=settings.monitor_max_age_h + 1)
    rival = _competitor(lace, "Rival", checked=fresh)
    assert client.portal.call(scheduler.sweep_laces) == 0  # checked recently
    with psycopg.connect(settings.database_url, autocommit=True) as conn:
        conn.execute("UPDATE lace_competitors SET last_checked_at = %s WHERE id = %s", (stale, rival))
    assert client.portal.call(scheduler.sweep_laces) == 1
    # One already in flight: the next sweep leaves it alone.
    assert client.portal.call(scheduler.sweep_laces) == 0
    [run] = client.portal.call(_runs, lace, "lace_monitor")
    client.portal.call(_wait_for_status, run.id, {"completed"})


def test_scheduler_skips_laces_with_nothing_to_watch(client, lace, lace_runtime, checks):  # noqa: F811
    _competitor(lace, "Gone", status="dismissed")
    assert client.portal.call(scheduler.sweep_laces) == 0
