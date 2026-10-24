"""The Asana actions a Lace can propose, run on the founder's approval
(lace_app_actions): a follow-up task assigned to the founder. Composio tools
verified against the live catalog (2026-10-24)."""

from agents.lace.apps import AppError
from backend.app.services import connections as connection_service
from backend.app.services.lace_app_actions import ActionFailed, Outcome, RunContext, call, runs
from backend.app.services.lace_apps import asana_workspace


@runs("asana", "create_task")
async def create_task(ctx: RunContext, arguments: dict) -> Outcome:
    async def data(tool: str, args: dict):
        return (await call(ctx, tool, args))["data"]
    try:
        workspace = await asana_workspace(data)
    except AppError as exc:
        raise ActionFailed(str(exc)) from exc
    task = {"name": arguments["name"], "notes": arguments.get("notes") or "", "assignee": "me", "workspace": workspace,
            **({"due_on": arguments["due_on"]} if arguments.get("due_on") else {})}
    done = await call(ctx, "ASANA_CREATE_A_TASK", {"data": task, "opt_fields": ["permalink_url"]})
    return Outcome(f"Added “{arguments['name']}” to your Asana tasks.",
                   connection_service.response_field(done["data"], "permalink_url"), done["log_id"])
