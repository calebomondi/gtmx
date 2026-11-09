"""Each Lace's copy of the founder's CRM: read whole from Zoho or HubSpot
(through a stubbed Composio, in their documented shapes), each record with
where it stands, kept with its match keys, refreshed a batch at a time, and
left as it was when the CRM can't be read."""

import uuid
from datetime import UTC, datetime, timedelta

import psycopg

from agents.lace.apps import AppError
from backend.app.database.connect import AsyncSessionLocal
from backend.app.runs import scheduler
from backend.app.services import connections as connection_service
from backend.app.services import crm_sync, lace_apps
from backend.tests.helpers import stub_accounts
from backend.tests.test_lace_apps import _lace
from backend.tests.test_social_actions import composio  # noqa: F401 -- fixture
from config import settings

ZOHO = {
    "Accounts": [{"Account_Name": "Acme Clinics", "Website": "www.acmeclinics.test"}],
    "Deals": [{"Deal_Name": "Acme rollout", "Stage": "Closed Won", "Account_Name": {"name": "Acme Clinics"}},
              {"Deal_Name": "Beta pilot", "Stage": "Negotiation", "Account_Name": {"name": "Beta Health"}},
              {"Deal_Name": "Gamma", "Stage": "Closed Lost", "Account_Name": {"name": "Gamma"}}],
    "Contacts": [{"Full_Name": "Ada Lovelace", "Email": "ADA@acmeclinics.test", "Account_Name": {"name": "Acme Clinics"}}],
    "Leads": [{"Full_Name": "Joe Kamau", "Company": "Kamau Farms", "Email": "joe@gmail.com"}],
}


def _zoho(monkeypatch):
    stub_accounts(monkeypatch, {"zoho"})

    def execute(entity, tool, arguments, connection_id):
        assert tool == "ZOHO_GET_ZOHO_RECORDS"
        return {"data": {"data": ZOHO[arguments["module_api_name"]]}, "error": None, "log_id": "l"}
    monkeypatch.setattr(connection_service, "execute_tool", execute)


async def test_zoho_is_read_whole_with_where_each_stands(monkeypatch):
    _zoho(monkeypatch)
    crm, records = await lace_apps.DbLaceApps(AsyncSessionLocal, _lace()).crm_snapshot()
    assert crm == "zoho"
    assert [(r["kind"], r["company"], r["status"], r["stage"]) for r in records] == [
        ("company", "Acme Clinics", "known", None),
        ("company", "Acme Clinics", "customer", "Closed Won"),
        ("company", "Beta Health", "open_deal", "Negotiation"),
        ("company", "Gamma", "known", "Closed Lost"),
        ("person", "Acme Clinics", "known", None),
        ("person", "Kamau Farms", "lead", "Lead"),
    ]
    assert records[4]["email"] == "ada@acmeclinics.test"


async def test_hubspot_is_read_by_lifecycle_stage_page_by_page(composio, monkeypatch):  # noqa: F811
    stub_accounts(monkeypatch, {"hubspot"})
    pages = {
        ("HUBSPOT_LIST_COMPANIES", None): {"results": [{"properties": {"name": "Acme", "domain": "acme.test",
                                                                       "lifecyclestage": "customer"}}],
                                           "paging": {"next": {"after": "2"}}},
        ("HUBSPOT_LIST_COMPANIES", "2"): {"results": [{"properties": {"name": "Beta", "lifecyclestage": "opportunity"}}]},
        ("HUBSPOT_LIST_CONTACTS", None): {"results": [{"properties": {"firstname": "Ann", "lastname": "Wise",
                                                                      "email": "ann@beta.test", "lifecyclestage": "lead"}}]},
    }

    def execute(entity, tool, arguments, connection_id):
        return {"data": pages[(tool, arguments.get("after"))], "error": None, "log_id": "l"}
    monkeypatch.setattr(connection_service, "execute_tool", execute)
    crm, records = await lace_apps.DbLaceApps(AsyncSessionLocal, _lace()).crm_snapshot()
    assert crm == "hubspot"
    assert [(r["kind"], r["name"] or r["company"], r["status"]) for r in records] == [
        ("company", "Acme", "customer"), ("company", "Beta", "open_deal"), ("person", "Ann Wise", "lead")]


