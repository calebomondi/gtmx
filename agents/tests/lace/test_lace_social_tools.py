"""The Lace's social tools: every post, reply and like is a proposal the
founder approves, checked for each platform's limits; comments on their own
posts are read through their connected apps."""

import json

import pytest

from agents.lace.apps import AppError
from agents.lace.tools import build_tools


class Apps:
    def __init__(self, comments=None, error=None):
        self.comments, self.error = comments, error

    async def x(self, record, key):
        return None

    async def my_comments(self, platform, posts):
        if self.error:
            raise AppError(self.error)
        return self.comments


def _tools(store, settings, apps):
    return {t.name: t for t in build_tools(store, settings, apps=apps)}


async def _run(tool, **args) -> dict:
    return json.loads(await tool.ainvoke(args))


async def test_without_apps_the_lace_has_no_social_actions(store, settings):
    names = set(_tools(store, settings, None))
    assert not names & {"post_on_social", "reply_to_comment", "engage_on_x", "read_my_comments"}


async def test_a_post_is_a_proposal_with_its_card(store, settings):
    out = await _run(_tools(store, settings, Apps())["post_on_social"], platform="linkedin", text=" We opened in Nakuru. ")
    [card] = out["data"]["ui"]
    assert out["ok"] and (card["type"], card["title"], card["preview"], card["status"]) == (
        "action", "Post on LinkedIn", "We opened in Nakuru.", "proposed")
    [proposal] = store.proposed
    assert (proposal.app, proposal.action, proposal.arguments) == ("linkedin", "publish_post", {"text": "We opened in Nakuru."})


async def test_each_platforms_length_limit_is_kept(store, settings):
    out = await _run(_tools(store, settings, Apps())["post_on_social"], platform="x", text="x" * 281)
    assert not out["ok"] and "at most 280" in out["error"] and store.proposed == []


async def test_a_comment_reply_shows_what_it_answers(store, settings):
    out = await _run(_tools(store, settings, Apps())["reply_to_comment"], platform="instagram", comment_id="c9",
                     text="Thanks Joe! DM us.", comment="Do you ship to Kisumu?", post_url="https://instagram.com/p/1")
    assert out["data"]["ui"][0]["preview"] == "Replying to: “Do you ship to Kisumu?”\n\nThanks Joe! DM us."
    assert store.proposed[0].arguments == {"comment_id": "c9", "text": "Thanks Joe! DM us.", "url": "https://instagram.com/p/1"}


@pytest.mark.parametrize("args, ok, arguments", [
    ({"action": "like", "post_url": "https://x.com/acme/status/42"}, True, {"post_id": "42", "url": "https://x.com/acme/status/42"}),
    ({"action": "reply", "post_url": "https://x.com/acme/status/42", "text": "Congrats!"}, True,
     {"post_id": "42", "url": "https://x.com/acme/status/42", "text": "Congrats!"}),
    ({"action": "reply", "post_url": "https://x.com/acme/status/42"}, False, None),
    ({"action": "like", "post_url": "https://www.instagram.com/p/AbC"}, False, None),
])
async def test_x_engagement_needs_an_x_post(store, settings, args, ok, arguments):
    out = await _run(_tools(store, settings, Apps())["engage_on_x"], **args)
    assert out["ok"] is ok
    assert (store.proposed[0].arguments if ok else store.proposed) == (arguments if ok else [])


async def test_comments_on_own_posts_are_read_through_the_apps(store, settings):
    comment = {"platform": "instagram", "comment_id": "c1", "author": "farmer_joe", "text": "Price?"}
    out = await _run(_tools(store, settings, Apps(comments=[comment]))["read_my_comments"], platform="instagram")
    assert out["ok"] and out["data"] == [comment]
    missing = await _run(_tools(store, settings, Apps(comments=None))["read_my_comments"], platform="facebook")
    assert not missing["ok"] and "hasn't connected Facebook" in missing["error"]
    failed = await _run(_tools(store, settings, Apps(error="Instagram refused it (rate limit)"))["read_my_comments"],
                        platform="instagram")
    assert failed["error"] == "Instagram refused it (rate limit)"
