"""Watching what applies: each Lace with a confirmed jurisdiction searches
again weekly, tracked Kenyan bills are re-read daily from one read of the
tracker, a bill that moved reaches the Feed (or the member's own chat), and
the brief carries all of it."""

import uuid
from datetime import UTC, datetime, timedelta

import psycopg
from langchain_core.messages import AIMessage
from sqlalchemy import select

from backend.app.database.connect import AsyncSessionLocal
from backend.app.database.lace_models import LaceActivity, LaceEvent, LaceRegulation
from backend.app.runs import manager, scheduler
from backend.app.services import lace_briefs
from backend.tests.helpers import make_user
from backend.tests.test_lace_jobs import _runs, lace  # noqa: F401 -- fixture
from backend.tests.test_lace_regulations import ODPC, _found, _stub
from backend.tests.test_laces_api import lace_runtime  # noqa: F401 -- fixture
from backend.tests.test_runs import _wait_for_status
from config import settings
from data_sources.legislation import mzalendo
from data_sources.legislation.mzalendo import BillStatus, MzalendoError

WANJIRU = make_user("Wanjiru")
NA = "https://kenyalaw.org/akn/ke/bill/na/2026-04-10/the-value-added-tax-amendment-bill-2026/eng@2026-04-10"
SENATE = "https://kenyalaw.org/akn/ke/bill/senate/2026-02-19/the-artificial-intelligence-bill-2026/eng@2026-02-19"


def _sql(query: str, *args) -> None:
    with psycopg.connect(settings.database_url, autocommit=True) as conn:
        conn.execute(query, args)


def _bill(lace_id, title, url, stage=None, owner_id=None, status="tracked", jurisdiction="KE", checked=None):
    _sql("INSERT INTO lace_regulations (id, lace_id, owner_id, kind, title, jurisdiction, url, url_key, stage, status,"
         " last_checked_at, why_it_applies) VALUES (%s, %s, %s, 'bill', %s, %s, %s, %s, %s, %s, %s, 'We sell online.')",
         uuid.uuid4(), lace_id, owner_id, title, jurisdiction, url, url + "#k", stage, status, checked)


def _tracker(monkeypatch, rows=None, error=None):
    calls = []

    def stages(houses):
        calls.append(houses)
        if error:
            raise error
        return rows or []
    monkeypatch.setattr(mzalendo, "bill_stages", stages)
    return calls


def _row(title, year, house, stage):
    return BillStatus(title=title, year=year, house=house, stage=stage, url="https://mzalendo.com/x")


async def _read(lace_id):
    async with AsyncSessionLocal() as db:
        bills = {b.title: b for b in (await db.scalars(select(LaceRegulation).where(
            LaceRegulation.lace_id == uuid.UUID(lace_id)))).all()}
        feed = (await db.scalars(select(LaceActivity).where(LaceActivity.lace_id == uuid.UUID(lace_id),
                                                            LaceActivity.kind == "bill_moved"))).all()
        events = (await db.scalars(select(LaceEvent).where(LaceEvent.lace_id == uuid.UUID(lace_id)))).all()
    return bills, [a.title for a in feed], [(e.owner_id, e.text) for e in events]


def test_a_tracked_bill_that_moves_reaches_the_feed(client, lace, monkeypatch):  # noqa: F811
    _bill(lace, "The Value Added Tax (Amendment) Bill, 2026", NA, stage="first_reading")
    _bill(lace, "The Artificial Intelligence Bill, 2026", SENATE)                        # stage not read yet
    calls = _tracker(monkeypatch, [
        _row("The Value Added Tax (amendment) Bill", 2026, "National Assembly", "assented"),
        _row("The Value Added Tax (Amendment) Bill", 2025, "National Assembly", "second_reading"),  # last year's
        _row("The Artificial Intelligence Bill 2026", 2026, "Senate", "first_reading"),
    ])
    assert client.portal.call(scheduler.check_bills) == 1
    assert calls == [["National Assembly", "Senate"]]
    bills, feed, _ = client.portal.call(_read, lace)
    assert bills["The Value Added Tax (Amendment) Bill, 2026"].stage == "assented"
    assert bills["The Artificial Intelligence Bill, 2026"].stage == "first_reading"  # recorded quietly
    assert feed == ["The Value Added Tax (Amendment) Bill, 2026 was signed into law"]
    assert all(b.last_checked_at for b in bills.values())

    assert client.portal.call(scheduler.check_bills) == 0  # checked within the day: no read at all
    assert len(calls) == 1


def test_only_tracked_kenyan_bills_still_moving_are_read(client, lace, monkeypatch):  # noqa: F811
    _bill(lace, "Suggested", NA, status="suggested")
    _bill(lace, "Elsewhere", "https://www.legislation.gov.uk/bill", jurisdiction="GB")
    _bill(lace, "Signed", NA + "/s", stage="assented")
    _bill(lace, "Read today", NA + "/r", checked=datetime.now(UTC) - timedelta(hours=1))
    calls = _tracker(monkeypatch)
    assert client.portal.call(scheduler.check_bills) == 0 and calls == []


