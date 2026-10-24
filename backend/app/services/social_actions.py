"""The social actions a Lace can propose, run on the founder's approval
(lace_app_actions): posts on LinkedIn, X or the Facebook Page linked to the
Lace; replies to comments on the founder's own Instagram or Facebook posts;
replies, likes and reposts on X. Composio tools verified against the live
catalog (and, for LinkedIn and Instagram, read-only against a real account)."""

from backend.app.services import connections as connection_service
from backend.app.services.lace_app_actions import ActionFailed, Outcome, RunContext, call, runs
from backend.app.services.lace_channels import items


def _id(data) -> str | None:
    return connection_service.response_field(data, "id")


@runs("linkedin", "publish_post")
async def linkedin_post(ctx: RunContext, arguments: dict) -> Outcome:
    me = await call(ctx, "LINKEDIN_GET_MY_INFO", {})
    person = _id(me["data"])
    if not person:
        raise ActionFailed("LinkedIn didn't say who you are; reconnect LinkedIn and try again.")
    done = await call(ctx, "LINKEDIN_CREATE_LINKED_IN_POST", {
        "author": f"urn:li:person:{person}", "commentary": arguments["text"],
        "visibility": "PUBLIC", "lifecycleState": "PUBLISHED"})
    post = _id(done["data"])
    return Outcome("Posted on LinkedIn.", f"https://www.linkedin.com/feed/update/{post}" if post else None, done["log_id"])


async def _x_post(ctx: RunContext, arguments: dict, said: str) -> Outcome:
    done = await call(ctx, "TWITTER_CREATION_OF_A_POST", arguments)
    post = _id(done["data"])
    return Outcome(said, f"https://x.com/i/web/status/{post}" if post else None, done["log_id"])


@runs("x", "publish_post")
async def x_post(ctx: RunContext, arguments: dict) -> Outcome:
    return await _x_post(ctx, {"text": arguments["text"]}, "Posted on X.")


@runs("x", "reply")
async def x_reply(ctx: RunContext, arguments: dict) -> Outcome:
    return await _x_post(ctx, {"text": arguments["text"], "reply__in__reply__to__tweet__id": arguments["post_id"]},
                         "Replied on X.")


async def _x_me(ctx: RunContext) -> str:
    me = _id((await call(ctx, "TWITTER_USER_LOOKUP_ME", {}))["data"])
    if not me:
        raise ActionFailed("X didn't say who you are; reconnect X and try again.")
    return me


@runs("x", "like")
async def x_like(ctx: RunContext, arguments: dict) -> Outcome:
    done = await call(ctx, "TWITTER_USER_LIKE_POST", {"id": await _x_me(ctx), "tweet_id": arguments["post_id"]})
    return Outcome("Liked on X.", arguments.get("url"), done["log_id"])


@runs("x", "repost")
async def x_repost(ctx: RunContext, arguments: dict) -> Outcome:
    done = await call(ctx, "TWITTER_RETWEET_POST", {"id": await _x_me(ctx), "tweet_id": arguments["post_id"]})
    return Outcome("Reposted on X.", arguments.get("url"), done["log_id"])


async def facebook_page(ctx: RunContext) -> str:
    """The Page to act as: the one linked to this Lace, else the only Page the
    founder manages."""
    if ctx.linked_account:
        return ctx.linked_account
    pages = items((await call(ctx, "FACEBOOK_LIST_MANAGED_PAGES", {}))["data"])
    if len(pages) != 1:
        raise ActionFailed("Pick the Facebook Page this Lace uses: link it under Messaging → Inboxes.")
    return str(pages[0]["id"])


@runs("facebook", "publish_post")
async def facebook_post(ctx: RunContext, arguments: dict) -> Outcome:
    done = await call(ctx, "FACEBOOK_CREATE_POST", {"page_id": await facebook_page(ctx), "message": arguments["text"],
                                                    "published": True})
    post = _id(done["data"])
    return Outcome("Posted on your Facebook Page.", f"https://www.facebook.com/{post}" if post else None, done["log_id"])


@runs("facebook", "reply_to_comment")
async def facebook_reply(ctx: RunContext, arguments: dict) -> Outcome:
    done = await call(ctx, "FACEBOOK_CREATE_COMMENT", {"object_id": arguments["comment_id"], "message": arguments["text"]})
    return Outcome("Replied to the comment on Facebook.", arguments.get("url"), done["log_id"])


@runs("instagram", "reply_to_comment")
async def instagram_reply(ctx: RunContext, arguments: dict) -> Outcome:
    done = await call(ctx, "INSTAGRAM_REPLY_TO_COMMENT", {"ig_comment_id": arguments["comment_id"],
                                                          "message": arguments["text"]})
    return Outcome("Replied to the comment on Instagram.", arguments.get("url"), done["log_id"])
