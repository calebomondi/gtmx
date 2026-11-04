"""The Lace's tools for the team's standing instructions: how it should work
from now on ("only competitors selling in Kenya", "no events outside
Africa", "keep emails under 100 words"). They are kept, shown in its prompt
in every chat, and read by the background jobs they apply to."""

from langchain_core.tools import BaseTool, tool

from agents.lace.store import InstructionsFull, LaceStore
from agents.lace.tool_guard import guarded
from agents.schemas.lace import INSTRUCTION_CHARS, InstructionScope, ToolResult


def build_instruction_tools(store: LaceStore) -> list[BaseTool]:

    @tool(parse_docstring=True)
    @guarded
    async def remember_instruction(instruction: str, applies_to: InstructionScope) -> ToolResult:
        """Keep a standing instruction the founder gives about how you should work from now on, so it holds in every chat and every search, not just this one: "only look at competitors selling in Kenya", "skip events outside Africa", "always write emails in a casual tone". Save it as soon as they say it, without asking. Not for facts about the startup (record_fact) or for a one-off request.

        Args:
            instruction: The instruction in a short sentence, in their words where you can.
            applies_to: What it governs: competitors, leads, opportunities, outreach (drafts and replies), or everything.
        """
        text = " ".join(instruction.split())
        if not text:
            return ToolResult.failure("Give the instruction in a sentence.")
        if len(text) > INSTRUCTION_CHARS:
            return ToolResult.failure(f"Keep it under {INSTRUCTION_CHARS} characters.")
        if any(kept.text.lower() == text.lower() for kept in await store.instructions()):
            return ToolResult.success("That instruction is already kept.")
        try:
            kept = await store.add_instruction(text, applies_to)
        except InstructionsFull as exc:
            return ToolResult.failure(str(exc))
        return ToolResult.success(f"Kept as a standing instruction for {applies_to}. The founder can see and edit it "
                                  "in this Lace's settings, under Instructions.", kept.model_dump())

    @tool(parse_docstring=True)
    @guarded
    async def forget_instruction(instruction_id: str) -> ToolResult:
        """Drop a standing instruction the founder no longer wants, or one a new instruction replaces (keep the new one with remember_instruction).

        Args:
            instruction_id: Its id, from the standing instructions in your prompt.
        """
        dropped = await store.remove_instruction(instruction_id.strip())
        if dropped is None:
            return ToolResult.failure(f"No standing instruction has the id {instruction_id}.")
        return ToolResult.success(f"Dropped the instruction: {dropped.text}")

    return [remember_instruction, forget_instruction]
