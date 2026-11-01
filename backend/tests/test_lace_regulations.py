"""Regulations and the startup's jurisdictions: the database keeps codes,
kinds and bill stages to their known values, and one row per source page; a
founder confirms where the startup is; the search runs only then, and what it
finds waits for them to track or dismiss."""

import uuid

import pytest
from langchain_core.messages import AIMessage
from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError

from agents.schemas.regulations import Regulation
from backend.app.database.connect import AsyncSessionLocal
from backend.app.database.lace_models import Lace, LaceActivity, LaceRegulation
from backend.app.runs import manager, regulation_jobs
from backend.app.services.lace_store import DbLaceStore
from backend.tests.helpers import make_user
from backend.tests.test_lace_jobs import _wait_for_turns
from backend.tests.test_runs import _wait_for_status
from backend.tests.test_lace_jobs import lace  # noqa: F401 -- fixture
from backend.tests.test_laces_api import lace_runtime  # noqa: F401 -- fixture

VAT_BILL = {"kind": "bill", "title": "The Value Added Tax (Amendment) Bill, 2026", "jurisdiction": "KE",
            "url": "https://kenyalaw.org/akn/ke/bill/na/2026-04-10/vat-amendment-bill-2026",
            "url_key": "kenyalaw.org/akn/ke/bill/na/2026-04-10/vat-amendment-bill-2026", "stage": "first_reading"}


async def _add(lace_id: str, fields: dict | None = None) -> None:
    async with AsyncSessionLocal() as db:
        db.add(LaceRegulation(lace_id=uuid.UUID(lace_id), **{**VAT_BILL, **(fields or {})}))
        await db.commit()


async def _place(lace_id: str, registered_in: str | None, operates_in: list[str]) -> Lace:
    async with AsyncSessionLocal() as db:
        await db.execute(update(Lace).where(Lace.id == uuid.UUID(lace_id))
                         .values(registered_in=registered_in, operates_in=operates_in))
        await db.commit()
        return await db.get(Lace, uuid.UUID(lace_id))


def test_a_lace_starts_with_no_jurisdiction(client, lace):  # noqa: F811
    placed = client.portal.call(_place, lace, None, [])
    assert placed.registered_in is None and placed.operates_in == [] and placed.jurisdiction_confirmed_at is None


@pytest.mark.parametrize("code", ["KE", "US-DE", "GB-SCT"])
def test_iso_codes_are_kept(client, lace, code):  # noqa: F811
    placed = client.portal.call(_place, lace, code, ["KE", "NG"])
    assert placed.registered_in == code and placed.operates_in == ["KE", "NG"]


@pytest.mark.parametrize("code", ["Kenya", "ke", "K", "KE-"])
def test_anything_but_an_iso_code_is_refused(client, lace, code):  # noqa: F811
    with pytest.raises(IntegrityError):
        client.portal.call(_place, lace, code, [])
    with pytest.raises(IntegrityError):
        client.portal.call(_add, lace, {"jurisdiction": code})


def test_a_new_regulation_waits_for_the_founder(client, lace):  # noqa: F811
    client.portal.call(_add, lace)

    async def read():
        async with AsyncSessionLocal() as db:
            return (await db.execute(LaceRegulation.__table__.select())).one()
    row = client.portal.call(read)
    assert row.status == "suggested" and row.last_checked_at is None and row.owner_id is None


@pytest.mark.parametrize("field", [{"kind": "rule"}, {"stage": "debated"}, {"status": "open"}])
def test_unknown_kinds_stages_and_statuses_are_refused(client, lace, field):  # noqa: F811
    with pytest.raises(IntegrityError):
        client.portal.call(_add, lace, field)


def test_one_row_per_source_page(client, lace):  # noqa: F811
    client.portal.call(_add, lace)
    with pytest.raises(IntegrityError):
        client.portal.call(_add, lace, {"title": "The VAT (Amendment) Bill, 2026"})


WANJIRU = make_user("Wanjiru")
ODPC = "https://www.odpc.go.ke/registration"


def _store(lace_id: str, owner_id: uuid.UUID | None = None) -> DbLaceStore:
    return DbLaceStore(AsyncSessionLocal, uuid.UUID(lace_id), owner_id=owner_id)


def test_a_founder_confirms_where_the_startup_is(client, lace):  # noqa: F811
    store = _store(lace)
    assert not client.portal.call(store.jurisdiction).confirmed
    place = client.portal.call(store.set_jurisdiction, "KE", ["KE", "UG", "KE"])
    assert place.confirmed and place.registered_in == "KE" and place.operates_in == ["KE", "UG"]
    assert client.portal.call(store.jurisdiction) == place
    with pytest.raises(ValueError, match="Kenya"):
        client.portal.call(store.set_jurisdiction, "Kenya", [])
    assert client.portal.call(store.jurisdiction) == place


def _found(*items):
    return [Regulation(kind=k, title=t, jurisdiction="KE", url=u, stage=st, why_it_applies="It holds customer data.",
                       what_to_do="Register with the ODPC.", relevance=rel) for k, t, u, st, rel in items]


