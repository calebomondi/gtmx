"""The Lace's Asana tools: the founder's open tasks, with what is overdue or
due soon counted in code, and a follow-up task (call back, send the deck) as
a proposal the founder approves."""

from datetime import date, timedelta

from langchain_core.tools import BaseTool, tool

from agents.lace.app_actions import propose
from agents.lace.apps import AppError, LaceApps
from agents.lace.store import LaceStore
from agents.lace.tool_guard import guarded
from agents.schemas.lace import ProposedAction, ToolResult

SOON_DAYS = 7
NAME_CHARS = 200
NOTES_CHARS = 5000
NOT_CONNECTED = ("Asana isn't connected for this Lace, or is switched off. "
                 "The founder can connect it under Apps & accounts in your settings.")


def _due(task: dict) -> date | None:
    try:
        return date.fromisoformat(task.get("due_on") or "")
    except ValueError:
        return None


def summarise_tasks(tasks: list[dict], today: date) -> dict:
    """{open, overdue, due_soon, no_date}: the counts, worked out here."""
    dues = [_due(t) for t in tasks]
    return {"open": len(tasks), "overdue": sum(1 for d in dues if d and d < today),
            "due_soon": sum(1 for d in dues if d and today <= d <= today + timedelta(days=SOON_DAYS)),
            "no_date": sum(1 for d in dues if d is None)}


def build_asana_tools(store: LaceStore, apps: LaceApps) -> list[BaseTool]:

    @tool(parse_docstring=True)
    @guarded
    async def list_tasks() -> ToolResult:
        """The founder's open Asana tasks, with how many are overdue or due in the next week counted exactly: quote those counts. Overdue first."""
        try:
            tasks = await apps.asana_tasks()
        except AppError as exc:
            return ToolResult.failure(str(exc))
        if tasks is None:
            return ToolResult.failure(NOT_CONNECTED)
        today = date.today()
        counts = summarise_tasks(tasks, today)
        ordered = sorted(tasks, key=lambda t: (_due(t) is None, _due(t) or today))
        return ToolResult.success(
            f"{counts['open']} open tasks: {counts['overdue']} overdue, {counts['due_soon']} due in the next "
            f"{SOON_DAYS} days, {counts['no_date']} with no date.", {"counts": counts, "tasks": ordered})

    @tool(parse_docstring=True)
    @guarded
    async def create_follow_up_task(name: str, notes: str = "", due_on: str | None = None) -> ToolResult:
        """Propose an Asana task for the founder, assigned to them: a follow-up such as calling a prospect back or sending a deck. It is created only if they approve it.

        Args:
            name: What to do, e.g. "Call Samir at SunCulture about pricing".
            notes: Context: who, what was said, links.
            due_on: Due date, YYYY-MM-DD.
        """
        title = name.strip()
        if not title or len(title) > NAME_CHARS:
            return ToolResult.failure(f"Give the task a name of at most {NAME_CHARS} characters.")
        if due_on:
            try:
                date.fromisoformat(due_on)
            except ValueError:
                return ToolResult.failure("due_on must be a date, YYYY-MM-DD.")
        body = notes.strip()[:NOTES_CHARS]
        preview = "\n".join([title, *([f"Due {due_on}"] if due_on else []), *([body] if body else [])])
        return await propose(store, ProposedAction(
            app="asana", action="create_task", title="Add a task in Asana", preview=preview,
            arguments={"name": title, "notes": body, "due_on": due_on}))

    return [list_tasks, create_follow_up_task]
