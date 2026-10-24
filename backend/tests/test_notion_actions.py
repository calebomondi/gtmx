"""Notion through a stubbed Composio, as its documented response shapes:
searching and reading pages for the Lace, and the page a founder approves."""

from backend.app.database.connect import AsyncSessionLocal
from backend.app.services import lace_apps, notion_actions
from backend.tests.helpers import stub_accounts
from backend.tests.test_lace_apps import _lace
from backend.tests.test_social_actions import _ctx, composio  # noqa: F401 -- fixture


def _text(kind, text, **more):
    return {"type": kind, kind: {"rich_text": [{"plain_text": text}], **more}}


async def test_the_lace_searches_and_reads_notion(composio, monkeypatch):  # noqa: F811
    stub_accounts(monkeypatch, {"notion"})
    composio["answers"] = {
        "NOTION_SEARCH_NOTION_PAGE": {"response_data": {"results": [
            {"object": "page", "id": "p1", "url": "https://notion.so/p1",
             "properties": {"Name": {"type": "title", "title": [{"plain_text": "Pricing"}]}}},
            {"object": "database", "id": "d1", "url": "https://notion.so/d1", "title": [{"plain_text": "Leads"}]},
        ]}},
        "NOTION_FETCH_BLOCK_CONTENTS": {"block_child_data": {"results": [
            _text("heading_1", "Pricing"), _text("bulleted_list_item", "Basic: KES 2,000"),
            _text("to_do", "Annual plan", checked=True), {"type": "image", "image": {}},
        ], "has_more": False}},
    }
    apps = lace_apps.DbLaceApps(AsyncSessionLocal, _lace())
    assert await apps.notion_search("pricing") == [
        {"id": "p1", "title": "Pricing", "url": "https://notion.so/p1", "kind": "page"},
        {"id": "d1", "title": "Leads", "url": "https://notion.so/d1", "kind": "database"}]
    assert await apps.notion_page("p1") == "# Pricing\n- Basic: KES 2,000\n[x] Annual plan"


def test_markdown_becomes_notion_blocks():
    assert notion_actions.blocks("# Wins\n\n- Two replies\n1. Call Joe\n- [ ] Send deck\nPlain **bold**") == [
        {"content_block": {"content": "Wins", "block_property": "heading_1"}},
        {"content_block": {"content": "Two replies", "block_property": "bulleted_list_item"}},
        {"content_block": {"content": "Call Joe", "block_property": "numbered_list_item"}},
        {"content_block": {"content": "Send deck", "block_property": "to_do"}},
        {"content_block": {"content": "Plain **bold**", "block_property": "paragraph"}},
    ]
    assert len(notion_actions.blocks("x" * 4500)) == 3  # Notion's 2000 characters per text


async def test_an_approved_page_is_written_under_its_parent(composio):  # noqa: F811
    composio["answers"] = {"NOTION_CREATE_NOTION_PAGE": {"id": "new1", "url": "https://notion.so/new1"}}
    outcome = await notion_actions.create_page(_ctx("notion"), {"parent_id": "par", "title": "Brief",
                                                                "content": "\n".join(f"- {i}" for i in range(150))})
    tools = [tool for tool, _ in composio["calls"]]
    assert tools == ["NOTION_CREATE_NOTION_PAGE", "NOTION_ADD_MULTIPLE_PAGE_CONTENT", "NOTION_ADD_MULTIPLE_PAGE_CONTENT"]
    assert [len(args["content_blocks"]) for _, args in composio["calls"][1:]] == [100, 50]
    assert (outcome.result, outcome.url) == ("Wrote “Brief” in Notion.", "https://notion.so/new1")
