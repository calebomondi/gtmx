"""The Lace's social tools beyond reading: posting, replying and engaging on
the founder's own accounts, all as proposals the founder approves (nothing
runs until they click), and reading the comments on their own posts to find
the people worth reaching out to."""

from typing import Literal

from langchain_core.tools import BaseTool, tool

from agents.lace.app_actions import propose
from agents.lace.apps import AppError, CommentsOn, LaceApps, PublicFeed
from agents.lace.social_stats import summarise_posts
from agents.lace.store import LaceStore
from agents.lace.tool_guard import guarded
from agents.schemas.lace import ProposedAction, ToolResult
from data_sources.socials import x_api
from data_sources.socials.read import classify

# The most each platform takes in one post or reply.
TEXT_LIMITS = {"x": 280, "linkedin": 3000, "facebook": 5000, "instagram": 2200}
LABELS = {"x": "X", "linkedin": "LinkedIn", "facebook": "Facebook", "instagram": "Instagram", "tiktok": "TikTok"}
MAX_POSTS_READ = 10


def _too_long(platform: str, text: str) -> ToolResult | None:
    if not text.strip():
        return ToolResult.failure("The text is empty.")
    limit = TEXT_LIMITS[platform]
    return ToolResult.failure(f"{LABELS[platform]} takes at most {limit} characters; this is {len(text)}.") \
        if len(text) > limit else None


def build_social_tools(store: LaceStore, apps: LaceApps) -> list[BaseTool]:

    @tool(parse_docstring=True)
    @guarded
    async def post_on_social(platform: Literal["linkedin", "x", "facebook"], text: str) -> ToolResult:
        """Propose a post on the founder's LinkedIn, X, or the Facebook Page linked to you, in their voice. It is posted only if they approve it under your reply. Instagram posts need an image, which you can't add.

        Args:
            platform: Where to post.
            text: The post, exactly as it will appear.
        """
        if (refused := _too_long(platform, text)) is not None:
            return refused
        return await propose(store, ProposedAction(
            app=platform, action="publish_post", title=f"Post on {LABELS[platform]}", preview=text.strip(),
            arguments={"text": text.strip()}))

    @tool(parse_docstring=True)
    @guarded
    async def reply_to_comment(platform: CommentsOn, comment_id: str, text: str, comment: str = "",
                               post_url: str | None = None) -> ToolResult:
        """Propose a reply to a comment on the founder's own Instagram or Facebook post (from read_my_comments). It is sent only if they approve it.

        Args:
            platform: Where the comment is.
            comment_id: The comment's id, from read_my_comments.
            text: The reply, in the founder's voice.
            comment: The comment being answered, so the founder sees what it replies to.
            post_url: The post's link, from read_my_comments.
        """
        if (refused := _too_long(platform, text)) is not None:
            return refused
        preview = (f"Replying to: “{comment.strip()}”\n\n" if comment.strip() else "") + text.strip()
        return await propose(store, ProposedAction(
            app=platform, action="reply_to_comment", title=f"Reply to a comment on {LABELS[platform]}", preview=preview,
            arguments={"comment_id": comment_id, "text": text.strip(), "url": post_url}))

    @tool(parse_docstring=True)
    @guarded
    async def engage_on_x(action: Literal["reply", "like", "repost"], post_url: str, text: str = "") -> ToolResult:
        """Propose replying to, liking or reposting a post on X from the founder's account, e.g. a prospect's or partner's post. It runs only if they approve it.

        Args:
            action: reply (needs text), like or repost.
            post_url: The post's link, x.com/<handle>/status/<id>.
            text: The reply, for action reply.
        """
        link = classify(post_url)
        if link is None or link.platform != "x" or link.kind != "post":
            return ToolResult.failure("Give the link of a post on X: x.com/<handle>/status/<id>.")
        arguments = {"post_id": x_api.key(link.url, "post"), "url": link.url}
        if action == "reply":
            if (refused := _too_long("x", text)) is not None:
                return refused
            arguments["text"] = text.strip()
        titles = {"reply": "Reply on X", "like": "Like a post on X", "repost": "Repost on X"}
        preview = text.strip() if action == "reply" else link.url
        return await propose(store, ProposedAction(app="x", action=action, title=titles[action], preview=preview,
                                                   arguments=arguments))

    @tool(parse_docstring=True)
    @guarded
    async def how_my_posts_did(platform: PublicFeed) -> ToolResult:
        """How the founder's recent public posts on X, or videos on TikTok, did: views, likes and the rest, totalled and averaged exactly, and the ones that did best. Quote these numbers. Read from their public profile by the handle saved in your settings; nothing needs connecting.

        Args:
            platform: x or tiktok.
        """
        try:
            posts = await apps.my_posts(platform)
        except AppError as exc:
            return ToolResult.failure(str(exc))
        if posts is None:
            return ToolResult.failure(f"No {LABELS[platform]} handle is saved for you. Ask the founder for it, or they "
                                      f"can add it under Apps & accounts → {LABELS[platform]} in your settings.")
        if not posts:
            return ToolResult.success(f"No public posts found on that {LABELS[platform]} account.", [])
        summary = summarise_posts(posts)
        return ToolResult.success(f"{summary['posts']} recent {LABELS[platform]} posts.", summary)

    @tool(parse_docstring=True)
    @guarded
    async def read_my_comments(platform: CommentsOn, posts: int = 5) -> ToolResult:
        """Read the comments on the founder's own recent Instagram or Facebook posts: who is engaging, and what they said. Use it to spot warm leads and questions worth answering.

        Args:
            platform: Whose comments to read.
            posts: How many of their most recent posts to read (1 to 10).
        """
        try:
            comments = await apps.my_comments(platform, max(1, min(posts, MAX_POSTS_READ)))
        except AppError as exc:
            return ToolResult.failure(str(exc))
        if comments is None:
            return ToolResult.failure(f"The founder hasn't connected {LABELS[platform]} (Accounts page).")
        if not comments:
            return ToolResult.success(f"No comments on their last {posts} {LABELS[platform]} posts.", [])
        return ToolResult.success(f"{len(comments)} comments on their recent {LABELS[platform]} posts.", comments)

    return [post_on_social, reply_to_comment, engage_on_x, read_my_comments, how_my_posts_did]