def test_a_members_bill_moves_in_their_own_chat(client, lace, monkeypatch):  # noqa: F811
    _bill(lace, "The Artificial Intelligence Bill, 2026", SENATE, stage="first_reading", owner_id=WANJIRU.id)
    calls = _tracker(monkeypatch, [_row("The Artificial Intelligence Bill 2026", 2026, "Senate", "second_reading")])
    assert client.portal.call(scheduler.check_bills) == 1 and calls == [["Senate"]]
    _, feed, events = client.portal.call(_read, lace)
    assert feed == []
    [(owner, text)] = events
    assert owner == WANJIRU.id and "reached second reading" in text


def test_an_unreadable_tracker_is_tried_again_next_sweep(client, lace, monkeypatch):  # noqa: F811
    _bill(lace, "The Value Added Tax (Amendment) Bill, 2026", NA, stage="first_reading")
    calls = _tracker(monkeypatch, error=MzalendoError("down"))
    assert client.portal.call(scheduler.check_bills) == 0
    bills, _, _ = client.portal.call(_read, lace)
    assert bills["The Value Added Tax (Amendment) Bill, 2026"].last_checked_at is None
    client.portal.call(scheduler.check_bills)
    assert len(calls) == 2


def test_a_lace_searches_again_weekly_once_confirmed(client, lace, lace_runtime, user, monkeypatch):  # noqa: F811
    _stub(monkeypatch, [])
    assert client.portal.call(scheduler.sweep_lace_regulations) == 0  # no confirmed jurisdiction
    _sql("UPDATE laces SET registered_in = 'KE', jurisdiction_confirmed_at = now() WHERE id = %s", lace)
    assert client.portal.call(scheduler.sweep_lace_regulations) == 1
    [run] = client.portal.call(_runs, lace, "lace_regulations")
    client.portal.call(_wait_for_status, run.id, {"completed"})
    assert client.portal.call(scheduler.sweep_lace_regulations) == 0  # just searched
    _sql("UPDATE runs SET created_at = %s WHERE id = %s",
         datetime.now(UTC) - timedelta(hours=settings.regulation_search_every_h + 1), run.id)
    assert client.portal.call(scheduler.sweep_lace_regulations) == 1
    for r in client.portal.call(_runs, lace, "lace_regulations"):
        client.portal.call(_wait_for_status, r.id, {"completed"})
    assert client.portal.call(_runs, lace, "lace_turn") == []  # nothing new: the Lace isn't woken


async def test_the_brief_carries_regulations(lace):  # noqa: F811
    lace_id = uuid.UUID(lace)
    today = datetime.now(UTC).date()
    _sql("INSERT INTO lace_regulations (id, lace_id, kind, title, jurisdiction, url, url_key, status, next_date,"
         " what_to_do) VALUES (%s, %s, 'obligation', 'VAT monthly return', 'KE', 'https://kra.go.ke/vat',"
         " 'kra.go.ke/vat', 'tracked', %s, 'File on iTax.')", uuid.uuid4(), lace_id, today + timedelta(days=3))
    _sql("INSERT INTO lace_regulations (id, lace_id, kind, title, jurisdiction, url, url_key, status) VALUES"
         " (%s, %s, 'law', 'Hidden', 'KE', 'https://x.go.ke', 'x.go.ke', 'dismissed')", uuid.uuid4(), lace_id)
    _sql("INSERT INTO lace_activity (id, lace_id, kind, title) VALUES (%s, %s, 'bill_moved',"
         " 'The Tax Laws (Amendment) Bill, 2026 reached second reading')", uuid.uuid4(), lace_id)
    async with AsyncSessionLocal() as db:
        text = await lace_briefs.digest(db, lace_id, datetime.now(UTC) - timedelta(days=1), today)
    assert "Tracked bills that moved:\n- The Tax Laws (Amendment) Bill, 2026 reached second reading" in text
    assert "New laws and regulations that apply:\n- [obligation, KE] VAT monthly return (https://kra.go.ke/vat)" in text
    assert f"Compliance dates within a week:\n- VAT monthly return: {(today + timedelta(days=3)).isoformat()}" in text
    assert "Hidden" not in text


def test_a_search_that_finds_new_ones_goes_on_the_feed(client, lace, lace_runtime, user, monkeypatch):  # noqa: F811
    _sql("UPDATE laces SET registered_in = 'KE', jurisdiction_confirmed_at = now() WHERE id = %s", lace)
    _stub(monkeypatch, _found(("law", "The Data Protection Act, 2019", ODPC, None, "strong")))
    lace_runtime.append(AIMessage(content="Found one."))
    run = client.portal.call(manager.start_lace_job, "lace_regulations", user.id, uuid.UUID(lace), {})
    client.portal.call(_wait_for_status, run.id, {"completed"})

    async def feed():
        async with AsyncSessionLocal() as db:
            return (await db.scalars(select(LaceActivity).where(LaceActivity.lace_id == uuid.UUID(lace),
                                                                LaceActivity.kind == "regulations_found"))).all()
    [item] = client.portal.call(feed)
    assert item.title == "Found 1 law or regulation that applies" and "Data Protection Act" in item.summary
