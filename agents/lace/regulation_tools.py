"""The Lace's tools for the laws, regulations, bills and filing obligations
that apply to its startup: recording where it is registered and operates
(as a founder says), searching for what applies there, and keeping what the
founder tracks. What they find is information with its source, never legal
advice."""

from typing import Literal

from langchain_core.tools import BaseTool, tool

from agents.lace.edit_tools import MAX_IDS, _ids, _report
from agents.lace.store import JobRefused, LaceJobs, LaceStore
from agents.lace.tool_guard import guarded
from agents.schemas.lace import ToolResult

REGULATIONS_PER_READ = 50
NOT_CONFIRMED = ("No confirmed jurisdiction yet. Ask the founder where the startup is registered and where it "
                 "operates (staff, office, customers), suggesting what the facts say; then record their answer "
                 "with set_jurisdiction.")
_VERDICT_STATUS = {"track": "tracked", "dismiss": "dismissed"}


def build_regulation_tools(store: LaceStore, jobs: LaceJobs | None = None) -> list[BaseTool]:
    """The regulation tools, closed over the Lace's store; the search only
    when there is something to run jobs."""

    @tool(parse_docstring=True)
    @guarded
    async def set_jurisdiction(registered_in: str | None, operates_in: list[str]) -> ToolResult:
        """Record where the startup is registered and where it operates, as the founder told or confirmed to you. Only their word counts: never record a guess. Laws are searched only in these places.

        Args:
            registered_in: Where the company is registered, as an ISO 3166 code: KE, NG, or a subdivision like US-DE. None if they don't know.
            operates_in: Every place it has staff, an office or customers, as ISO 3166 codes, e.g. ["KE", "UG"].
        """
        codes = [c.strip().upper() for c in operates_in if c.strip()]
        try:
            place = await store.set_jurisdiction(registered_in.strip().upper() if registered_in else None, codes)
        except ValueError as exc:
            return ToolResult.failure(str(exc))
        registered = f"registered in {place.registered_in}" if place.registered_in else "registration unknown"
        return ToolResult.success(f"Recorded: {registered}, operating in {', '.join(place.operates_in) or 'nowhere yet'}.",
                                  place.model_dump())

    @tool(parse_docstring=True)
    @guarded
    async def list_regulations(status: Literal["tracked", "suggested", "dismissed"] = "tracked") -> ToolResult:
        """The laws, regulations, bills and filing obligations on file for the startup, with where it is registered and operates. Tracked ones are what the founder follows, the soonest next date first; suggested ones wait for them to track or dismiss.

        Args:
            status: Which to read: tracked (default), suggested or dismissed.
        """
        place = await store.jurisdiction()
        rows = await store.regulations(status, REGULATIONS_PER_READ)
        where = (f" Jurisdiction: {', '.join(place.places)}" + ("" if place.confirmed else " (not confirmed)")
                 if place.places else " No jurisdiction recorded.")
        return ToolResult.success(f"{len(rows)} {status} regulations.{where}",
                                  {"jurisdiction": place.model_dump(),
                                   "regulations": [r.model_dump(exclude_none=True) for r in rows]})

    @tool(parse_docstring=True)
    @guarded
    async def update_regulations(ids: list[str], verdict: Literal["track", "dismiss"]) -> ToolResult:
        """Track regulations (you watch them and say when a bill moves or a date nears) or dismiss them (they stop being suggested), when the founder asks.

        Args:
            ids: Up to 20 regulation ids, from list_regulations or an update.
            verdict: track or dismiss.
        """
        wanted = _ids(ids)
        if wanted is None:
            return ToolResult.failure(f"Give 1 to {MAX_IDS} ids.")
        result = await store.set_regulations(wanted, _VERDICT_STATUS[verdict])
        return _report("Tracking" if verdict == "track" else "Dismissed", result)

    tools: list[BaseTool] = [set_jurisdiction, list_regulations, update_regulations]
    if jobs is None:
        return tools

    @tool(parse_docstring=True)
    @guarded
    async def find_regulations() -> ToolResult:
        """Search official sources for the laws, regulations, bills and filing obligations that apply to the startup where it is registered and operates: company, tax, employment, data protection, sector licences, and new bills that would change them. Keeps only cited ones. Runs in the background; you get an update when it is done. Needs a confirmed jurisdiction (set_jurisdiction)."""
        if not (await store.jurisdiction()).confirmed:
            return ToolResult.failure(NOT_CONFIRMED)
        try:
            await jobs.start("find_regulations", {})
        except JobRefused as exc:
            return ToolResult.failure(str(exc))
        return ToolResult.success("Started looking for the laws and regulations that apply. You will get an "
                                  "update here when it finishes.")

    return [*tools, find_regulations]
