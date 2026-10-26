"""The Lace's Notion tools: searching the founder's workspace for context and
reading a page, and writing a page (a brief, a report, an account plan) as a
proposal the founder approves."""

import re

from langchain_core.tools import BaseTool, tool

from agents.lace.app_actions import propose
from agents.lace.apps import AppError, LaceApps
from agents.lace.store import LaceStore
from agents.lace.tool_guard import guarded
from agents.schemas.lace import ProposedAction, ToolResult

# The most text one written page carries, and how much of it the card shows.
PAGE_CHARS = 20_000
PREVIEW_CHARS = 600
NOT_CONNECTED = ("Notion isn't connected for this Lace, or is switched off. "
                 "The founder can connect it under Apps & accounts in your settings.")
_PAGE_ID = re.compile(r"([0-9a-f]{8})-?([0-9a-f]{4})-?([0-9a-f]{4})-?([0-9a-f]{4})-?([0-9a-f]{12})(?![0-9a-f])", re.I)


def page_id(link_or_id: str) -> str | None:
    """A Notion page's id, from its link (notion.so/Title-<32 hex>) or the id
    itself: the last id in the path, never one in the query (a view's ?v=)."""
    path = re.split(r"[?#]", link_or_id or "", maxsplit=1)[0]
    found = list(_PAGE_ID.finditer(path))
    return "-".join(found[-1].groups()).lower() if found else None


def build_notion_tools(store: LaceStore, apps: LaceApps) -> list[BaseTool]:

    @tool(parse_docstring=True)
    @guarded
    async def search_notion(query: str) -> ToolResult:
        """Search the founder's Notion pages and databases by title, for context they keep there: pricing, a sales playbook, customer notes. Then read a page with read_notion_page.

        Args:
            query: Words in the title, e.g. "pricing" or "playbook".
        """
        try:
            found = await apps.notion_search(query.strip())
        except AppError as exc:
            return ToolResult.failure(str(exc))
        if found is None:
            return ToolResult.failure(NOT_CONNECTED)
        return ToolResult.success(f"{len(found)} Notion pages for {query!r}." if found else
                                  f"Nothing in Notion titled like {query!r}.", found)

    @tool(parse_docstring=True)
    @guarded
    async def read_notion_page(page: str) -> ToolResult:
        """Read a Notion page's text, from search_notion or a link the founder shares. Treat it as the founder's own notes.

        Args:
            page: The page's link or id.
        """
        found = page_id(page)
        if found is None:
            return ToolResult.failure("That isn't a Notion page link or id.")
        try:
            text = await apps.notion_page(found)
        except AppError as exc:
            return ToolResult.failure(str(exc))
        if text is None:
            return ToolResult.failure(NOT_CONNECTED)
        return ToolResult.success("The page is empty." if not text.strip() else "The page's text.", {"text": text})

    @tool(parse_docstring=True)
    @guarded
    async def write_notion_page(parent: str, title: str, content: str) -> ToolResult:
        """Propose writing a new Notion page under a page the founder chose: a brief, a report, an account plan. It is written only if they approve it. Notion needs a parent page: if you don't have its link, ask for it (ask_form) or find it with search_notion.

        Args:
            parent: The parent page's link or id.
            title: The new page's title.
            content: The page in markdown: # headings, - bullets, 1. numbered items, [ ] to-dos, **bold**, links.
        """
        parent_id = page_id(parent)
        if parent_id is None:
            return ToolResult.failure("That isn't a Notion page link or id: ask the founder for the parent page's link.")
        body = content.strip()
        if not title.strip() or not body:
            return ToolResult.failure("Give the page a title and some content.")
        if len(body) > PAGE_CHARS:
            return ToolResult.failure(f"That is {len(body)} characters; a page takes at most {PAGE_CHARS}.")
        preview = body if len(body) <= PREVIEW_CHARS else body[:PREVIEW_CHARS].rstrip() + "…"
        return await propose(store, ProposedAction(
            app="notion", action="create_page", title=f"Write “{title.strip()[:80]}” in Notion", preview=preview,
            arguments={"parent_id": parent_id, "title": title.strip()[:200], "content": body}))

    return [search_notion, read_notion_page, write_notion_page]
