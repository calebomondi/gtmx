"""The Lace's tool for its GTM playbooks (agents/prompts/playbook_library.py): read the
whole method before starting a task the prompt's playbook list covers."""

from langchain_core.tools import BaseTool, tool

from agents.prompts.playbook_library import playbook, playbooks
from agents.lace.tool_guard import guarded
from agents.schemas.lace import ToolResult


def build_playbook_tools() -> list[BaseTool]:

    @tool(parse_docstring=True)
    @guarded
    async def read_playbook(name: str) -> ToolResult:
        """Read one of your GTM playbooks in full: how a good go-to-market operator does that kind of task. Read the one that fits before you start the task (writing a cold email, a follow-up, answering a reply, judging how warm a lead is, choosing who to email). The founder's standing instructions outrank a playbook.

        Args:
            name: The playbook's name, from the list in your instructions, e.g. cold-email.
        """
        found = playbook(name)
        if found is None:
            return ToolResult.failure(f"There's no playbook called {name!r}. The playbooks are: "
                                      + ", ".join(playbooks()) + ".")
        return ToolResult.success(f"The {found.name} playbook. Follow it for this task.",
                                  {"name": found.name, "method": found.body})

    return [read_playbook]