def test_records_are_kept_with_their_match_keys():
    now = datetime.now(UTC)
    rows = crm_sync.rows_for(uuid.uuid4(), "zoho", [
        {"kind": "company", "status": "customer", "company": "Acme Clinics Ltd.", "website": "https://www.acme.test/about"},
        {"kind": "person", "status": "known", "name": "Ada", "company": None, "email": "ada@acme.test"},
        {"kind": "person", "status": "lead", "name": "Joe", "company": "Kamau Farms", "email": "joe@gmail.com"},
        {"kind": "person", "status": "known", "name": "Nobody"},  # nothing to match by
        {"kind": "company", "status": "open_deal", "company": "ACME Clinics Ltd", "stage": "Negotiation"},
    ], now)
    assert [(r.domain, r.company_key, r.email) for r in rows] == [
        ("acme.test", "acmeclinicsltd", None), ("acme.test", None, "ada@acme.test"),
        (None, "kamaufarms", "joe@gmail.com"),  # free mail says nothing about the company
        ("acme.test", "acmeclinicsltd", None)]  # a deal takes its company's site


def _records(lace_id) -> list[tuple]:
    with psycopg.connect(settings.database_url) as conn:
        return conn.execute("SELECT crm, kind, status, domain FROM lace_crm_records WHERE lace_id = %s ORDER BY kind,"
                            " status", (lace_id,)).fetchall()


def _synced_at(lace_id):
    with psycopg.connect(settings.database_url) as conn:
        return conn.execute("SELECT crm_synced_at FROM laces WHERE id = %s", (lace_id,)).fetchone()[0]


def _active_lace():
    lace_id = _lace()
    with psycopg.connect(settings.database_url, autocommit=True) as conn:
        conn.execute("UPDATE laces SET status = 'active' WHERE id = %s", (lace_id,))
    return lace_id


def test_a_sync_replaces_the_copy_and_a_failed_read_keeps_it(client, monkeypatch):
    lace_id = _active_lace()
    _zoho(monkeypatch)
    assert client.portal.call(crm_sync.sync_lace, lace_id) == 6
    first = _synced_at(lace_id)
    assert ("zoho", "company", "customer", "acmeclinics.test") in _records(lace_id)

    async def broken(self):
        raise AppError("Zoho CRM refused the request.")
    monkeypatch.setattr(lace_apps.DbLaceApps, "crm_snapshot", broken)
    assert client.portal.call(crm_sync.sync_lace, lace_id) is None
    assert len(_records(lace_id)) == 6 and _synced_at(lace_id) == first

    async def none(self):
        return None
    monkeypatch.setattr(lace_apps.DbLaceApps, "crm_snapshot", none)
    assert client.portal.call(crm_sync.sync_lace, lace_id) == 0  # the CRM was disconnected
    assert _records(lace_id) == [] and _synced_at(lace_id) > first


def test_the_sweep_refreshes_due_copies_a_batch_at_a_time(client, monkeypatch):
    laces = [_active_lace() for _ in range(3)]
    with psycopg.connect(settings.database_url, autocommit=True) as conn:
        conn.execute("UPDATE laces SET crm_synced_at = %s WHERE id = %s", (datetime.now(UTC), laces[2]))  # fresh
    synced: list = []

    async def sync(lace_id, now=None):
        synced.append(lace_id)
        return 0
    monkeypatch.setattr(crm_sync, "sync_lace", sync)
    monkeypatch.setattr(settings, "crm_sync_batch", 1)
    assert client.portal.call(scheduler.sync_crms) == 1
    assert synced[0] in laces[:2]
    later = datetime.now(UTC) + timedelta(hours=settings.crm_sync_every_h + 1)
    synced.clear()
    monkeypatch.setattr(settings, "crm_sync_batch", 10)
    client.portal.call(scheduler.sync_crms, later)
    assert set(laces) <= set(synced)
