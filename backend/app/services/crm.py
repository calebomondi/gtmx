"""The founder's CRM, as a Lace reads it: deals and records from Zoho CRM or
HubSpot in one shape, through Composio. Each function takes
`run(tool, arguments)`, which returns a tool's data or raises AppError.
Composio tools verified against the live catalog (2026-10-24)."""

from collections.abc import Awaitable, Callable

Run = Callable[[str, dict], Awaitable[object]]

# Zoho returns at most 200 records a page; these bound what one read fetches.
ZOHO_PAGE = 200
DEAL_PAGES = 5
FIND_PAGES = 3
FOUND_MAX = 20
_ZOHO_GET = "ZOHO_GET_ZOHO_RECORDS"
_ZOHO_FIND = {  # module -> fields read, and how a record reads as {kind, name, company, email}
    "Leads": ("Full_Name,First_Name,Last_Name,Company,Email",
              lambda r: ("lead", r.get("Full_Name") or _join(r.get("First_Name"), r.get("Last_Name")),
                         r.get("Company"), r.get("Email"))),
    "Contacts": ("Full_Name,First_Name,Last_Name,Account_Name,Email",
                 lambda r: ("contact", r.get("Full_Name") or _join(r.get("First_Name"), r.get("Last_Name")),
                            _name(r.get("Account_Name")), r.get("Email"))),
    "Accounts": ("Account_Name,Website", lambda r: ("company", r.get("Account_Name"), r.get("Account_Name"), None)),
}


def _join(*parts) -> str:
    return " ".join(p for p in parts if p)


def _name(lookup) -> str | None:
    """A Zoho lookup field ({name, id}) as its name."""
    return lookup.get("name") if isinstance(lookup, dict) else lookup


def _records(data) -> list[dict]:
    rows = data.get("data") if isinstance(data, dict) else data
    return [r for r in rows or [] if isinstance(r, dict)]


async def _zoho_pages(run: Run, module: str, fields: str, pages: int) -> list[dict]:
    found: list[dict] = []
    for page in range(1, pages + 1):
        rows = _records(await run(_ZOHO_GET, {"module_api_name": module, "fields": fields, "per_page": ZOHO_PAGE,
                                              "page": page, "sort_by": "Modified_Time", "sort_order": "desc"}))
        found += rows
        if len(rows) < ZOHO_PAGE:
            break
    return found


def _amount(value) -> float | None:
    try:
        return float(value) if value is not None else None
    except (TypeError, ValueError):
        return None


async def zoho_deals(run: Run) -> list[dict]:
    rows = await _zoho_pages(run, "Deals", "Deal_Name,Stage,Amount,Closing_Date,Account_Name,Modified_Time", DEAL_PAGES)
    deals = []
    for r in rows:
        stage = r.get("Stage") or ""
        closed = stage.lower().startswith("closed")
        deals.append({"name": r.get("Deal_Name"), "company": _name(r.get("Account_Name")), "stage": stage or None,
                      "amount": _amount(r.get("Amount")), "close_date": r.get("Closing_Date"),
                      "updated": r.get("Modified_Time"), "closed": closed, "won": closed and "won" in stage.lower()})
    return deals


def matches(records: list[dict], query: str) -> list[dict]:
    """The records whose name, company or email contains `query`, bounded."""
    needle = query.lower()
    return [r for r in records
            if any(needle in (r.get(k) or "").lower() for k in ("name", "company", "email"))][:FOUND_MAX]


async def zoho_find(run: Run, query: str) -> list[dict]:
    records = []
    for module, (fields, read) in _ZOHO_FIND.items():
        for row in await _zoho_pages(run, module, fields, FIND_PAGES):
            kind, name, company, email = read(row)
            records.append({"kind": kind, "name": name, "company": company, "email": email})
    return matches(records, query)


