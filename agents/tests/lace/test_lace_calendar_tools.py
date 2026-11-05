"""Calendar changes are proposals the founder approves; free times come from
their calendar, bounded."""

import json

from agents.lace.calendar_tools import build_calendar_tools
from lace_fakes import MemoryStore


class Apps:
    def __init__(self, free=None):
        self.free, self.asked = free, []

    async def calendar_free_times(self, days, minutes):
        self.asked.append((days, minutes))
        return self.free


async def _call(store, apps, name, **args) -> dict:
    return json.loads(await {t.name: t for t in build_calendar_tools(store, apps)}[name].ainvoke(args))


async def test_free_times_are_bounded_and_say_when_none():
    apps = Apps({"timezone": "Africa/Nairobi", "slots": ["Mon 10 Nov, 14:00-14:30 (Africa/Nairobi)"]})
    out = await _call(MemoryStore(), apps, "find_free_times", days_ahead=90, minutes=5)
    assert out["summary"] == "1 free times, in Africa/Nairobi." and apps.asked == [(30, 15)]
    assert "isn't connected" in (await _call(MemoryStore(), Apps(), "find_free_times"))["summary"]


async def test_a_meeting_is_proposed_not_made():
    store = MemoryStore()
    out = await _call(store, Apps(), "schedule_meeting", title="Thalace demo", start="2026-11-10T14:00", minutes=45,
                      attendees=[" Jane@Acme.test ", "jane@acme.test"], agenda="Leads walkthrough")
    assert out["ok"] and out["data"]["ui"][0]["status"] == "proposed"
    [action] = store.proposed
    assert (action.app, action.action) == ("googlecalendar", "create_event")
    assert action.arguments == {"title": "Thalace demo", "start": "2026-11-10T14:00", "minutes": 45,
                                "attendees": ["jane@acme.test"], "agenda": "Leads walkthrough"}
    assert action.preview.startswith("Tue 10 Nov 2026, 14:00, 45 minutes, with a Google Meet link\nWith: jane@acme.test")


async def test_bad_times_and_addresses_are_refused():
    store = MemoryStore()
    assert "YYYY-MM-DDTHH:MM" in (await _call(store, Apps(), "schedule_meeting", title="x", start="next tuesday"))["summary"]
    bad = await _call(store, Apps(), "schedule_meeting", title="x", start="2026-11-10T14:00", attendees=["jane"])
    assert bad["summary"] == "Not an email address: jane." and store.proposed == []


async def test_moving_and_cancelling_are_proposed():
    store = MemoryStore()
    await _call(store, Apps(), "reschedule_meeting", event_id="e1", title="Pilot review", start="2026-11-11T09:30")
    await _call(store, Apps(), "cancel_meeting", event_id="e1", title="Pilot review")
    assert [(a.action, a.title) for a in store.proposed] == [("move_event", "Move \"Pilot review\""),
                                                            ("cancel_event", "Cancel \"Pilot review\"")]
