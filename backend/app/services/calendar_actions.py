"""Changes to the founder's Google Calendar the Lace proposes, run only on
their approval: a new meeting (with a Meet link, inviting its people), a
meeting moved, a meeting cancelled. Guests are notified by Google."""

import asyncio
from datetime import datetime, timedelta

from backend.app.services import calendar
from backend.app.services.lace_app_actions import ActionFailed, Outcome, RunContext, call, runs


async def _timezone(ctx: RunContext, arguments: dict) -> str:
    return arguments.get("timezone") or await asyncio.to_thread(calendar.timezone_of, ctx.entity, ctx.connection_id)


def _start(arguments: dict) -> datetime:
    try:
        return datetime.fromisoformat(arguments["start"])
    except (KeyError, ValueError) as exc:
        raise ActionFailed("The meeting's time couldn't be read; ask for it again.") from exc


def _event(data) -> dict:
    inner = (data or {}).get("response_data") if isinstance(data, dict) else None
    return inner if isinstance(inner, dict) else (data if isinstance(data, dict) else {})


@runs("googlecalendar", "create_event")
async def create_event(ctx: RunContext, arguments: dict) -> Outcome:
    tz = await _timezone(ctx, arguments)
    done = await call(ctx, "GOOGLECALENDAR_CREATE_EVENT", calendar.event_arguments(
        arguments["title"], _start(arguments), int(arguments["minutes"]), tz, list(arguments.get("attendees") or []),
        arguments.get("agenda") or ""))
    event = _event(done["data"])
    return Outcome(f"Added \"{arguments['title']}\" to the calendar on {arguments['start']} ({tz}); guests are invited.",
                   event.get("htmlLink"), done["log_id"])


@runs("googlecalendar", "move_event")
async def move_event(ctx: RunContext, arguments: dict) -> Outcome:
    tz = await _timezone(ctx, arguments)
    start = _start(arguments)
    end = start + timedelta(minutes=int(arguments["minutes"]))
    done = await call(ctx, "GOOGLECALENDAR_PATCH_EVENT", {
        "calendar_id": "primary", "event_id": arguments["event_id"], "start_time": start.isoformat(),
        "end_time": end.isoformat(), "timezone": tz, "send_updates": "all"})
    return Outcome(f"Moved \"{arguments['title']}\" to {arguments['start']} ({tz}); guests are told.",
                   _event(done["data"]).get("htmlLink"), done["log_id"])


@runs("googlecalendar", "cancel_event")
async def cancel_event(ctx: RunContext, arguments: dict) -> Outcome:
    done = await call(ctx, "GOOGLECALENDAR_DELETE_EVENT", {
        "calendar_id": "primary", "event_id": arguments["event_id"], "send_updates": "all"})
    return Outcome(f"Cancelled \"{arguments['title']}\"; guests are told.", None, done["log_id"])