# HubSpot pages hold at most 100 records.
HUBSPOT_PAGE = 100
HUBSPOT_DEAL_PAGES = 10
_HUBSPOT_DEAL_FIELDS = ["dealname", "dealstage", "amount", "closedate", "hs_lastmodifieddate", "hs_is_closed",
                        "hs_is_closed_won"]


def _results(data) -> tuple[list[dict], str | None]:
    """A HubSpot list's records and its next-page cursor, wrapped or not."""
    body = data if isinstance(data, dict) else {}
    if "results" not in body:
        body = next((body[k] for k in ("data", "response_data") if isinstance(body.get(k), dict)), body)
    rows = [r for r in body.get("results") or [] if isinstance(r, dict)]
    return rows, ((body.get("paging") or {}).get("next") or {}).get("after")


def _true(value) -> bool:
    return str(value).lower() == "true"


async def _hubspot_stages(run: Run) -> dict[str, str]:
    """Deal stage id -> its label, across the deal pipelines."""
    pipelines, _ = _results(await run("HUBSPOT_RETRIEVE_ALL_PIPELINES_FOR_SPECIFIED_OBJECT_TYPE", {"objectType": "deals"}))
    return {str(s.get("id")): s.get("label") for p in pipelines for s in p.get("stages") or [] if isinstance(s, dict)}


async def hubspot_deals(run: Run) -> list[dict]:
    stages = await _hubspot_stages(run)
    deals, after = [], None
    for _ in range(HUBSPOT_DEAL_PAGES):
        rows, after = _results(await run("HUBSPOT_LIST_DEALS", {
            "limit": HUBSPOT_PAGE, "properties": _HUBSPOT_DEAL_FIELDS, **({"after": after} if after else {})}))
        for row in rows:
            p = row.get("properties") or {}
            deals.append({"name": p.get("dealname"), "company": None,
                          "stage": stages.get(str(p.get("dealstage"))) or p.get("dealstage"),
                          "amount": _amount(p.get("amount")), "close_date": (p.get("closedate") or "")[:10] or None,
                          "updated": p.get("hs_lastmodifieddate"), "closed": _true(p.get("hs_is_closed")),
                          "won": _true(p.get("hs_is_closed_won"))})
        if not after:
            break
    return deals


async def hubspot_find(run: Run, query: str) -> list[dict]:
    """HubSpot's own search, over contacts and companies."""
    people, _ = _results(await run("HUBSPOT_SEARCH_CRM_OBJECTS_BY_CRITERIA", {
        "objectType": "contacts", "query": query, "limit": FOUND_MAX,
        "properties": ["firstname", "lastname", "email", "company", "lifecyclestage"]}))
    companies, _ = _results(await run("HUBSPOT_SEARCH_CRM_OBJECTS_BY_CRITERIA", {
        "objectType": "companies", "query": query, "limit": FOUND_MAX, "properties": ["name", "domain"]}))
    found = []
    for row in people:
        p = row.get("properties") or {}
        found.append({"kind": "lead" if p.get("lifecyclestage") == "lead" else "contact",
                      "name": _join(p.get("firstname"), p.get("lastname")) or None, "company": p.get("company"),
                      "email": p.get("email")})
    for row in companies:
        p = row.get("properties") or {}
        found.append({"kind": "company", "name": p.get("name"), "company": p.get("name"), "email": None})
    return found[:FOUND_MAX]


# The whole CRM, for a Lace's copy of it (crm_sync): pages per module, so
# one sync is bounded (Zoho: 1,000 per module; HubSpot: 1,000 per object).
SNAPSHOT_PAGES = 5
HUBSPOT_SNAPSHOT_PAGES = 10
# Where each status ranks when one company turns up more than once.
STATUS_RANK = {"customer": 3, "open_deal": 2, "lead": 1, "known": 0}
# HubSpot lifecycle stages, as a CRM status.
_HUBSPOT_LIFECYCLE = {"customer": "customer", "evangelist": "customer", "opportunity": "open_deal",
                      "lead": "lead", "marketingqualifiedlead": "lead", "salesqualifiedlead": "lead"}


