"""The Lace: one ReAct loop per startup.

    agent --(tool calls)--> tools --> agent ... --(answer)--> END

State is only the conversation. What the Lace knows lives in its store and
reaches the model two ways: the brief in the system prompt on every step, and
the tools.

The model's text is streamed as it is written: run the graph with
stream_mode "custom" to receive {"token": text} and {"reset": True} items.

Bounds per founder turn: at most `lace_max_tool_calls_per_turn` tool calls,
after which the model must answer with what it has. Each step re-sends at most
`lace_history_token_budget` tokens of conversation. The run's wall clock is
capped by the run manager that drives the graph.
"""

import asyncio
from collections.abc import Callable, Sequence
from typing import Annotated, Literal, TypedDict

from langchain_core.messages import AnyMessage, HumanMessage, SystemMessage, ToolMessage
from langchain_core.tools import BaseTool
from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.config import get_stream_writer
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode

from agents.context_budget import count_tokens
from agents.lace.prompts import system_prompt
from agents.lace.store import LaceJobs, LaceStore
from agents.lace.tools import build_tools
from agents.llm.main import TokenSink, invoke_with_tools
from config import Settings, get_settings

# The model step, injectable so tests can script it:
# (messages, tools, sink) -> AIMessage, streaming its text into `sink`.
ModelStep = Callable[[Sequence[AnyMessage], Sequence[BaseTool], TokenSink], AnyMessage]

BRIEF_FACTS = 80

_OUT_OF_TOOL_CALLS = (
    "You have used this turn's tool calls. Answer the founder now with what you "
    "have, and say what you would look into next."
)


_INTERRUPTED = '{"ok": false, "summary": "Interrupted before it finished.", "error": "interrupted"}'


class LaceState(TypedDict):
    messages: Annotated[list[AnyMessage], add_messages]


def _default_step(messages: Sequence[AnyMessage], tools: Sequence[BaseTool], sink: TokenSink) -> AnyMessage:
    return invoke_with_tools(messages, tools, log_label="lace:step", sink=sink)


class _StreamSink:
    """Hands tokens from the model's worker thread to the graph's custom
    stream, on the event loop that owns it. Under `ainvoke` (no custom
    stream) the writer drops them."""

    def __init__(self, loop: asyncio.AbstractEventLoop, write: Callable[[dict], None]):
        self._loop, self._write = loop, write

    def token(self, text: str) -> None:
        self._loop.call_soon_threadsafe(self._write, {"token": text})

    def reset(self) -> None:
        self._loop.call_soon_threadsafe(self._write, {"reset": True})


def _turn_start(messages: Sequence[AnyMessage]) -> int:
    """Index of the founder's latest message: where this turn began."""
    for i in range(len(messages) - 1, -1, -1):
        if isinstance(messages[i], HumanMessage):
            return i
    return 0


def tool_calls_this_turn(messages: Sequence[AnyMessage]) -> int:
    return sum(isinstance(m, ToolMessage) for m in messages[_turn_start(messages):])


def close_dangling_tool_calls(messages: Sequence[AnyMessage]) -> list[AnyMessage]:
    """Answer any tool call that never got a result, so the model is never sent
    a call without its answer (providers reject that). It happens when a turn
    is cancelled or the server restarts between the call and its result."""
    answered = {m.tool_call_id for m in messages if isinstance(m, ToolMessage)}
    out: list[AnyMessage] = []
    for message in messages:
        out.append(message)
        for tool_call in getattr(message, "tool_calls", None) or []:
            if tool_call["id"] not in answered:
                out.append(ToolMessage(content=_INTERRUPTED, tool_call_id=tool_call["id"]))
    return out


def history_window(messages: Sequence[AnyMessage], budget: int) -> list[AnyMessage]:
    """The most recent messages that fit `budget` tokens, starting on a
    founder message so a tool result is never sent without the call that made
    it. The current turn is always kept whole, even over budget."""
    turn = _turn_start(messages)
    used = sum(count_tokens(str(m.content)) for m in messages[turn:])
    start = turn
    for i in range(turn - 1, -1, -1):
        used += count_tokens(str(messages[i].content))
        if used > budget:
            break
        if isinstance(messages[i], HumanMessage):
            start = i
    return list(messages[start:])


def build_lace_graph(
    store: LaceStore,
    *,
    checkpointer: BaseCheckpointSaver | None = None,
    settings: Settings | None = None,
    model_step: ModelStep = _default_step,
    jobs: LaceJobs | None = None,
):
    """Compile the Lace for one startup. `store` scopes every tool to it;
    `jobs` runs the tools that take longer than a turn."""
    settings = settings or get_settings()
    tools = build_tools(store, settings, jobs)

    async def agent(state: LaceState) -> dict:
        profile, facts = await asyncio.gather(store.profile(), store.facts(None, BRIEF_FACTS))
        messages = state["messages"]
        prompt: list[AnyMessage] = [SystemMessage(content=system_prompt(profile, facts))]
        prompt += close_dangling_tool_calls(history_window(messages, settings.lace_history_token_budget))
        allowed = tools
        if tool_calls_this_turn(messages) >= settings.lace_max_tool_calls_per_turn:
            prompt.append(SystemMessage(content=_OUT_OF_TOOL_CALLS))
            allowed = []
        sink = _StreamSink(asyncio.get_running_loop(), get_stream_writer())
        # The ladder is synchronous and sleeps on throttles: off the event loop.
        reply = await asyncio.to_thread(model_step, prompt, allowed, sink)
        return {"messages": [reply]}

    def route(state: LaceState) -> Literal["tools", "__end__"]:
        last = state["messages"][-1]
        return "tools" if getattr(last, "tool_calls", None) else END

    builder = StateGraph(LaceState)
    builder.add_node("agent", agent)
    builder.add_node("tools", ToolNode(tools))
    builder.add_edge(START, "agent")
    builder.add_conditional_edges("agent", route, {"tools": "tools", END: END})
    builder.add_edge("tools", "agent")
    return builder.compile(checkpointer=checkpointer)
