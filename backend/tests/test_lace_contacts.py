"""Contact search for a Lace's accounts: who can be reached, saved per
account, reported honestly, and kept when the account is found again."""

import json
import uuid

import psycopg
from langchain_core.messages import AIMessage
from sqlalchemy import update

from agents.schemas.accounts import AccountRecord, ContactRecord, TriggerEvent
from backend.app.database.connect import AsyncSessionLocal
from backend.app.database.lace_models import LaceAccount
from backend.app.runs import lace_jobs
from backend.app.runs import manager
from backend.app.services import lace_accounts
from backend.tests.test_lace_jobs import _wait_for_turns, lace  # noqa: F401 -- fixture
from backend.tests.test_laces_api import API, lace_runtime  # noqa: F401 -- fixture
from backend.tests.test_runs import _wait_for_status
from config import settings


def _record(name: str, **kw) -> AccountRecord:
    return AccountRecord(name=name, website=f"https://{name.lower()}.test",
                         trigger_event=TriggerEvent(event="Hiring", signal_type="hiring_post", source="https://x.test"),
                         **kw)


def _account(lace_id, name: str, checked: bool = False) -> uuid.UUID:
    with psycopg.connect(settings.database_url, autocommit=True) as conn:
        return conn.execute(
            "INSERT INTO lace_accounts (id, lace_id, key, name, account_type, record, contacts_checked_at)"
            " VALUES (%s, %s, %s, %s, 'company', %s, %s) RETURNING id",
            (uuid.uuid4(), lace_id, f"{name.lower()}.test", name, json.dumps(_record(name).model_dump(mode="json")),
             "2026-10-01T00:00:00Z" if checked else None),
        ).fetchone()[0]


def _fake_search(monkeypatch):
    searched = []

    def complete(record, titles, cfg):
        searched.append(record.name)
        if record.name == "Alpha":
            return record.model_copy(update={"key_contacts": [
                ContactRecord(name="Jane Doe", title="COO", email="jane@alpha.test")]})
        if record.name == "Beta":
            return record.model_copy(update={"socials": {"x": "https://x.com/beta"}})
        return record

    monkeypatch.setattr(lace_jobs, "complete_contacts", complete)
    return searched


def test_contacts_are_found_saved_and_reported(client, lace, lace_runtime, user, monkeypatch):  # noqa: F811
    searched = _fake_search(monkeypatch)
    for name in ("Alpha", "Beta", "Gamma"):
        _account(lace, name)
    _account(lace, "Done", checked=True)
    lace_runtime.append(AIMessage(content="Jane Doe is the COO at Alpha."))

    run = client.portal.call(manager.start_lace_job, "lace_contacts", user.id, uuid.UUID(lace), {})
    run = client.portal.call(_wait_for_status, run.id, {"completed"})
    turns = client.portal.call(_wait_for_turns, lace, 1)

    assert sorted(searched) == ["Alpha", "Beta", "Gamma"]  # "Done" was searched before
    assert run.progress == {"searched": 3, "person": 1, "organisation": 1, "none": 1}
    update = turns[-1].input["updates"][0]
    assert "Alpha: Jane Doe (COO): jane@alpha.test" in update
    assert "Beta: no named person found; reachable through x" in update
    assert "Gamma: could not find anyone to contact" in update
    accounts = {a["name"]: a for a in client.get(f"{API}/laces/{lace}/accounts").json()}
    assert accounts["Alpha"]["contact_status"] == "person"
    assert accounts["Alpha"]["contacts"] == [{"name": "Jane Doe", "title": "COO", "email": "jane@alpha.test",
                                              "linkedin": None}]
    assert accounts["Beta"]["channels"] == {"x": "https://x.com/beta"} and accounts["Gamma"]["contact_status"] == "none"
    assert accounts["Alpha"]["contacts_checked_at"]
    assert accounts["Done"]["contacts_checked_at"].startswith("2026-10-01")  # untouched


def test_named_accounts_are_searched_even_if_searched_before(client, lace, lace_runtime, user, monkeypatch):  # noqa: F811
    searched = _fake_search(monkeypatch)
    done = _account(lace, "Done", checked=True)
    _account(lace, "Other")
    lace_runtime.append(AIMessage(content="Nothing new at Done."))
    run = client.portal.call(manager.start_lace_job, "lace_contacts", user.id, uuid.UUID(lace),
                             {"account_ids": [str(done), "not-an-id"]})
    client.portal.call(_wait_for_status, run.id, {"completed"})
    assert searched == ["Done"]


async def test_finding_an_account_again_keeps_its_contacts(lace):  # noqa: F811
    lace_id = uuid.UUID(lace)
    with psycopg.connect(settings.database_url, autocommit=True) as conn:
        user_id = conn.execute("SELECT user_id FROM laces WHERE id = %s", (lace_id,)).fetchone()[0]
        run_id = conn.execute("INSERT INTO runs (id, user_id, lace_id, kind, status) VALUES (%s, %s, %s,"
                              " 'lace_accounts', 'completed') RETURNING id", (uuid.uuid4(), user_id, lace_id)).fetchone()[0]
    async with AsyncSessionLocal() as db, db.begin():
        assert await lace_accounts.upsert_found(db, lace_id, run_id, [(_record("Alpha"), None)]) == (1, 0)
        # Contacts are searched for at accounts the founder saved.
        assert await lace_accounts.due_for_contacts(db, lace_id, None, 10) == []
        await db.execute(update(LaceAccount).where(LaceAccount.lace_id == lace_id).values(status="target"))
        [row] = await lace_accounts.due_for_contacts(db, lace_id, None, 10)
        await lace_accounts.save_contacts(db, row.id, _record("Alpha", key_contacts=[
            ContactRecord(name="Jane Doe", email="jane@alpha.test")], socials={"x": "https://x.com/alpha"}))
    async with AsyncSessionLocal() as db, db.begin():
        assert await lace_accounts.upsert_found(db, lace_id, run_id, [(_record("Alpha"), None)]) == (0, 1)
        [row] = await lace_accounts.list_for_lace(db, lace_id, "target", 10)
        assert row.contact_status == "person" and row.record["socials"] == {"x": "https://x.com/alpha"}
        assert [c["name"] for c in row.record["key_contacts"]] == ["Jane Doe"]
