"""Lace run segments: onboarding and one founder turn.

Both run under the run manager (timeout, failure recording, restart recovery).
The Lace's conversation lives on one LangGraph thread per Lace, in the shared
Postgres checkpointer; the graph is compiled per run around that Lace's store.

Frames: "step" (what the Lace is doing, for the progress line), "tool_result"
(each tool's summary), "message" (the Lace's reply), then "complete". While
the model writes, live-only "token" frames carry the reply as it forms, and
"token_reset" says to discard the text so far.
"""

import asyncio
import json
import uuid
from datetime import UTC, datetime

from langchain_core.messages import AIMessage, AnyMessage, HumanMessage, ToolMessage

from agents.lace.graph import BRIEF_FACTS, build_lace_graph
from agents.lace.onboarding import onboard, opening_message
from agents.lace.store import LaceJobs
from agents.lace.prompts import system_prompt
from backend.app.agents_runtime import get_checkpointer
from backend.app.database import models
from backend.app.database.connect import AsyncSessionLocal
from backend.app.database.lace_models import Lace
from backend.app.runs import events
from backend.app.services.lace_store import DbLaceStore
from backend.app.services.runs import set_run_fields
from config import settings

# Characters per streamed "token" frame.
TOKEN_FRAME_CHARS = 24

# What the progress line says while a tool runs.
_STEP_TEXT = {
    "search_web": lambda a: f"Searching the web for “{a.get('query', '')}”",
    "map_site": lambda a: f"Looking through {a.get('url', 'a site')}",
    "read_page": lambda a: f"Reading {a.get('url', 'a page')}",
    "read_pages": lambda a: f"Reading {len(a.get('urls') or [])} pages",
    "get_facts": lambda a: "Checking what I know",
    "record_fact": lambda a: "Noting that down",
    "define_icp": lambda a: "Working out who your ideal customers are",
    "list_competitors": lambda a: "Checking the competitors I track",
    "find_competitors": lambda a: "Starting a competitor search",
    "check_competitors": lambda a: "Checking competitors for changes",
    "list_accounts": lambda a: "Checking the target accounts",
    "find_contacts": lambda a: "Starting a search for contacts",
    "draft_outreach": lambda a: "Starting to draft messages",
    "find_opportunities": lambda a: "Starting a search for opportunities",
    "list_opportunities": lambda a: "Checking the opportunities on file",
    "find_accounts": lambda a: "Starting a search for customers" + (f" in {a['country']}" if a.get("country") else ""),
}

# Marks a message on the thread as an update for the Lace, not the founder's words.
EVENT_FLAG = "lace_event"


def thread_config(lace_id: uuid.UUID) -> dict:
    return {"configurable": {"thread_id": f"lace:{lace_id}"}}


def _graph(lace_id: uuid.UUID, jobs: LaceJobs | None = None):
    store = DbLaceStore(AsyncSessionLocal, lace_id)
    return build_lace_graph(store, checkpointer=get_checkpointer(), jobs=jobs), store


def step_text(tool_call: dict) -> str:
    describe = _STEP_TEXT.get(tool_call["name"])
    return describe(tool_call.get("args") or {}) if describe else f"Using {tool_call['name']}"


def _tool_summary(message: ToolMessage) -> dict:
    try:
        result = json.loads(message.content)
    except (TypeError, ValueError):
        return {"tool": message.name, "ok": False, "summary": "Unreadable tool result"}
    return {"tool": message.name, "ok": bool(result.get("ok")), "summary": str(result.get("summary") or "")}


async def _finish(run_id: uuid.UUID, reply: str) -> None:
    await events.publish(run_id, "message", {"role": "lace", "content": reply})
    await set_run_fields(models.Run, run_id, status="completed", finished_at=datetime.now(UTC))
    await events.publish(run_id, "complete", {})


