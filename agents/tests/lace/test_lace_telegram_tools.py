"""The Lace's Telegram tools: a post to the startup's channel is a proposal
the founder approves."""

import json

import pytest

from agents.lace.telegram_tools import chat_target
from agents.lace.tools import build_tools


@pytest.mark.parametrize("given, target", [
    ("@shanga_team", "@shanga_team"), ("https://t.me/shanga_team", "@shanga_team"), ("t.me/shanga_team/", "@shanga_team"),
    ("-1001234567890", "-1001234567890"), ("123456789", "123456789"),
    ("shanga team", None), ("@abc", None), ("https://example.com/shanga", None),
])
def test_chat_targets(given, target):
    assert chat_target(given) == target


async def _post(store, settings, **args) -> dict:
    tools = {t.name: t for t in build_tools(store, settings, apps=object())}
    return json.loads(await tools["post_to_telegram"].ainvoke(args))


async def test_a_post_is_a_proposal(store, settings):
    out = await _post(store, settings, channel="t.me/shanga_team", text=" Pilot starts Monday. ")
    assert out["data"]["ui"][0]["title"] == "Post in @shanga_team on Telegram"
    assert store.proposed[0].arguments == {"chat_id": "@shanga_team", "text": "Pilot starts Monday."}


@pytest.mark.parametrize("channel, text, said", [
    ("our group", "hi", "@name"), ("@shanga_team", " ", "empty"), ("@shanga_team", "x" * 4097, "at most 4096"),
])
async def test_a_bad_post_is_refused(store, settings, channel, text, said):
    out = await _post(store, settings, channel=channel, text=text)
    assert not out["ok"] and said in out["error"] and store.proposed == []
