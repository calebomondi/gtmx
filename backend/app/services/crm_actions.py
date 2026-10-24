"""The CRM actions a Lace can propose, run on the founder's approval
(lace_app_actions): adding a lead. Composio tools verified against the live
catalog (2026-10-24)."""

from backend.app.services import connections as connection_service
from backend.app.services.lace_app_actions import ActionFailed, Outcome, RunContext, call, runs


@runs("zoho", "add_lead")
async def zoho_add_lead(ctx: RunContext, arguments: dict) -> Outcome:
    *first, last = arguments["name"].split()
    lead = {"Last_Name": last, "First_Name": " ".join(first) or None, "Company": arguments["company"],
            "Email": arguments.get("email"), "Designation": arguments.get("title"),
            "Description": arguments.get("note")}
    done = await call(ctx, "ZOHO_CREATE_ZOHO_RECORD", {"module_api_name": "Leads",
                                                       "data": [{k: v for k, v in lead.items() if v}]})
    rows = done["data"] if isinstance(done["data"], list) else (done["data"] or {}).get("data") or []
    result = rows[0] if rows and isinstance(rows[0], dict) else {}
    if result.get("status") == "error":
        raise ActionFailed(f"Zoho CRM refused it: {result.get('message') or result.get('code')}")
    return Outcome(f"Added {arguments['name']} to Zoho CRM as a lead.", None, done["log_id"])


@runs("hubspot", "add_lead")
async def hubspot_add_lead(ctx: RunContext, arguments: dict) -> Outcome:
    *first, last = arguments["name"].split()
    contact = {"firstname": " ".join(first) or None, "lastname": last, "email": arguments.get("email"),
               "company": arguments["company"], "jobtitle": arguments.get("title"), "message": arguments.get("note"),
               "lifecyclestage": "lead"}
    done = await call(ctx, "HUBSPOT_CREATE_CONTACT", {k: v for k, v in contact.items() if v})
    if not connection_service.response_field(done["data"], "id"):
        raise ActionFailed("HubSpot didn't say it made the contact; check HubSpot before trying again.")
    return Outcome(f"Added {arguments['name']} to HubSpot as a lead.", None, done["log_id"])
