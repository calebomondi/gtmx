"""The Lace reads the founder's mail, calendar and X mentions only through
the apps on for it, and says so plainly when one isn't."""

import json

from agents.lace.apps import AppError
from agents.lace.inbox_tools import build_inbox_tools


class Apps:
    def __init__(self, mail=None, events=None, mentions=None, fails=None):
        self.mail, self.events, self.mentions, self.fails, self.asked = mail, events, mentions, fails, []

    async def email_search(self, query, days):
        self.asked.append((query, days))
        if self.fails:
            raise AppError(self.fails)
        return self.mail

    async def email_thread(self, thread_id):
        return self.mail

    async def calendar_events(self, days_ahead):
        self.asked.append(days_ahead)
        return self.events

    async def x_mentions(self):
        return self.mentions


async def _call(apps, name, **args) -> dict:
    return json.loads(await {t.name: t for t in build_inbox_tools(apps)}[name].ainvoke(args))


async def test_searching_mail_bounds_the_window_and_lists_what_matched():
    apps = Apps(mail=[{"thread_id": "t1", "from": "jane@acme.test", "subject": "Pilot"}])
    out = await _call(apps, "search_email", query="  from:jane@acme.test ", days=400)
    assert out["ok"] and out["data"][0]["thread_id"] == "t1" and apps.asked == [("from:jane@acme.test", 90)]
    assert (await _call(Apps(mail=[]), "search_email", query="x"))["summary"] == "No mail matched in the last 30 days."


async def test_an_app_that_isnt_on_or_refuses_is_said_plainly():
    off = await _call(Apps(), "search_email", query="x")
    assert not off["ok"] and "Gmail isn't connected for this Lace" in off["summary"]
    assert "Google Calendar isn't connected" in (await _call(Apps(), "my_calendar"))["summary"]
    assert "X isn't connected" in (await _call(Apps(), "my_x_mentions"))["summary"]
    refused = await _call(Apps(fails="This Gmail is the Lace owner's own account"), "search_email", query="x")
    assert not refused["ok"] and "owner's own account" in refused["summary"]


async def test_calendar_and_mentions():
    apps = Apps(events=[{"title": "Call with Acme"}], mentions=[])
    out = await _call(apps, "my_calendar", days_ahead=99)
    assert out["summary"] == "1 events in the next 30 days." and apps.asked == [30]
    assert (await _call(apps, "my_x_mentions"))["summary"] == "No recent mentions on X."
    missing = await _call(Apps(mail=[]), "read_email_thread", thread_id="nope")
    assert not missing["ok"] and "No thread has the id nope" in missing["summary"]
