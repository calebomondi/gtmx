"""The Notion actions a Lace can propose, run on the founder's approval
(lace_app_actions): writing a new page under one the founder chose. Composio
tools verified against the live catalog (2026-10-24)."""

import re

from backend.app.services import connections as connection_service
from backend.app.services.lace_app_actions import ActionFailed, Outcome, RunContext, call, runs

# Notion takes at most 100 blocks per call and 2000 characters per text.
BLOCKS_PER_CALL = 100
TEXT_CHARS = 2000
_LINE_KINDS = (
    (re.compile(r"^### +"), "heading_3"), (re.compile(r"^## +"), "heading_2"), (re.compile(r"^# +"), "heading_1"),
    (re.compile(r"^[-*] +\[ \] +|^\[ \] +"), "to_do"), (re.compile(r"^[-*] +"), "bulleted_list_item"),
    (re.compile(r"^\d+[.)] +"), "numbered_list_item"), (re.compile(r"^> +"), "quote"),
)


def blocks(markdown: str) -> list[dict]:
    """The page's lines as Composio's flattened Notion blocks (Composio reads
    the inline markdown: bold, italics, links)."""
    out = []
    for line in markdown.splitlines():
        if not line.strip():
            continue
        kind, text = "paragraph", line.strip()
        for pattern, name in _LINE_KINDS:
            if pattern.match(text):
                kind, text = name, pattern.sub("", text, count=1)
                break
        out += [{"content_block": {"content": text[i:i + TEXT_CHARS], "block_property": kind}}
                for i in range(0, len(text), TEXT_CHARS)]
    return out


@runs("notion", "create_page")
async def create_page(ctx: RunContext, arguments: dict) -> Outcome:
    made = await call(ctx, "NOTION_CREATE_NOTION_PAGE", {"parent_id": arguments["parent_id"],
                                                         "title": arguments["title"]})
    page = connection_service.response_field(made["data"], "id")
    if not page:
        raise ActionFailed("Notion didn't make the page: check that your Notion connection can open the parent page.")
    content = blocks(arguments["content"])
    for i in range(0, len(content), BLOCKS_PER_CALL):
        await call(ctx, "NOTION_ADD_MULTIPLE_PAGE_CONTENT", {"parent_block_id": page,
                                                             "content_blocks": content[i:i + BLOCKS_PER_CALL]})
    url = connection_service.response_field(made["data"], "url")
    return Outcome(f"Wrote “{arguments['title']}” in Notion.", url, made["log_id"])
