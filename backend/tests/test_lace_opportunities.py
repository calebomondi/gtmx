"""A Lace's opportunities: found in the background, saved per source page,
listed while open, dismissed for good, and searched again weekly."""

import uuid
from datetime import UTC, datetime, timedelta

import psycopg
from langchain_core.messages import AIMessage

from agents.schemas.opportunities import Opportunity
from backend.app.runs import lace_jobs, manager, scheduler
from backend.tests.helpers import make_user
from backend.tests.test_lace_jobs import _runs, _wait_for_turns, lace  # noqa: F401 -- fixture
from backend.tests.test_laces_api import API, lace_runtime  # noqa: F401 -- fixture
from backend.tests.test_runs import _wait_for_status
from config import settings

SOON = (datetime.now(UTC).date() + timedelta(days=20)).isoformat()
LATER = (datetime.now(UTC).date() + timedelta(days=60)).isoformat()


def _found(*items):
    return [Opportunity(kind=k, title=t, url=u, deadline=d, why_it_fits="Its buyers attend.", how_to_act="Apply now.")
            for k, t, u, d in items]


def _stub(monkeypatch, found):
    seen = {}

    def find(profile, facts, icp, cfg, kinds):
        seen["kinds"] = kinds
        return found
    monkeypatch.setattr(lace_jobs, "find_opportunities", find)
    return seen


def test_opportunities_are_found_listed_and_reported(client, lace, lace_runtime, user, monkeypatch):  # noqa: F811
    seen = _stub(monkeypatch, _found(("showcase", "Agritech Expo", "https://www.expo.test/2026/", LATER),
                                     ("sell", "IoT sensors tender", "https://tenders.test/iot", SOON)))
    lace_runtime.append(AIMessage(content="Two opportunities: a tender closing soon and an expo."))
    run = client.portal.call(manager.start_lace_job, "lace_opportunities", user.id, uuid.UUID(lace), {"kinds": ["sell", "bogus"]})
    run = client.portal.call(_wait_for_status, run.id, {"completed"})
    turns = client.portal.call(_wait_for_turns, lace, 1)

    assert seen["kinds"] == ["sell"]
    assert run.progress == {"found": 2, "new": 2, "refreshed": 0}
    update = turns[-1].input["updates"][0]
    assert update.index("IoT sensors tender") < update.index("Agritech Expo")  # soonest first
    listed = client.get(f"{API}/laces/{lace}/opportunities").json()
    assert [o["title"] for o in listed] == ["IoT sensors tender", "Agritech Expo"]
    assert listed[0]["deadline"] == SOON and listed[0]["how_to_act"] == "Apply now."


def test_closed_ones_are_hidden_and_dismissal_sticks(client, lace, lace_runtime, user, monkeypatch):  # noqa: F811
    with psycopg.connect(settings.database_url, autocommit=True) as conn:
        conn.execute("INSERT INTO lace_opportunities (id, lace_id, kind, title, url, url_key, deadline) VALUES"
                     " (%s, %s, 'sell', 'Closed tender', 'https://t.test/old', 't.test/old', %s)",
                     (uuid.uuid4(), lace, datetime.now(UTC).date() - timedelta(days=1)))
    _stub(monkeypatch, _found(("partner", "Reseller programme", "https://partner.test", None)))
    lace_runtime.extend([AIMessage(content="One."), AIMessage(content="Again.")])
    run = client.portal.call(manager.start_lace_job, "lace_opportunities", user.id, uuid.UUID(lace), {})
    client.portal.call(_wait_for_status, run.id, {"completed"})
    [open_one] = client.get(f"{API}/laces/{lace}/opportunities").json()
    assert open_one["title"] == "Reseller programme"
    client.patch(f"{API}/laces/{lace}/opportunities/{open_one['id']}", json={"status": "dismissed"})
    client.portal.call(_wait_for_turns, lace, 1)

    run = client.portal.call(manager.start_lace_job, "lace_opportunities", user.id, uuid.UUID(lace), {})
    run = client.portal.call(_wait_for_status, run.id, {"completed"})
    assert run.progress["refreshed"] == 1
    assert client.get(f"{API}/laces/{lace}/opportunities").json() == []
    assert [o["title"] for o in client.get(f"{API}/laces/{lace}/opportunities?status=dismissed").json()] == [
        "Reseller programme"]
    client.portal.call(_wait_for_turns, lace, 2)


def test_a_scheduled_search_with_nothing_new_stays_quiet(client, lace, lace_runtime, user, monkeypatch):  # noqa: F811
    _stub(monkeypatch, [])
    run = client.portal.call(manager.start_lace_job, "lace_opportunities", user.id, uuid.UUID(lace), {"scheduled": True})
    client.portal.call(_wait_for_status, run.id, {"completed"})
    assert client.portal.call(_runs, lace, "lace_turn") == []


def test_the_weekly_scan_picks_due_laces_with_an_icp(client, lace, lace_runtime, user, monkeypatch):  # noqa: F811
    _stub(monkeypatch, [])
    assert client.portal.call(scheduler.sweep_lace_opportunities) == 0  # no ICP yet
    with psycopg.connect(settings.database_url, autocommit=True) as conn:
        conn.execute("UPDATE laces SET icp = '{\"buyer_type\": \"b2b\"}' WHERE id = %s", (lace,))
    assert client.portal.call(scheduler.sweep_lace_opportunities) == 1
    [run] = client.portal.call(_runs, lace, "lace_opportunities")
    client.portal.call(_wait_for_status, run.id, {"completed"})
    assert client.portal.call(scheduler.sweep_lace_opportunities) == 0  # searched this week
    with psycopg.connect(settings.database_url, autocommit=True) as conn:
        conn.execute("UPDATE runs SET created_at = %s WHERE id = %s",
                     (datetime.now(UTC) - timedelta(days=settings.lace_opportunity_scan_days + 1), run.id))
    assert client.portal.call(scheduler.sweep_lace_opportunities) == 1
    for r in client.portal.call(_runs, lace, "lace_opportunities"):
        client.portal.call(_wait_for_status, r.id, {"completed"})


def test_opportunities_are_private(client, lace, lace_runtime):  # noqa: F811
    with psycopg.connect(settings.database_url, autocommit=True) as conn:
        oid = conn.execute("INSERT INTO lace_opportunities (id, lace_id, kind, title, url, url_key) VALUES"
                           " (%s, %s, 'sell', 'T', 'https://t.test', 't.test') RETURNING id", (uuid.uuid4(), lace)).fetchone()[0]
    client.sign_in(make_user("Intruder"))
    assert client.get(f"{API}/laces/{lace}/opportunities").status_code == 404
    assert client.patch(f"{API}/laces/{lace}/opportunities/{oid}", json={"status": "dismissed"}).status_code == 404