def _record(kind: str, status: str, *, name=None, company=None, email=None, website=None, stage=None) -> dict:
    """One CRM record in the shape every CRM is read into: {kind (company or
    person), status (CrmStatus), name, company, email, website, stage}."""
    return {"kind": kind, "status": status, "name": name or None, "company": company or None,
            "email": (email or "").strip().lower() or None, "website": website or None, "stage": stage or None}


def _deal_status(stage: str) -> str:
    lowered = stage.lower()
    if not lowered.startswith("closed"):
        return "open_deal"
    return "customer" if "won" in lowered else "known"


async def zoho_snapshot(run: Run) -> list[dict]:
    """Every company and person in Zoho CRM, with where each stands: a won deal
    makes its company a customer, an open one an open deal; leads are leads."""
    records = [_record("company", "known", company=r.get("Account_Name"), website=r.get("Website"))
               for r in await _zoho_pages(run, "Accounts", "Account_Name,Website", SNAPSHOT_PAGES)]
    for r in await _zoho_pages(run, "Deals", "Deal_Name,Stage,Account_Name", SNAPSHOT_PAGES):
        if company := _name(r.get("Account_Name")):
            stage = r.get("Stage") or ""
            records.append(_record("company", _deal_status(stage), company=company, stage=stage))
    for r in await _zoho_pages(run, "Contacts", "Full_Name,First_Name,Last_Name,Account_Name,Email", SNAPSHOT_PAGES):
        records.append(_record("person", "known", name=r.get("Full_Name") or _join(r.get("First_Name"), r.get("Last_Name")),
                               company=_name(r.get("Account_Name")), email=r.get("Email")))
    for r in await _zoho_pages(run, "Leads", "Full_Name,First_Name,Last_Name,Company,Email,Website", SNAPSHOT_PAGES):
        records.append(_record("person", "lead", name=r.get("Full_Name") or _join(r.get("First_Name"), r.get("Last_Name")),
                               company=r.get("Company"), email=r.get("Email"), website=r.get("Website"), stage="Lead"))
    return records


async def _hubspot_all(run: Run, tool: str, properties: list[str]) -> list[dict]:
    rows, after = [], None
    for _ in range(HUBSPOT_SNAPSHOT_PAGES):
        page, after = _results(await run(tool, {"limit": HUBSPOT_PAGE, "properties": properties,
                                                **({"after": after} if after else {})}))
        rows += [r.get("properties") or {} for r in page]
        if not after:
            break
    return rows


async def hubspot_snapshot(run: Run) -> list[dict]:
    """Every company and contact in HubSpot, with where each stands, from its
    lifecycle stage (customer, opportunity, lead)."""
    records = []
    for p in await _hubspot_all(run, "HUBSPOT_LIST_COMPANIES", ["name", "domain", "lifecyclestage"]):
        stage = p.get("lifecyclestage") or ""
        records.append(_record("company", _HUBSPOT_LIFECYCLE.get(stage, "known"), company=p.get("name"),
                               website=p.get("domain"), stage=stage))
    for p in await _hubspot_all(run, "HUBSPOT_LIST_CONTACTS", ["firstname", "lastname", "email", "company",
                                                               "lifecyclestage"]):
        stage = p.get("lifecyclestage") or ""
        records.append(_record("person", _HUBSPOT_LIFECYCLE.get(stage, "known"),
                               name=_join(p.get("firstname"), p.get("lastname")), company=p.get("company"),
                               email=p.get("email"), stage=stage))
    return records


DEALS: dict[str, Callable[[Run], Awaitable[list[dict]]]] = {"zoho": zoho_deals, "hubspot": hubspot_deals}
SNAPSHOT: dict[str, Callable[[Run], Awaitable[list[dict]]]] = {"zoho": zoho_snapshot, "hubspot": hubspot_snapshot}
FIND: dict[str, Callable[[Run, str], Awaitable[list[dict]]]] = {"zoho": zoho_find, "hubspot": hubspot_find}
