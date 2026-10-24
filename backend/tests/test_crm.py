"""The founder's CRM through a stubbed Composio, as Zoho's documented
response shapes: deals and lookups for the Lace, and a lead they approve."""

import pytest

from backend.app.database.connect import AsyncSessionLocal
from backend.app.services import connections as connection_service
from backend.app.services import crm_actions, lace_apps
from backend.app.services.lace_app_actions import ActionFailed
from backend.tests.helpers import stub_accounts
from backend.tests.test_lace_apps import _lace
from backend.tests.test_social_actions import _ctx, composio  # noqa: F401 -- fixture



async def test_zoho_deals_read_in_one_shape(composio, monkeypatch):  # noqa: F811
    stub_accounts(monkeypatch, {"zoho"})
    composio["answers"] = {"ZOHO_GET_ZOHO_RECORDS": {"data": [
        {"Deal_Name": "Alpha", "Stage": "Closed Won", "Amount": 1200, "Closing_Date": "2026-10-01",
         "Account_Name": {"name": "Alpha Ltd", "id": "1"}, "Modified_Time": "2026-10-02T10:00:00+03:00"},
        {"Deal_Name": "Beta", "Stage": "Qualification", "Amount": None},
    ]}}
    apps = lace_apps.DbLaceApps(AsyncSessionLocal, _lace())
    assert await apps.crm() == "zoho"
    assert await apps.crm_deals() == [
        {"name": "Alpha", "company": "Alpha Ltd", "stage": "Closed Won", "amount": 1200.0, "close_date": "2026-10-01",
         "updated": "2026-10-02T10:00:00+03:00", "closed": True, "won": True},
        {"name": "Beta", "company": None, "stage": "Qualification", "amount": None, "close_date": None,
         "updated": None, "closed": False, "won": False}]
    assert composio["calls"][0][1]["module_api_name"] == "Deals"
    assert len(composio["calls"]) == 1  # a short page is the last


async def test_zoho_lookup_matches_leads_contacts_and_companies(composio, monkeypatch):  # noqa: F811
    stub_accounts(monkeypatch, {"zoho"})
    rows = {"Leads": [{"Full_Name": "Joe Kamau", "Company": "Acme Farms", "Email": "joe@acme.test"},
                      {"Full_Name": "Ann Wise", "Company": "Other"}],
            "Contacts": [{"First_Name": "Sam", "Last_Name": "Otieno", "Account_Name": {"name": "Acme Farms"}}],
            "Accounts": [{"Account_Name": "ACME Farms"}]}
    def execute(entity, tool, arguments, connection_id):
        return {"data": {"data": rows[arguments["module_api_name"]]}, "error": None, "log_id": "l"}
    monkeypatch.setattr(connection_service, "execute_tool", execute)
    found = await lace_apps.DbLaceApps(AsyncSessionLocal, _lace()).crm_find("acme")
    assert found == [{"kind": "lead", "name": "Joe Kamau", "company": "Acme Farms", "email": "joe@acme.test"},
                     {"kind": "contact", "name": "Sam Otieno", "company": "Acme Farms", "email": None},
                     {"kind": "company", "name": "ACME Farms", "company": "ACME Farms", "email": None}]


async def test_no_crm_means_nothing_read(composio, monkeypatch):  # noqa: F811
    stub_accounts(monkeypatch, {"gmail"})
    apps = lace_apps.DbLaceApps(AsyncSessionLocal, _lace())
    assert (await apps.crm(), await apps.crm_deals(), await apps.crm_find("x")) == (None, None, None)


async def test_an_approved_lead_goes_into_zoho(composio):  # noqa: F811
    composio["answers"] = {"ZOHO_CREATE_ZOHO_RECORD": [{"code": "SUCCESS", "status": "success", "details": {"id": "9"}}]}
    outcome = await crm_actions.zoho_add_lead(_ctx("zoho"), {"name": "Joe Wa Kamau", "company": "Acme",
                                                             "email": "joe@acme.test"})
    assert composio["calls"] == [("ZOHO_CREATE_ZOHO_RECORD", {"module_api_name": "Leads", "data": [
        {"Last_Name": "Kamau", "First_Name": "Joe Wa", "Company": "Acme", "Email": "joe@acme.test"}]})]
    assert outcome.result == "Added Joe Wa Kamau to Zoho CRM as a lead."


