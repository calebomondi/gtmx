"""The Lace's Calendly tools: booking links for drafts, and booked meetings
with the Lace's contacts marked."""

import json

from agents.lace.tools import build_tools
from agents.schemas.lace import ContactSummary


class Apps:
    def __init__(self, links=None, meetings=None):
        self.links, self.meetings, self.window = links, meetings, None

    async def calendly_links(self):
        return self.links

    async def calendly_meetings(self, days_back, days_ahead):
        self.window = (days_back, days_ahead)
        return self.meetings


def _tools(store, settings, apps):
    return {t.name: t for t in build_tools(store, settings, apps=apps)}


async def _run(tool, **args) -> dict:
    return json.loads(await tool.ainvoke(args))


async def test_booking_links(store, settings):
    links = [{"name": "Intro call", "minutes": 30, "url": "https://calendly.com/acme/intro"}]
    out = await _run(_tools(store, settings, Apps(links=links))["booking_links"])
    assert out["ok"] and out["data"] == links


async def test_meetings_mark_the_lace_s_contacts(store, settings):
    store.people = [ContactSummary(id="p1", name="Joe Kamau", email="Joe@Acme.test", company="Acme",
                                   account_id="a1", approved=True)]
    apps = Apps(meetings=[{"name": "Intro call", "start": "2026-10-25T09:00:00Z",
                           "invitees": [{"name": "Joe", "email": "joe@acme.test"}]},
                          {"name": "Intro call", "start": "2026-10-26T09:00:00Z",
                           "invitees": [{"name": "Stranger", "email": "x@y.test"}]}])
    out = await _run(_tools(store, settings, apps)["calendly_meetings"], days_back=500)
    assert out["summary"] == "2 meetings, 1 with your contacts."
    assert out["data"][0]["invitees"][0]["contact"] == "Joe Kamau at Acme"
    assert out["data"][1]["invitees"][0]["contact"] is None
    assert apps.window == (60, 14)


async def test_without_calendly_it_says_so(store, settings):
    out = await _run(_tools(store, settings, Apps())["booking_links"])
    assert not out["ok"] and "isn't connected" in out["error"]
