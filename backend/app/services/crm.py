"""The founder's CRM, as a Lace reads it: deals and records from Zoho CRM in
one shape, through Composio. Each function takes
`run(tool, arguments)`, which returns a tool's data or raises AppError.
Composio tools verified against the live catalog (2026-10-24)."""

from collections.abc import Awaitable, Callable

Run = Callable[[str, dict], Awaitable[object]]

# The CRMs a Lace reads, in the order it picks one when the founder connected several.
CRM_APPS = ("zoho",)
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


DEALS: dict[str, Callable[[Run], Awaitable[list[dict]]]] = {"zoho": zoho_deals}
FIND: dict[str, Callable[[Run, str], Awaitable[list[dict]]]] = {"zoho": zoho_find}
