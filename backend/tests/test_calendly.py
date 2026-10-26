"""Calendly through a stubbed Composio, as Calendly's documented response
shapes: the founder's booking links and the meetings booked with them."""

from backend.app.database.connect import AsyncSessionLocal
from backend.app.services import lace_apps
from backend.tests.helpers import stub_accounts
from backend.tests.test_lace_apps import _lace
from backend.tests.test_social_actions import composio  # noqa: F401 -- fixture

ME = {"resource": {"uri": "https://api.calendly.com/users/U1"}}


async def test_booking_links_are_the_active_meeting_types(composio, monkeypatch):  # noqa: F811
    stub_accounts(monkeypatch, {"calendly"})
    composio["answers"] = {"CALENDLY_GET_CURRENT_USER": ME, "CALENDLY_LIST_USER_S_EVENT_TYPES": {"collection": [
        {"name": "Intro call", "duration": 30, "scheduling_url": "https://calendly.com/acme/intro"}]}}
    assert await lace_apps.DbLaceApps(AsyncSessionLocal, _lace()).calendly_links() == [
        {"name": "Intro call", "minutes": 30, "url": "https://calendly.com/acme/intro"}]
    assert composio["calls"][1][1] == {"user": "https://api.calendly.com/users/U1", "active": True, "count": 100}


async def test_meetings_come_with_who_booked(composio, monkeypatch):  # noqa: F811
    stub_accounts(monkeypatch, {"calendly"})
    composio["answers"] = {
        "CALENDLY_GET_CURRENT_USER": {"data": ME},  # wrapped or not, it reads the same
        "CALENDLY_LIST_EVENTS": {"collection": [{"uri": "https://api.calendly.com/scheduled_events/E1",
                                                 "name": "Intro call", "start_time": "2026-10-25T09:00:00Z"}]},
        "CALENDLY_LIST_EVENT_INVITEES": {"collection": [{"name": "Joe Kamau", "email": "joe@acme.test"}]},
    }
    meetings = await lace_apps.DbLaceApps(AsyncSessionLocal, _lace()).calendly_meetings(7, 14)
    assert meetings == [{"name": "Intro call", "start": "2026-10-25T09:00:00Z",
                         "invitees": [{"name": "Joe Kamau", "email": "joe@acme.test"}]}]
    assert composio["calls"][2] == ("CALENDLY_LIST_EVENT_INVITEES", {"uuid": "E1", "status": "active"})
