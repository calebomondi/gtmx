"""The Lace's Slack tools: searching the team's messages, and a post as a
proposal the founder approves."""

import json

import pytest

from agents.lace.apps import AppError
from agents.lace.tools import build_tools


class Apps:
    def __init__(self, found=None, error=None):
        self.found, self.error = found, error

    async def slack_search(self, query):
        if self.error:
            raise AppError(self.error)
        return self.found


def _tools(store, settings, apps):
    return {t.name: t for t in build_tools(store, settings, apps=apps)}


async def _run(tool, **args) -> dict:
    return json.loads(await tool.ainvoke(args))


async def test_search_finds_the_teams_messages(store, settings):
    found = [{"text": "Acme wants a demo", "author": "wanjiru", "channel": "sales", "date": None, "link": None}]
    out = await _run(_tools(store, settings, Apps(found))["search_slack"], query="Acme in:#sales")
    assert out["ok"] and out["data"] == found


@pytest.mark.parametrize("apps, said", [(Apps(None), "isn't connected"), (Apps(error="Slack refused it"), "refused")])
async def test_search_failures_say_why(store, settings, apps, said):
    out = await _run(_tools(store, settings, apps)["search_slack"], query="x")
    assert not out["ok"] and said in out["error"]


async def test_a_post_is_a_proposal(store, settings):
    out = await _run(_tools(store, settings, Apps())["post_to_slack"], channel="#Sales", text="*Two* replies today.")
    [card] = out["data"]["ui"]
    assert (card["title"], card["preview"]) == ("Post in #sales on Slack", "*Two* replies today.")
    assert store.proposed[0].arguments == {"channel": "sales", "text": "*Two* replies today."}


@pytest.mark.parametrize("channel, text, said", [
    ("the sales one", "hi", "channel's name"), ("#sales", "  ", "empty"), ("#sales", "x" * 4001, "at most 4000"),
])
async def test_a_bad_post_is_refused(store, settings, channel, text, said):
    out = await _run(_tools(store, settings, Apps())["post_to_slack"], channel=channel, text=text)
    assert not out["ok"] and said in out["error"] and store.proposed == []
