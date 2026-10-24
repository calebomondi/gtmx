"""The social actions a founder approves, run through a stubbed Composio as
its documented and observed response shapes; and reading the comments on
their own posts."""

import uuid

import pytest

from backend.app.services import connections as connection_service
from backend.app.services import lace_apps, social_actions
from backend.app.services.lace_app_actions import ActionFailed, RunContext


@pytest.fixture
def composio(monkeypatch):
    """`box["answers"]`: tool -> data (or an exception, or {"error": ...})."""
    box = {"calls": [], "answers": {}}

    def execute(user_id, tool, arguments, connection_id):
        box["calls"].append((tool, arguments))
        answer = box["answers"].get(tool, {})
        if isinstance(answer, Exception):
            raise answer
        if isinstance(answer, dict) and "error" in answer:
            return {"data": None, "error": answer["error"], "log_id": None}
        return {"data": answer, "error": None, "log_id": "log_9"}
    monkeypatch.setattr(connection_service, "execute_tool", execute)
    return box


def _ctx(app, linked=None):
    return RunContext(uuid.uuid4(), uuid.uuid4(), app, f"ca_{app}", linked)


async def test_a_linkedin_post_is_by_the_founder(composio):
    composio["answers"] = {"LINKEDIN_GET_MY_INFO": {"id": "abc123"}, "LINKEDIN_CREATE_LINKED_IN_POST": {"id": "urn:li:share:7"}}
    outcome = await social_actions.linkedin_post(_ctx("linkedin"), {"text": "We opened in Nakuru."})
    assert composio["calls"][1] == ("LINKEDIN_CREATE_LINKED_IN_POST", {
        "author": "urn:li:person:abc123", "commentary": "We opened in Nakuru.", "visibility": "PUBLIC",
        "lifecycleState": "PUBLISHED"})
    assert (outcome.result, outcome.url, outcome.log_id) == (
        "Posted on LinkedIn.", "https://www.linkedin.com/feed/update/urn:li:share:7", "log_9")


async def test_x_likes_and_replies(composio):
    composio["answers"] = {"TWITTER_USER_LOOKUP_ME": {"data": {"id": "u1"}}, "TWITTER_CREATION_OF_A_POST": {"data": {"id": "99"}}}
    await social_actions.x_like(_ctx("x"), {"post_id": "42"})
    assert composio["calls"][-1] == ("TWITTER_USER_LIKE_POST", {"id": "u1", "tweet_id": "42"})
    reply = await social_actions.x_reply(_ctx("x"), {"post_id": "42", "text": "Congrats!"})
    assert composio["calls"][-1] == ("TWITTER_CREATION_OF_A_POST", {"text": "Congrats!", "reply__in__reply__to__tweet__id": "42"})
    assert reply.url == "https://x.com/i/web/status/99"


async def test_a_facebook_post_goes_to_the_page_linked_to_the_lace(composio):
    composio["answers"] = {"FACEBOOK_CREATE_POST": {"id": "pg_1_5"},
                           "FACEBOOK_LIST_MANAGED_PAGES": {"data": [{"id": "pg_2"}, {"id": "pg_3"}]}}
    await social_actions.facebook_post(_ctx("facebook", linked="pg_1"), {"text": "Hello"})
    assert composio["calls"][-1] == ("FACEBOOK_CREATE_POST", {"page_id": "pg_1", "message": "Hello", "published": True})
    # Not linked, and two Pages to choose from: the founder picks one.
    with pytest.raises(ActionFailed, match="link it under Messaging"):
        await social_actions.facebook_post(_ctx("facebook"), {"text": "Hello"})
    composio["answers"]["FACEBOOK_LIST_MANAGED_PAGES"] = {"data": [{"id": "pg_4"}]}
    await social_actions.facebook_post(_ctx("facebook"), {"text": "Hello"})
    assert composio["calls"][-1][1]["page_id"] == "pg_4"


async def test_comment_replies(composio):
    await social_actions.instagram_reply(_ctx("instagram"), {"comment_id": "c9", "text": "Thanks!"})
    assert composio["calls"][-1] == ("INSTAGRAM_REPLY_TO_COMMENT", {"ig_comment_id": "c9", "message": "Thanks!"})
    await social_actions.facebook_reply(_ctx("facebook"), {"comment_id": "c8", "text": "Thanks!"})
    assert composio["calls"][-1] == ("FACEBOOK_CREATE_COMMENT", {"object_id": "c8", "message": "Thanks!"})


async def test_a_refusal_says_whose_and_why(composio):
    composio["answers"] = {"TWITTER_CREATION_OF_A_POST": {"error": "403 duplicate content"}}
    with pytest.raises(ActionFailed, match="X refused it: 403 duplicate content"):
        await social_actions.x_post(_ctx("x"), {"text": "Hello"})


async def test_comments_on_own_instagram_posts(composio, monkeypatch):
    async def live(self, platform):
        return lace_apps._Live(uuid.uuid4(), "ca_ig", "ig_1")
    monkeypatch.setattr(lace_apps.DbLaceApps, "_live", live)
    composio["answers"] = {
        "INSTAGRAM_GET_USER_MEDIA": {"data": [
            {"id": "m1", "permalink": "https://instagram.com/p/1", "caption": "Launch day", "comments_count": 1},
            {"id": "m2", "permalink": "https://instagram.com/p/2", "caption": "Quiet one", "comments_count": 0}]},
        "INSTAGRAM_GET_POST_COMMENTS": {"data": [
            {"id": "c1", "username": "farmer_joe", "text": "Price?", "timestamp": "2026-10-20T10:00:00+0000"}]},
    }
    found = await lace_apps.DbLaceApps(None, uuid.uuid4()).my_comments("instagram", 5)
    assert found == [{"platform": "instagram", "post_url": "https://instagram.com/p/1", "post_text": "Launch day",
                      "comment_id": "c1", "author": "farmer_joe", "text": "Price?", "date": "2026-10-20T10:00:00+0000"}]
    # Only posts with comments are read for them, and the linked account's.
    assert [c[0] for c in composio["calls"]] == ["INSTAGRAM_GET_USER_MEDIA", "INSTAGRAM_GET_POST_COMMENTS"]
    assert composio["calls"][0][1]["ig_user_id"] == "ig_1"


def test_every_social_action_has_a_runner():
    from backend.app.services.lace_app_actions import RUNNERS
    for key in [("linkedin", "publish_post"), ("x", "publish_post"), ("x", "reply"), ("x", "like"), ("x", "repost"),
                ("facebook", "publish_post"), ("facebook", "reply_to_comment"), ("instagram", "reply_to_comment")]:
        assert key in RUNNERS