def _stub(monkeypatch, found):
    seen = {}

    def find(profile, facts, registered_in, operates_in, cfg):
        seen["places"] = (registered_in, operates_in)
        return found
    monkeypatch.setattr(regulation_jobs, "find_regulations", find)
    return seen


def _run(client, user, lace_id, params=None):
    run = client.portal.call(manager.start_lace_job, "lace_regulations", user.id, uuid.UUID(lace_id), params or {})
    return client.portal.call(_wait_for_status, run.id, {"completed", "failed"})


def test_the_search_waits_for_a_confirmed_jurisdiction(client, lace, lace_runtime, user, monkeypatch):  # noqa: F811
    _stub(monkeypatch, [])
    lace_runtime.append(AIMessage(content="Where are we registered?"))
    assert _run(client, user, lace).status == "failed"
    update_text = client.portal.call(_wait_for_turns, lace, 1)[-1].input["updates"][0]
    assert "set_jurisdiction" in update_text

    async def failed():
        async with AsyncSessionLocal() as db:
            return (await db.scalars(select(LaceActivity.kind).where(LaceActivity.lace_id == uuid.UUID(lace)))).all()
    assert "job_failed" in client.portal.call(failed)


def test_what_applies_is_saved_as_suggestions(client, lace, lace_runtime, user, monkeypatch):  # noqa: F811
    client.portal.call(_store(lace).set_jurisdiction, "KE", ["KE"])
    seen = _stub(monkeypatch, _found(
        ("law", "The Data Protection Act, 2019", ODPC, None, "strong"),
        ("bill", "The VAT (Amendment) Bill, 2026", VAT_BILL["url"], "first_reading", "moderate"),
        ("bill", "The Anti-Doping (Amendment) Bill, 2026", "https://kenyalaw.org/doping", None, "weak"),
    ))
    lace_runtime.append(AIMessage(content="Two apply."))
    run = _run(client, user, lace)
    assert run.status == "completed" and run.progress == {"found": 2, "new": 2, "refreshed": 0}
    assert seen["places"] == ("KE", ["KE"])
    update_text = client.portal.call(_wait_for_turns, lace, 1)[-1].input["updates"][0]
    assert update_text.index("VAT (Amendment)") < update_text.index("Data Protection")  # bills first
    assert "Anti-Doping" not in update_text and "not legal advice" in update_text

    store = _store(lace)
    suggested = client.portal.call(store.regulations, "suggested")
    assert {r.title for r in suggested} == {"The Data Protection Act, 2019", "The VAT (Amendment) Bill, 2026"}
    assert client.portal.call(store.regulations, "tracked") == []


def test_tracking_and_dismissal_stick_across_searches(client, lace, lace_runtime, user, monkeypatch):  # noqa: F811
    client.portal.call(_store(lace).set_jurisdiction, "KE", [])
    _stub(monkeypatch, _found(("law", "The Data Protection Act, 2019", ODPC, None, "strong"),
                              ("bill", "The VAT (Amendment) Bill, 2026", VAT_BILL["url"], "first_reading", "strong")))
    lace_runtime.extend([AIMessage(content="Found."), AIMessage(content="Again.")])
    _run(client, user, lace)
    store = _store(lace)
    by_title = {r.title: r.id for r in client.portal.call(store.regulations, "suggested")}
    changed = client.portal.call(store.set_regulations, [by_title["The Data Protection Act, 2019"], "nope"], "tracked")
    assert [c.name for c in changed.changed] == ["The Data Protection Act, 2019"] and changed.missing == ["nope"]
    client.portal.call(store.set_regulations, [by_title["The VAT (Amendment) Bill, 2026"]], "dismissed")

    async def advance_bill():
        async with AsyncSessionLocal() as db:
            await db.execute(update(LaceRegulation).where(LaceRegulation.lace_id == uuid.UUID(lace),
                                                          LaceRegulation.kind == "bill").values(stage="committee"))
            await db.commit()
    client.portal.call(advance_bill)
    client.portal.call(_wait_for_turns, lace, 1)
    assert _run(client, user, lace).progress["refreshed"] == 2
    assert [r.title for r in client.portal.call(store.regulations, "tracked")] == ["The Data Protection Act, 2019"]
    [dismissed] = client.portal.call(store.regulations, "dismissed")
    assert dismissed.stage == "committee"  # a search never sets a bill's stage back
    client.portal.call(_wait_for_turns, lace, 2)


def test_a_members_private_finds_stay_theirs(client, lace, lace_runtime, user, monkeypatch):  # noqa: F811
    client.portal.call(_store(lace).set_jurisdiction, "KE", [])
    _stub(monkeypatch, _found(("law", "The Data Protection Act, 2019", ODPC, None, "strong")))
    lace_runtime.append(AIMessage(content="Found."))
    _run(client, user, lace, {"private_to": str(WANJIRU.id)})
    client.portal.call(_wait_for_turns, lace, 1)
    assert client.portal.call(_store(lace).regulations, "suggested") == []
    [mine] = client.portal.call(_store(lace, WANJIRU.id).regulations, "suggested")
    assert client.portal.call(_store(lace).set_regulations, [mine.id], "tracked").missing == [mine.id]
