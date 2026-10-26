"""The Lace's CRM tools, for whichever CRM it uses (Zoho CRM or HubSpot): the
pipeline summed up in code, whether someone is already in the CRM, and adding
a lead as a proposal the founder approves."""

from datetime import date

from langchain_core.tools import BaseTool, tool
from pydantic import ValidationError

from agents.lace.app_actions import propose
from agents.lace.apps import AppError, LaceApps
from agents.lace.crm import summarise_deals
from agents.lace.store import LaceStore
from agents.lace.tool_guard import guarded
from agents.schemas.lace import NewLead, ProposedAction, ToolResult

LABELS = {"zoho": "Zoho CRM", "hubspot": "HubSpot"}
NO_CRM = ("No CRM is connected for this Lace, or it is switched off. The founder can connect Zoho CRM or "
          "HubSpot under Apps & accounts in your settings.")


def build_crm_tools(store: LaceStore, apps: LaceApps) -> list[BaseTool]:

    @tool(parse_docstring=True)
    @guarded
    async def crm_pipeline() -> ToolResult:
        """The founder's CRM pipeline, worked out exactly: deals and value by stage, open, won and lost, stale open deals, and those due to close soon. Quote these numbers; never add up deals yourself."""
        try:
            deals = await apps.crm_deals()
        except AppError as exc:
            return ToolResult.failure(str(exc))
        if deals is None:
            return ToolResult.failure(NO_CRM)
        summary = summarise_deals(deals, date.today())
        return ToolResult.success(
            f"{summary['deals']} deals: {summary['open']['count']} open worth {summary['open']['value']:,.2f}, "
            f"{summary['won']['count']} won, {summary['lost']} lost; {summary['stale']['count']} open deals "
            f"untouched for {summary['stale']['days']}+ days.", summary)

    @tool(parse_docstring=True)
    @guarded
    async def crm_lookup(query: str) -> ToolResult:
        """Check whether a person or company is already in the founder's CRM (as a lead, contact or company) before reaching out or adding them.

        Args:
            query: A name, company or email.
        """
        if len(query.strip()) < 2:
            return ToolResult.failure("Give at least two characters of a name, company or email.")
        try:
            found = await apps.crm_find(query.strip())
        except AppError as exc:
            return ToolResult.failure(str(exc))
        if found is None:
            return ToolResult.failure(NO_CRM)
        return ToolResult.success(f"{len(found)} matches in the CRM for {query!r}." if found else
                                  f"Nobody in the CRM matches {query!r}.", found)

    @tool(parse_docstring=True)
    @guarded
    async def add_lead_to_crm(name: str, company: str, email: str | None = None, title: str | None = None,
                              note: str | None = None) -> ToolResult:
        """Propose adding a person to the founder's CRM as a lead: someone who replied with interest, or a contact the founder wants tracked. Check with crm_lookup first. It is added only if they approve it.

        Args:
            name: Their full name.
            company: Their company.
            email: Their email, if known.
            title: Their role, if known.
            note: Why they are a lead, in a line.
        """
        crm = await apps.crm()
        if crm is None:
            return ToolResult.failure(NO_CRM)
        try:
            lead = NewLead(name=name.strip(), company=company.strip(), email=email and email.strip() or None,
                           title=title, note=note)
        except ValidationError:
            return ToolResult.failure("Give at least a name and a company, each within normal length.")
        preview = "\n".join(filter(None, [f"{lead.name}, {lead.title + ' at ' if lead.title else ''}{lead.company}",
                                          lead.email, lead.note]))
        return await propose(store, ProposedAction(
            app=crm, action="add_lead", title=f"Add {lead.name} to {LABELS[crm]}", preview=preview,
            arguments=lead.model_dump(exclude_none=True)))

    return [crm_pipeline, crm_lookup, add_lead_to_crm]
