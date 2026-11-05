"""The Google Calendar a Lace uses (its own, else the founder's), through
Composio: free slots a reply can offer, and adding a meeting the founder
approved."""

import asyncio
from datetime import UTC, datetime, time, timedelta
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.database.lace_models import Lace
from backend.app.services import connections as connection_service
from backend.app.services.errors import ConflictError
from utils.log import logger

_PROFILE_TOOL = "GOOGLECALENDAR_GET_CALENDAR_PROFILE"
_FREE_TOOL = "GOOGLECALENDAR_FIND_FREE_SLOTS"
_CREATE_TOOL = "GOOGLECALENDAR_CREATE_EVENT"
LOOKAHEAD_DAYS = 7
SLOT_MINUTES = 30
MAX_SLOTS = 3
_WORK_START, _WORK_END = time(9), time(17)




def _zone(name: str) -> ZoneInfo:
    try:
        return ZoneInfo(name)
    except (ZoneInfoNotFoundError, ValueError):
        return ZoneInfo("UTC")


def _round_up(moment: datetime) -> datetime:
    """To the next slot boundary (:00 or :30)."""
    moment = moment.replace(second=0, microsecond=0) + (timedelta(minutes=1) if moment.second or moment.microsecond else timedelta())
    return moment + timedelta(minutes=(-moment.minute) % SLOT_MINUTES)


def pick_slots(free: list[dict], zone: ZoneInfo, now: datetime, minutes: int = SLOT_MINUTES, count: int = MAX_SLOTS,
               per_day: int = 1) -> list[datetime]:
    """Up to `count` starts of `minutes`-long slots inside working hours on
    weekdays, at most `per_day` a day, an hour or more apart."""
    picked: list[datetime] = []
    length = timedelta(minutes=minutes)
    for period in free:
        start = datetime.fromisoformat(str(period["start"]).replace("Z", "+00:00")).astimezone(zone)
        end = datetime.fromisoformat(str(period["end"]).replace("Z", "+00:00")).astimezone(zone)
        cursor = _round_up(max(start, now.astimezone(zone) + timedelta(hours=2)))
        while cursor + length <= end and len(picked) < count:
            same_day = [p for p in picked if p.date() == cursor.date()]
            if cursor.weekday() < 5 and _WORK_START <= cursor.time() and (cursor + length).time() <= _WORK_END \
                    and len(same_day) < per_day and all(abs(cursor - p) >= timedelta(hours=1) for p in same_day):
                picked.append(cursor)
                if per_day == 1:
                    break
            cursor += timedelta(minutes=SLOT_MINUTES)
    return sorted(picked)


def _free_periods(data: dict) -> list[dict]:
    calendars = data.get("calendars") or {}
    windows = calendars.values() if isinstance(calendars, dict) else calendars
    return [period for window in windows if isinstance(window, dict) for period in window.get("free") or []]


def timezone_of(entity: str, connection_id: str) -> str:
    """The calendar's own timezone, e.g. "Africa/Nairobi"; UTC when unsaid."""
    profile = connection_service.execute_tool(entity, _PROFILE_TOOL, {}, connection_id)
    return (profile.get("data") or {}).get("timeZone") or "UTC"


def read_free_slots(entity: str, connection_id: str, days: int = LOOKAHEAD_DAYS, minutes: int = SLOT_MINUTES,
                    count: int = MAX_SLOTS, per_day: int = 1) -> tuple[list[str], str]:
    """(free slots as "Mon 10 Nov, 14:00-14:30 (tz)", the calendar's timezone).
    Raises ConflictError when the calendar won't say."""
    tz = timezone_of(entity, connection_id)
    now = datetime.now(UTC)
    result = connection_service.execute_tool(entity, _FREE_TOOL, {
        "items": ["primary"], "time_min": now.isoformat(), "time_max": (now + timedelta(days=days)).isoformat(),
        "timezone": tz,
    }, connection_id)
    if result.get("error") or not isinstance(result.get("data"), dict):
        raise ConflictError("Google Calendar didn't say when you're free; try again in a moment.")
    slots = pick_slots(_free_periods(result["data"]), _zone(tz), now, minutes, count, per_day)
    return [s.strftime("%a %d %b, %H:%M") + f"-{(s + timedelta(minutes=minutes)).strftime('%H:%M')} ({tz})"
            for s in slots], tz


async def free_slots(db: AsyncSession, lace: Lace) -> tuple[list[str], str]:
    """(human-readable free slots, timezone) for the next working days, or
    ([], "") when no calendar is connected or it can't be read."""
    account = await connection_service.connection_for(db, lace, "googlecalendar")
    if account is None:
        return [], ""
    try:
        return await asyncio.to_thread(read_free_slots, account.entity, account.id)
    except Exception:  # noqa: BLE001 -- slots are a nicety; the reply is drafted without them
        logger.exception("Reading free slots for Lace %s failed", lace.id)
        return [], ""


async def add_meeting(db: AsyncSession, lace: Lace, meeting: dict) -> str | None:
    """Create the event (with a Meet link, inviting the contact). Only ever
    called from the user's explicit click. Returns the event's link."""
    account = await connection_service.connection_for(db, lace, "googlecalendar")
    if account is None:
        raise ConflictError("Connect Google Calendar (this Lace's settings) to add meetings.")
    start = datetime.fromisoformat(meeting["start"])
    minutes = int((datetime.fromisoformat(meeting["end"]) - start).total_seconds() // 60) or SLOT_MINUTES
    arguments = event_arguments(meeting.get("title") or "Meeting", start, minutes, meeting.get("timezone") or "UTC",
                                [meeting["attendee"]] if meeting.get("attendee") else [])
    result = await asyncio.to_thread(connection_service.execute_tool, account.entity, _CREATE_TOOL, arguments, account.id)
    if result.get("error"):
        raise ConflictError("Google Calendar didn't accept the meeting. Try again, or add it from Calendar.")
    data = result.get("data") or {}
    event = data.get("response_data") or data
    return event.get("htmlLink") or data.get("display_url")


def event_arguments(title: str, start: datetime, minutes: int, timezone: str, attendees: list[str],
                    description: str = "") -> dict:
    """GOOGLECALENDAR_CREATE_EVENT's arguments: a meeting with a Meet link,
    inviting `attendees` (emails), starting at `start` in `timezone`."""
    return {
        "summary": title, "start_datetime": start.strftime("%Y-%m-%dT%H:%M:%S"),
        "event_duration_hour": minutes // 60, "event_duration_minutes": minutes % 60, "timezone": timezone,
        "attendees": attendees, "description": description, "calendar_id": "primary", "create_meeting_room": True,
        "send_updates": "all",
    }
