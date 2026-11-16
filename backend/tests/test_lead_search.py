"""The daily lead search: each active Lace with an ideal customer profile,
past its first day, gets a search a day on its own; its new finds wait for
the founder to review, and a search that finds nothing new says nothing."""

from datetime import UTC, datetime, timedelta

import psycopg
from langchain_core.messages import AIMessage

from agents.schemas.accounts import AccountFit, AccountRecord, TriggerEvent
from agents.schemas.icp import ICP
from backend.app.runs import lace_jobs, scheduler
from backend.tests.test_lace_jobs import _runs, _wait_for_turns, lace  # noqa: F401 -- fixture
from backend.tests.test_laces_api import lace_runtime  # noqa: F401 -- fixture
from backend.tests.test_runs import _wait_for_status
from config import settings

FIT = AccountFit(need="Payroll", capability="Multi-site payroll", payoff="Time saved", angle="Congrats", strength="strong")


def _found(*names):
    return [(AccountRecord(name=n, website=f"https://{n.lower()}.test",
                           trigger_event=TriggerEvent(event="Raised", signal_type="funding_round", source="https://n.test")),
             FIT) for n in names]


def _ready(lace_id) -> None:
    with psycopg.connect(settings.database_url, autocommit=True) as conn:
        conn.execute("UPDATE laces SET status = 'active', icp = %s WHERE id = %s",
                     (ICP(buyer_type="b2b", industries=["Clinics"]).model_dump_json(), lace_id))


def test_a_lace_searches_for_leads_once_a_day(client, lace, lace_runtime, monkeypatch):  # noqa: F811
    results = [_found("Alpha", "Beta"), _found("Alpha", "Beta")]
    monkeypatch.setattr(lace_jobs, "find_accounts", lambda *a, **k: results.pop(0))
    lace_runtime.append(AIMessage(content="Two new leads to review."))
    _ready(lace)

    assert client.portal.call(scheduler.sweep_lace_leads) == 1
    [run] = client.portal.call(_runs, lace, "lace_accounts")
    run = client.portal.call(_wait_for_status, run.id, {"completed"})
    assert run.input == {"scheduled": True} and run.progress["new"] == 2
    with psycopg.connect(settings.database_url) as conn:
        assert {s for (s,) in conn.execute("SELECT status FROM lace_accounts WHERE lace_id = %s", (lace,))} == {
            "suggested"}  # they wait for the founder
    assert "Alpha" in client.portal.call(_wait_for_turns, lace, 1)[-1].input["updates"][0]
    assert client.portal.call(scheduler.sweep_lace_leads) == 0  # searched today

    # A day on: searched again; the same two leads are nothing new, so nothing is said.
    with psycopg.connect(settings.database_url, autocommit=True) as conn:
        conn.execute("UPDATE runs SET created_at = %s WHERE id = %s",
                     (datetime.now(UTC) - timedelta(hours=settings.lead_search_every_h + 1), run.id))
    assert client.portal.call(scheduler.sweep_lace_leads) == 1
    second = [r for r in client.portal.call(_runs, lace, "lace_accounts") if r.id != run.id][0]
    second = client.portal.call(_wait_for_status, second.id, {"completed"})
    assert second.progress["new"] == 0
    with psycopg.connect(settings.database_url) as conn:
        assert conn.execute("SELECT count(*) FROM lace_events WHERE run_id = %s", (second.id,)).fetchone()[0] == 0


def test_no_search_without_an_icp_or_on_the_first_day(client, lace):  # noqa: F811
    with psycopg.connect(settings.database_url, autocommit=True) as conn:
        conn.execute("UPDATE laces SET status = 'active' WHERE id = %s", (lace,))
    assert client.portal.call(scheduler.sweep_lace_leads) == 0  # no ICP yet
    _ready(lace)
    with psycopg.connect(settings.database_url, autocommit=True) as conn:
        conn.execute("UPDATE laces SET created_at = now() WHERE id = %s", (lace,))
    assert client.portal.call(scheduler.sweep_lace_leads) == 0  # its first day
    assert client.portal.call(_runs, lace, "lace_accounts") == []
