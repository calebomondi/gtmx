"""Free slots offered in replies: one per working day, inside working hours,
not in the next two hours."""

from datetime import datetime
from zoneinfo import ZoneInfo

from backend.app.services.calendar import pick_slots

NAIROBI = ZoneInfo("Africa/Nairobi")


def test_one_slot_per_working_day_inside_hours():
    now = datetime(2026, 10, 15, 6, 10, tzinfo=ZoneInfo("UTC"))  # Thu 09:10 Nairobi
    free = [
        {"start": "2026-10-15T07:00:00Z", "end": "2026-10-15T15:00:00Z"},  # Thu 10:00-18:00
        {"start": "2026-10-17T06:00:00Z", "end": "2026-10-17T14:00:00Z"},  # Saturday: skipped
        {"start": "2026-10-20T04:00:00Z", "end": "2026-10-20T06:45:00Z"},  # Tue 07:00-09:45
        {"start": "2026-10-21T13:40:00Z", "end": "2026-10-21T14:20:00Z"},  # Wed 16:40-17:20: no 30 min fits
        {"start": "2026-10-22T09:15:00Z", "end": "2026-10-22T12:00:00Z"},  # Thu 12:15-15:00
    ]
    slots = pick_slots(free, NAIROBI, now)
    assert [s.strftime("%a %H:%M") for s in slots] == ["Thu 11:30", "Tue 09:00", "Thu 12:30"]


def test_no_free_time_means_no_slots():
    assert pick_slots([], NAIROBI, datetime(2026, 10, 15, tzinfo=NAIROBI)) == []