async def onboarding_segment(run_id: uuid.UUID, lace_id: uuid.UUID) -> None:
    graph, store = _graph(lace_id)
    await events.publish(run_id, "step", {"text": "Reading your website"})
    result = await onboard(store, settings)
    await events.publish(run_id, "onboarded", result.model_dump(mode="json"))

    await events.publish(run_id, "step", {"text": "Writing to you"})
    profile, facts = await asyncio.gather(store.profile(), store.facts(None, BRIEF_FACTS))
    reply = await asyncio.to_thread(opening_message, system_prompt(profile, facts), result)
    # The opening is the Lace's own first message on its thread, so the next
    # turn's history starts with it.
    await graph.aupdate_state(thread_config(lace_id), {"messages": [AIMessage(content=reply)]}, as_node="agent")
    async with AsyncSessionLocal() as db, db.begin():
        lace = await db.get(Lace, lace_id)
        if lace is not None and lace.status == "onboarding":
            lace.status = "active"
    await _finish(run_id, reply)


class _TokenRelay:
    """Batches streamed tokens into "token" frames a few words at a time:
    one frame per model token would be hundreds per reply."""

    def __init__(self, run_id: uuid.UUID):
        self._run_id, self._buffer = run_id, ""

    def add(self, text: str) -> None:
        self._buffer += text
        if len(self._buffer) >= TOKEN_FRAME_CHARS:
            self.flush()

    def flush(self) -> None:
        if self._buffer:
            events.broadcast(self._run_id, "token", {"text": self._buffer})
            self._buffer = ""

    def reset(self) -> None:
        self._buffer = ""
        events.broadcast(self._run_id, "token_reset")


def founder_message(text: str) -> HumanMessage:
    return HumanMessage(content=text)


def event_message(updates: list[str]) -> HumanMessage:
    """Updates delivered to the Lace as one message, flagged so the founder's
    view of the conversation leaves it out."""
    body = "\n".join(f"- {u}" for u in updates)
    return HumanMessage(
        content=("Updates for you to pass on (these are not from the founder):\n" + body
                 + "\n\nTell the founder what this means for them, briefly."),
        additional_kwargs={EVENT_FLAG: True},
    )


async def turn_segment(run_id: uuid.UUID, lace_id: uuid.UUID, message: HumanMessage,
                       jobs: LaceJobs | None = None) -> None:
    graph, _ = _graph(lace_id, jobs)
    relay = _TokenRelay(run_id)
    reply = ""
    async for mode, chunk in graph.astream({"messages": [message]}, thread_config(lace_id),
                                           stream_mode=["updates", "custom"]):
        if mode == "custom":
            if "token" in chunk:
                relay.add(chunk["token"])
            elif chunk.get("reset"):
                relay.reset()
            continue
        relay.flush()
        for node, output in chunk.items():
            for message in (output or {}).get("messages", []):
                if node == "agent" and message.tool_calls:
                    # Text before a tool call ("let me look that up") is not the reply.
                    relay.reset()
                    for tool_call in message.tool_calls:
                        await events.publish(run_id, "step", {"text": step_text(tool_call)})
                elif node == "agent":
                    reply = str(message.content)
                elif isinstance(message, ToolMessage):
                    await events.publish(run_id, "tool_result", _tool_summary(message))
    await _finish(run_id, reply)


def visible_messages(messages: list[AnyMessage]) -> list[dict]:
    """The conversation as the founder sees it: their messages and the Lace's
    replies, without tool calls, results or updates."""
    out = []
    for m in messages:
        if isinstance(m, HumanMessage) and not m.additional_kwargs.get(EVENT_FLAG):
            out.append({"role": "founder", "content": str(m.content)})
        elif isinstance(m, AIMessage) and not m.tool_calls and str(m.content).strip():
            out.append({"role": "lace", "content": str(m.content)})
    return out


async def history(lace_id: uuid.UUID, limit: int) -> list[dict]:
    graph, _ = _graph(lace_id)
    state = await graph.aget_state(thread_config(lace_id))
    messages = (state.values or {}).get("messages", []) if state else []
    return visible_messages(messages)[-limit:]
