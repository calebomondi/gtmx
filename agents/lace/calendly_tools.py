"""The Lace's Calendly tools, read only: the founder's booking links to put in
drafts, and the meetings people booked, with who among them is one of the
Lace's contacts."""

from langchain_core.tools import BaseTool, tool

from agents.lace.apps import AppError, LaceApps
from agents.lace.store import LaceStore
from agents.lace.tool_guard import guarded
from agents.schemas.lace import ToolResult

MAX_DAYS = 60
NOT_CONNECTED = ("Calendly isn't connected for this Lace, or is switched off. "
                 "The founder can connect it under Apps & accounts in your settings.")


def build_calendly_tools(store: LaceStore, apps: LaceApps) -> list[BaseTool]:

    @tool(parse_docstring=True)
    @guarded
    async def booking_links() -> ToolResult:
        """The founder's Calendly booking links, one per meeting type. Put the right one in a draft when someone wants to talk, instead of proposing times by hand."""
        try:
            links = await apps.calendly_links()
        except AppError as exc:
            return ToolResult.failure(str(exc))
        if links is None:
            return ToolResult.failure(NOT_CONNECTED)
        return ToolResult.success(f"{len(links)} booking links." if links else
                                  "The founder has no active meeting types on Calendly.", links)

    @tool(parse_docstring=True)
    @guarded
    async def calendly_meetings(days_back: int = 7, days_ahead: int = 14) -> ToolResult:
        """Meetings people booked on the founder's Calendly, and who booked them; those who are your contacts are marked, so you can prepare or follow up.

        Args:
            days_back: How many past days to include (at most 60).
            days_ahead: How many coming days to include (at most 60).
        """
        try:
            meetings = await apps.calendly_meetings(max(0, min(days_back, MAX_DAYS)), max(0, min(days_ahead, MAX_DAYS)))
        except AppError as exc:
            return ToolResult.failure(str(exc))
        if meetings is None:
            return ToolResult.failure(NOT_CONNECTED)
        known = {c.email.lower(): c for c in await store.contacts(limit=1000) if c.email}
        for meeting in meetings:
            for person in meeting["invitees"]:
                contact = known.get((person.get("email") or "").lower())
                person["contact"] = f"{contact.name} at {contact.company}" if contact else None
        ours = sum(1 for m in meetings if any(p["contact"] for p in m["invitees"]))
        return ToolResult.success(f"{len(meetings)} meetings, {ours} with your contacts.", meetings)

    return [booking_links, calendly_meetings]
