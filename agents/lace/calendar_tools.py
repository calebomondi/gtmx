"""The Lace's Google Calendar tools beyond reading it (my_calendar): finding
when the founder is free, and proposing a meeting, a new time for one, or
cancelling one. A change runs only when the founder approves it, and Google
tells the guests."""

import re
from datetime import datetime

from langchain_core.tools import BaseTool, tool

from agents.lace.app_actions import propose
from agents.lace.apps import AppError, LaceApps
from agents.lace.store import LaceStore
from agents.lace.tool_guard import guarded
from agents.schemas.lace import ProposedAction, ToolResult

MAX_DAYS = 30
MIN_MINUTES, MAX_MINUTES = 15, 240
MAX_ATTENDEES = 20
TITLE_CHARS = 120
AGENDA_CHARS = 2000
_EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
_OFF = ToolResult.failure("Google Calendar isn't connected for this Lace, or is switched off. The founder can connect "
                          "it under Apps & accounts in your settings.")


def _when(start: str) -> datetime | None:
    try:
        return datetime.fromisoformat(start.strip())
    except ValueError:
        return None


def _length(minutes: int) -> int:
    return max(MIN_MINUTES, min(minutes, MAX_MINUTES))


def build_calendar_tools(store: LaceStore, apps: LaceApps) -> list[BaseTool]:

    @tool(parse_docstring=True)
    @guarded
    async def find_free_times(days_ahead: int = 7, minutes: int = 30) -> ToolResult:
        """When the founder is free for a meeting, in working hours on weekdays, from their Google Calendar: to offer someone times or to pick one before schedule_meeting.

        Args:
            days_ahead: How many days ahead to look (at most 30).
            minutes: How long the meeting is (15 to 240).
        """
        try:
            free = await apps.calendar_free_times(max(1, min(days_ahead, MAX_DAYS)), _length(minutes))
        except AppError as exc:
            return ToolResult.failure(str(exc))
        if free is None:
            return _OFF
        if not free["slots"]:
            return ToolResult.success(f"No free {minutes}-minute slot in working hours in the next {days_ahead} days.",
                                      free)
        return ToolResult.success(f"{len(free['slots'])} free times, in {free['timezone']}.", free)

    @tool(parse_docstring=True)
    @guarded
    async def schedule_meeting(title: str, start: str, minutes: int = 30, attendees: list[str] | None = None,
                               agenda: str = "") -> ToolResult:
        """Propose a meeting on the founder's Google Calendar, with a Google Meet link, inviting the people named. It is added only if the founder approves it; Google then emails the invitations. Pick a time with find_free_times first.

        Args:
            title: What the meeting is, e.g. "Thalace demo with Acme".
            start: When it starts, in the founder's calendar's timezone: "YYYY-MM-DDTHH:MM", e.g. "2026-11-10T14:00".
            minutes: How long it lasts (15 to 240).
            attendees: The guests' email addresses.
            agenda: What it is about, for the invitation.
        """
        when = _when(start)
        if when is None:
            return ToolResult.failure('Give the start as "YYYY-MM-DDTHH:MM".')
        guests = list(dict.fromkeys(a.strip().lower() for a in attendees or [] if a.strip()))
        if bad := [a for a in guests if not _EMAIL.match(a)]:
            return ToolResult.failure(f"Not an email address: {', '.join(bad)}.")
        if len(guests) > MAX_ATTENDEES:
            return ToolResult.failure(f"Invite at most {MAX_ATTENDEES} people.")
        name = " ".join(title.split())[:TITLE_CHARS] or "Meeting"
        length = _length(minutes)
        who = f"\nWith: {', '.join(guests)}" if guests else ""
        about = f"\n\n{agenda.strip()[:AGENDA_CHARS]}" if agenda.strip() else ""
        return await propose(store, ProposedAction(
            app="googlecalendar", action="create_event", title=f"Add \"{name}\" to the calendar",
            preview=f"{when:%a %d %b %Y, %H:%M}, {length} minutes, with a Google Meet link{who}{about}",
            arguments={"title": name, "start": when.isoformat(timespec="minutes"), "minutes": length,
                       "attendees": guests, "agenda": agenda.strip()[:AGENDA_CHARS]}))

    @tool(parse_docstring=True)
    @guarded
    async def reschedule_meeting(event_id: str, title: str, start: str, minutes: int = 30) -> ToolResult:
        """Propose moving a meeting on the founder's calendar to a new time. It moves only if they approve it; Google tells the guests.

        Args:
            event_id: The meeting's id, from my_calendar.
            title: Its title, from my_calendar, so the founder knows which one.
            start: The new start, in the calendar's timezone: "YYYY-MM-DDTHH:MM".
            minutes: How long it lasts (15 to 240).
        """
        when = _when(start)
        if when is None or not event_id.strip():
            return ToolResult.failure('Give the meeting\'s id from my_calendar and the start as "YYYY-MM-DDTHH:MM".')
        length = _length(minutes)
        return await propose(store, ProposedAction(
            app="googlecalendar", action="move_event", title=f"Move \"{title.strip()[:TITLE_CHARS]}\"",
            preview=f"To {when:%a %d %b %Y, %H:%M}, {length} minutes",
            arguments={"event_id": event_id.strip(), "title": title.strip()[:TITLE_CHARS],
                       "start": when.isoformat(timespec="minutes"), "minutes": length}))

    @tool(parse_docstring=True)
    @guarded
    async def cancel_meeting(event_id: str, title: str) -> ToolResult:
        """Propose cancelling a meeting on the founder's calendar. It is cancelled only if they approve it; Google tells the guests.

        Args:
            event_id: The meeting's id, from my_calendar.
            title: Its title, from my_calendar, so the founder knows which one.
        """
        if not event_id.strip():
            return ToolResult.failure("Give the meeting's id, from my_calendar.")
        name = title.strip()[:TITLE_CHARS]
        return await propose(store, ProposedAction(
            app="googlecalendar", action="cancel_event", title=f"Cancel \"{name}\"",
            preview="Guests are told it is cancelled.", arguments={"event_id": event_id.strip(), "title": name}))

    return [find_free_times, schedule_meeting, reschedule_meeting, cancel_meeting]
