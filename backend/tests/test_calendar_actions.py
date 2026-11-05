"""Calendar changes the founder approves, through a stubbed Composio: a new
meeting with a Meet link and its guests, a meeting moved, one cancelled."""

import pytest

from backend.app.services import calendar_actions
from backend.app.services.lace_app_actions import ActionFailed
from backend.app.services.lace_apps import _meeting
from backend.tests.test_social_actions import _ctx, composio  # noqa: F401 -- fixture


async def test_a_new_meeting_invites_its_guests_with_a_meet_link(composio):  # noqa: F811
    composio["answers"] = {"GOOGLECALENDAR_GET_CALENDAR_PROFILE": {"timeZone": "Africa/Nairobi"},
                           "GOOGLECALENDAR_CREATE_EVENT": {"response_data": {"htmlLink": "https://calendar.test/e1"}}}
    outcome = await calendar_actions.create_event(_ctx("googlecalendar"), {
        "title": "Thalace demo with Acme", "start": "2026-11-10T14:00", "minutes": 45,
        "attendees": ["jane@acme.test"], "agenda": "Walk through leads."})
    assert composio["calls"][1] == ("GOOGLECALENDAR_CREATE_EVENT", {
        "summary": "Thalace demo with Acme", "start_datetime": "2026-11-10T14:00:00", "event_duration_hour": 0,
        "event_duration_minutes": 45, "timezone": "Africa/Nairobi", "attendees": ["jane@acme.test"],
        "description": "Walk through leads.", "calendar_id": "primary", "create_meeting_room": True,
        "send_updates": "all"})
    assert outcome.url == "https://calendar.test/e1" and "Africa/Nairobi" in outcome.result


async def test_moving_and_cancelling_tell_the_guests(composio):  # noqa: F811
    composio["answers"] = {"GOOGLECALENDAR_PATCH_EVENT": {"htmlLink": "https://calendar.test/e2"}}
    moved = await calendar_actions.move_event(_ctx("googlecalendar"), {
        "event_id": "e2", "title": "Pilot review", "start": "2026-11-11T09:30", "minutes": 30, "timezone": "UTC"})
    assert composio["calls"][0] == ("GOOGLECALENDAR_PATCH_EVENT", {
        "calendar_id": "primary", "event_id": "e2", "start_time": "2026-11-11T09:30:00",
        "end_time": "2026-11-11T10:00:00", "timezone": "UTC", "send_updates": "all"})
    assert moved.url == "https://calendar.test/e2"
    cancelled = await calendar_actions.cancel_event(_ctx("googlecalendar"), {"event_id": "e2", "title": "Pilot review"})
    assert composio["calls"][1] == ("GOOGLECALENDAR_DELETE_EVENT", {
        "calendar_id": "primary", "event_id": "e2", "send_updates": "all"})
    assert cancelled.result == "Cancelled \"Pilot review\"; guests are told."


async def test_a_refused_change_says_why(composio):  # noqa: F811
    composio["answers"] = {"GOOGLECALENDAR_DELETE_EVENT": {"error": "404 Not Found"}}
    with pytest.raises(ActionFailed, match="Google Calendar refused it: 404"):
        await calendar_actions.cancel_event(_ctx("googlecalendar"), {"event_id": "gone", "title": "x"})


def test_a_meeting_comes_with_what_preparing_needs():
    event = {"id": "e1", "summary": "Call", "start": {"dateTime": "2026-11-10T14:00:00+03:00"},
             "end": {"dateTime": "2026-11-10T14:30:00+03:00"}, "location": "Westlands", "description": "Agenda",
             "hangoutLink": "https://meet.google.com/abc", "organizer": {"email": "me@thalace.com"},
             "attendees": [{"email": "me@thalace.com", "self": True},
                           {"email": "jane@acme.test", "displayName": "Jane", "responseStatus": "accepted"}]}
    assert _meeting(event) == {
        "id": "e1", "title": "Call", "start": "2026-11-10T14:00:00+03:00", "end": "2026-11-10T14:30:00+03:00",
        "location": "Westlands", "join": "https://meet.google.com/abc", "description": "Agenda",
        "organizer": "me@thalace.com", "attendees": [{"name": "Jane", "email": "jane@acme.test", "response": "accepted"}]}