async def test_a_refused_lead_says_why(composio):  # noqa: F811
    composio["answers"] = {"ZOHO_CREATE_ZOHO_RECORD": [{"code": "DUPLICATE_DATA", "status": "error",
                                                        "message": "duplicate data"}]}
    with pytest.raises(ActionFailed, match="duplicate data"):
        await crm_actions.zoho_add_lead(_ctx("zoho"), {"name": "Joe", "company": "Acme"})


async def test_hubspot_deals_read_with_their_stage_names(composio, monkeypatch):  # noqa: F811
    stub_accounts(monkeypatch, {"hubspot"})
    composio["answers"] = {
        "HUBSPOT_RETRIEVE_ALL_PIPELINES_FOR_SPECIFIED_OBJECT_TYPE": {"results": [
            {"id": "default", "stages": [{"id": "appointmentscheduled", "label": "Appointment"},
                                         {"id": "closedwon", "label": "Closed won"}]}]},
        "HUBSPOT_HUBSPOT_LIST_DEALS": {"results": [
            {"id": "1", "properties": {"dealname": "Alpha", "dealstage": "closedwon", "amount": "1200",
                                       "closedate": "2026-10-01T00:00:00Z", "hs_is_closed": "true",
                                       "hs_is_closed_won": "true", "hs_lastmodifieddate": "2026-10-02T00:00:00Z"}},
            {"id": "2", "properties": {"dealname": "Beta", "dealstage": "appointmentscheduled", "amount": None,
                                       "hs_is_closed": "false"}}]},
    }
    apps = lace_apps.DbLaceApps(AsyncSessionLocal, _lace())
    assert await apps.crm() == "hubspot"
    assert await apps.crm_deals() == [
        {"name": "Alpha", "company": None, "stage": "Closed won", "amount": 1200.0, "close_date": "2026-10-01",
         "updated": "2026-10-02T00:00:00Z", "closed": True, "won": True},
        {"name": "Beta", "company": None, "stage": "Appointment", "amount": None, "close_date": None,
         "updated": None, "closed": False, "won": False}]


async def test_hubspot_lookup_uses_its_search(composio, monkeypatch):  # noqa: F811
    stub_accounts(monkeypatch, {"hubspot"})

    def execute(entity, tool, arguments, connection_id):
        results = {"contacts": [{"properties": {"firstname": "Joe", "lastname": "Kamau", "email": "joe@acme.test",
                                                "company": "Acme", "lifecyclestage": "lead"}}],
                   "companies": [{"properties": {"name": "Acme", "domain": "acme.test"}}]}[arguments["objectType"]]
        return {"data": {"results": results}, "error": None, "log_id": "l"}
    monkeypatch.setattr(connection_service, "execute_tool", execute)
    assert await lace_apps.DbLaceApps(AsyncSessionLocal, _lace()).crm_find("acme") == [
        {"kind": "lead", "name": "Joe Kamau", "company": "Acme", "email": "joe@acme.test"},
        {"kind": "company", "name": "Acme", "company": "Acme", "email": None}]


async def test_the_lace_prefers_zoho_when_both_are_connected(composio, monkeypatch):  # noqa: F811
    stub_accounts(monkeypatch, {"zoho", "hubspot"})
    assert await lace_apps.DbLaceApps(AsyncSessionLocal, _lace()).crm() == "zoho"


async def test_an_approved_lead_goes_into_hubspot(composio):  # noqa: F811
    composio["answers"] = {"HUBSPOT_CREATE_CONTACT": {"id": "501"}}
    outcome = await crm_actions.hubspot_add_lead(_ctx("hubspot"), {"name": "Joe Kamau", "company": "Acme",
                                                                   "title": "COO"})
    assert composio["calls"] == [("HUBSPOT_CREATE_CONTACT", {"firstname": "Joe", "lastname": "Kamau", "company": "Acme",
                                                             "jobtitle": "COO", "lifecyclestage": "lead"})]
    assert outcome.result == "Added Joe Kamau to HubSpot as a lead."
