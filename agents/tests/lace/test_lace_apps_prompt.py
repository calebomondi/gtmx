"""The Lace is told which of the founder's apps it can use, once a turn, so it
never says one is connected, or works, when it isn't."""

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage

from agents.lace.apps import AppError, AppStatus
from agents.lace.graph import build_lace_graph
from agents.lace.prompts import render_apps
from lace_fakes import MemoryStore, ScriptedModel

GMAIL = AppStatus(platform="gmail", label="Gmail", connected=True, enabled=True, account="shared",
                  account_name="caleb@thalace.com")
SLACK = AppStatus(platform="slack", label="Slack", connected=True, enabled=False, account="own")
X = AppStatus(platform="x", label="X", connected=True, needs_attention=True, enabled=True, account="own")
HUBSPOT = AppStatus(platform="hubspot", label="HubSpot", connected=False, enabled=True)
NOTION = AppStatus(platform="notion", label="Notion", connected=True, enabled=True, account="own")


def test_each_app_says_whether_the_lace_can_use_it():
    text = render_apps([GMAIL, SLACK, X, HUBSPOT, NOTION])
    lines = text.splitlines()
    assert lines[1] == ("- Gmail: on, the founder's shared account (caleb@thalace.com). The emails the founder "
                        "approves go out from it, replies come back to you, and you can search and read their mail "
                        "(search_email, read_email_thread).")
    assert "Slack: connected but switched off for you" in lines[2]
    assert "X: connected but needs the founder to sign in again" in lines[3]
    assert lines[4].startswith("- Notion: on, this Lace's own account. Their pages (search_notion")
    assert lines[5].startswith("- Not connected: HubSpot.")


class Apps:
    def __init__(self, listed=None, fails=False):
        self.listed, self.fails, self.calls = listed or [], fails, 0

    async def overview(self):
        self.calls += 1
        if self.fails:
            raise AppError("apps unavailable (TimeoutError)")
        return self.listed


def _notes(model) -> list[str]:
    return [m.content for m in model.calls[-1][0] if isinstance(m, SystemMessage)]


async def test_the_list_is_read_once_a_turn(settings):
    apps = Apps([GMAIL])
    model = ScriptedModel(AIMessage(content="", tool_calls=[{"name": "get_facts", "args": {}, "id": "1"}]),
                          AIMessage(content="Gmail is connected."))
    out = await build_lace_graph(MemoryStore(), settings=settings, apps=apps, model_step=model).ainvoke(
        {"messages": [HumanMessage(content="is my email connected?")]}, {"configurable": {"thread_id": "t"}})
    assert any(isinstance(m, ToolMessage) for m in out["messages"])
    assert apps.calls == 1 and any(n.startswith("Your apps") and "Gmail: on" in n for n in _notes(model))


async def test_without_the_list_the_turn_goes_on(settings):
    model = ScriptedModel(AIMessage(content="Hi."))
    await build_lace_graph(MemoryStore(), settings=settings, apps=Apps(fails=True), model_step=model).ainvoke(
        {"messages": [HumanMessage(content="hi")]}, {"configurable": {"thread_id": "t"}})
    assert not any(n.startswith("Your apps") for n in _notes(model))
