"""Leads already in the founder's CRM: matched against the Lace's copy of it
by domain, company name or a person's email; labelled with where they stand;
a customer there is a customer here and an open deal is warm; and a cold first
email is never drafted to a customer or an open deal unless the founder
confirms."""

import uuid

import psycopg
from langchain_core.messages import AIMessage

from agents.schemas.accounts import AccountRecord, ContactRecord, TriggerEvent
from backend.app.database.connect import AsyncSessionLocal
from backend.app.runs import manager
from backend.app.services import crm_match, lace_accounts
from backend.tests.test_lace_jobs import _wait_for_turns, lace  # noqa: F401 -- fixture
from backend.tests.test_lace_outreach import _account, _stub_writer
from backend.tests.test_laces_api import lace_runtime  # noqa: F401 -- fixture
from backend.tests.test_runs import _wait_for_status
from config import settings


def _crm(lace_id, *records: tuple) -> None:
    """(kind, status, stage, domain, company_key, email) rows in the Lace's CRM copy."""
    with psycopg.connect(settings.database_url, autocommit=True) as conn:
        conn.execute("DELETE FROM lace_crm_records WHERE lace_id = %s", (lace_id,))
        for kind, status, stage, domain, company_key, email in records:
            conn.execute("INSERT INTO lace_crm_records (id, lace_id, crm, kind, status, stage, domain, company_key,"
                         " email) VALUES (%s, %s, 'zoho', %s, %s, %s, %s, %s, %s)",
                         (uuid.uuid4(), lace_id, kind, status, stage, domain, company_key, email))


def _lead(account_id) -> tuple:
    with psycopg.connect(settings.database_url) as conn:
        return conn.execute("SELECT crm_status, crm_stage, temperature, temperature_reason FROM lace_accounts"
                            " WHERE id = %s", (account_id,)).fetchone()


async def _match(lace_id) -> int:
    async with AsyncSessionLocal() as db, db.begin():
        return await crm_match.match_accounts(db, uuid.UUID(lace_id))


def test_leads_in_the_crm_are_labelled_and_warmed(client, lace):  # noqa: F811
    by_site = _account(lace, "Alpha", [])                                  # alpha.test
    by_name = _account(lace, "Beta Health", [])                            # betahealth
    by_email = _account(lace, "Gamma", [ContactRecord(name="Gina", email="gina@gamma-group.test")])
    lead_only = _account(lace, "Delta", [])
    stranger = _account(lace, "Epsilon", [])
    _crm(lace, ("company", "known", None, "alpha.test", "alpha", None),
         ("company", "customer", "Closed Won", "alpha.test", "alpha", None),
         ("company", "open_deal", "Negotiation", None, "betahealth", None),
         ("person", "known", None, None, None, "gina@gamma-group.test"),
         ("person", "lead", "Lead", "delta.test", "delta", "d@delta.test"))
    assert client.portal.call(_match, lace) == 4
    assert _lead(by_site) == ("customer", "Closed Won", "customer", "A customer in your CRM")
    assert _lead(by_name) == ("open_deal", "Negotiation", "warm", "Open deal in your CRM (Negotiation)")
    assert _lead(by_email) == ("known", None, "cold", None)  # on file, but nothing about warmth
    assert _lead(lead_only) == ("lead", "Lead", "cold", None)
    assert _lead(stranger) == (None, None, "cold", None)

    # Gone from the CRM: the label goes, the temperature it earned stays.
    _crm(lace)
    client.portal.call(_match, lace)
    assert _lead(by_name) == (None, None, "warm", "Open deal in your CRM (Negotiation)")


async def _save_found(lace_id, name, website):
    record = AccountRecord(name=name, website=website,
                           trigger_event=TriggerEvent(event="Raised", signal_type="funding_round", source="https://n.test"))
    async with AsyncSessionLocal() as db, db.begin():
        await lace_accounts.upsert_found(db, uuid.UUID(lace_id), None, [(record, None)])


def test_a_search_find_already_in_the_crm_says_so(client, lace):  # noqa: F811
    _crm(lace, ("company", "customer", "Closed Won", "zeta.test", "zeta", None))
    client.portal.call(_save_found, lace, "Zeta", "https://www.zeta.test")
    with psycopg.connect(settings.database_url) as conn:
        assert conn.execute("SELECT status, crm_status, temperature FROM lace_accounts WHERE name = 'Zeta'"
                            ).fetchone() == ("suggested", "customer", "customer")


def test_no_cold_email_to_a_customer_or_open_deal_unless_confirmed(client, lace, lace_runtime, user,  # noqa: F811
                                                                   monkeypatch):
    written = _stub_writer(monkeypatch)
    customer = _account(lace, "Alpha", [ContactRecord(name="Jane", email="jane@alpha.test")])
    _account(lace, "Omega", [ContactRecord(name="Olu", email="olu@omega.test")])
    _crm(lace, ("company", "customer", "Closed Won", "alpha.test", "alpha", None))
    client.portal.call(_match, lace)
    lace_runtime.extend(AIMessage(content="Noted.") for _ in range(3))

    # Picked automatically: the customer isn't even considered.
    run = client.portal.call(manager.start_lace_job, "lace_drafts", user.id, uuid.UUID(lace), {})
    client.portal.call(_wait_for_status, run.id, {"completed"})
    assert [w[0] for w in written] == ["Omega"]

    # Named: skipped and said, so the Lace can ask the founder.
    run = client.portal.call(manager.start_lace_job, "lace_drafts", user.id, uuid.UUID(lace),
                             {"account_ids": [str(customer)]})
    client.portal.call(_wait_for_status, run.id, {"completed"})
    update = client.portal.call(_wait_for_turns, lace, 2)[-1].input["updates"][0]
    assert "Alpha (a customer, Closed Won)" in update and [w[0] for w in written] == ["Omega"]

    # Confirmed by the founder: drafted.
    run = client.portal.call(manager.start_lace_job, "lace_drafts", user.id, uuid.UUID(lace),
                             {"account_ids": [str(customer)], "crm_confirmed": True})
    client.portal.call(_wait_for_status, run.id, {"completed"})
    assert [w[0] for w in written] == ["Omega", "Alpha"]


def test_each_sync_labels_the_leads_again(client, lace, monkeypatch):  # noqa: F811
    from backend.app.services import crm_sync
    from backend.tests.test_crm_sync import _zoho

    beta = _account(lace, "Beta Health", [])
    _zoho(monkeypatch)  # Beta Health has an open deal at Negotiation
    client.portal.call(crm_sync.sync_lace, uuid.UUID(lace))
    assert _lead(beta)[:3] == ("open_deal", "Negotiation", "warm")
