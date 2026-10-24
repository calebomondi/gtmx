"""The Lace's Notion tools: searching and reading the founder's pages, and a
new page as a proposal the founder approves."""

import json

import pytest

from agents.lace.apps import AppError
from agents.lace.notion_tools import page_id
from agents.lace.tools import build_tools

PAGE = "1a2b3c4d5e6f7a8b9c0d1e2f3a4b5c6d"
PAGE_ID = "1a2b3c4d-5e6f-7a8b-9c0d-1e2f3a4b5c6d"


class Apps:
    def __init__(self, found=None, text=None, error=None):
        self.found, self.text, self.error, self.read = found, text, error, []

    async def notion_search(self, query):
        if self.error:
            raise AppError(self.error)
        return self.found

    async def notion_page(self, page):
        self.read.append(page)
        return self.text


def _tools(store, settings, apps):
    return {t.name: t for t in build_tools(store, settings, apps=apps)}


async def _run(tool, **args) -> dict:
    return json.loads(await tool.ainvoke(args))


@pytest.mark.parametrize("given, found", [
    (f"https://www.notion.so/acme/Pricing-{PAGE}", PAGE_ID),
    (f"https://www.notion.so/{PAGE}?v=ffffffffffffffffffffffffffffffff&p=1", PAGE_ID),  # not the view's id
    (PAGE_ID, PAGE_ID),
    ("https://example.com/pricing", None),
])
def test_page_ids_from_links(given, found):
    assert page_id(given) == found


async def test_search_and_read(store, settings):
    apps = Apps(found=[{"id": PAGE_ID, "title": "Pricing", "url": "https://notion.so/x", "kind": "page"}],
                text="# Pricing\n- Basic: KES 2,000")
    tools = _tools(store, settings, apps)
    found = await _run(tools["search_notion"], query="pricing")
    assert found["ok"] and found["data"][0]["title"] == "Pricing"
    read = await _run(tools["read_notion_page"], page=f"https://www.notion.so/Pricing-{PAGE}")
    assert read["data"]["text"].startswith("# Pricing") and apps.read == [PAGE_ID]


@pytest.mark.parametrize("apps, said", [(Apps(None), "isn't connected"), (Apps(error="Notion refused it"), "refused")])
async def test_search_failures_say_why(store, settings, apps, said):
    out = await _run(_tools(store, settings, apps)["search_notion"], query="x")
    assert not out["ok"] and said in out["error"]


async def test_a_new_page_is_a_proposal(store, settings):
    out = await _run(_tools(store, settings, Apps())["write_notion_page"], parent=f"https://notion.so/Briefs-{PAGE}",
                     title="Week 43 brief", content="# Wins\n- Two replies from Nakuru")
    [card] = out["data"]["ui"]
    assert (card["title"], card["preview"]) == ("Write “Week 43 brief” in Notion", "# Wins\n- Two replies from Nakuru")
    [proposal] = store.proposed
    assert (proposal.app, proposal.action, proposal.arguments["parent_id"]) == ("notion", "create_page", PAGE_ID)


async def test_a_page_needs_its_parent(store, settings):
    out = await _run(_tools(store, settings, Apps())["write_notion_page"], parent="the briefs page",
                     title="x", content="y")
    assert not out["ok"] and "ask the founder" in out["error"] and store.proposed == []
