"""Lace run segments: onboarding, one founder turn, and the brief.

Both run under the run manager (timeout, failure recording, restart recovery).
The Lace's conversation lives on one LangGraph thread per Lace, in the shared
Postgres checkpointer; the graph is compiled per run around that Lace's store.

Frames: "step" (what the Lace is doing, for the progress line), "progress"
(onboarding only: {fraction, text} for the creation page), "tool_result"
(each tool's summary), "message" (the Lace's reply), then "complete". While
the model writes, live-only "token" frames carry the reply as it forms, and
"token_reset" says to discard the text so far.
"""

import asyncio
import json
import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import UTC, datetime

from langchain_core.messages import AIMessage, AnyMessage, HumanMessage, ToolMessage
from pydantic import TypeAdapter

from agents.lace.answers import AnswerError, describe
from agents.lace.graph import BRIEF_FACTS, build_lace_graph
from agents.lace.onboarding import Progress, onboard, opening_message
from agents.lace.store import LaceJobs
from agents.lace.prompts import system_prompt
from agents.schemas.lace_ui import BlockAnswer, UiBlock
from backend.app.agents_runtime import get_checkpointer
from backend.app.database import models
from backend.app.database.connect import AsyncSessionLocal
from backend.app.database.lace_models import Lace
from backend.app.runs import events
from backend.app.services import lace_activity, lace_brief_email, lace_briefs
from backend.app.services.errors import ConflictError, InvalidInputError
from backend.app.services.lace_apps import DbLaceApps
from backend.app.services.lace_store import DbLaceStore
from backend.app.services.runs import set_run_fields
from config import settings

# Where the founder's progress bar stands while the Lace writes its first
# message, after onboarding's own stages (agents/lace/onboarding.py).
WRITING_PROGRESS = 0.95
# Characters per streamed "token" frame.
TOKEN_FRAME_CHARS = 24
# What the Lace says while it works ("let me check the pricing page") is
# kept as one line of its step trail, at most this long.
NARRATION_CHARS = 200
# The step shown when a model call failed and the answer starts over.
RETRY_STEP = "That didn't go through. Trying again"

# What the progress line says while a tool runs.
_STEP_TEXT = {
    "search_web": lambda a: f"Searching the web for “{a.get('query', '')}”",
    "map_site": lambda a: f"Looking through {a.get('url', 'a site')}",
    "read_page": lambda a: f"Reading {a.get('url', 'a page')}",
    "read_pages": lambda a: f"Reading {len(a.get('urls') or [])} pages",
    "read_social": lambda a: f"Reading {a.get('url', 'a social profile')}",
    "suggest_replies": lambda a: "Suggesting replies",
    "get_facts": lambda a: "Checking what I know",
    "record_fact": lambda a: "Noting that down",
    "define_icp": lambda a: "Starting to work out your ideal customers",
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
# On a founder's message: what they attached ([{id, filename}]), and their own
# words, which the founder sees without the note the model gets.
ATTACHMENTS_KEY = "documents"
FOUNDER_TEXT_KEY = "founder_text"
# On a founder message that answers a question: the answer, so the question
# shows as answered.
ANSWER_KEY = "answer"
# On a founder message about one draft: its id. The Lace's replies to it carry
# the id too, so the draft's own panel can show that exchange.
DRAFT_KEY = "draft_id"


def thread_config(lace_id: uuid.UUID) -> dict:
    return {"configurable": {"thread_id": f"lace:{lace_id}"}}


async def forget_thread(lace_id: uuid.UUID) -> None:
    """Drop the Lace's conversation from the checkpointer."""
    await get_checkpointer().adelete_thread(thread_config(lace_id)["configurable"]["thread_id"])


def _graph(lace_id: uuid.UUID, jobs: LaceJobs | None = None):
    store = DbLaceStore(AsyncSessionLocal, lace_id)
    apps = DbLaceApps(AsyncSessionLocal, lace_id)
    return build_lace_graph(store, checkpointer=get_checkpointer(), jobs=jobs, apps=apps), store


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


@asynccontextmanager
async def _progress_frames(run_id: uuid.UUID) -> AsyncIterator[Progress]:
    """A thread-safe progress callback whose reports become "progress"
    frames, published in order; all are out when the block ends."""
    loop = asyncio.get_running_loop()
    queue: asyncio.Queue[tuple[float, str] | None] = asyncio.Queue()

    async def publish_all() -> None:
        while (item := await queue.get()) is not None:
            await events.publish(run_id, "progress", {"fraction": round(item[0], 3), "text": item[1]})

    publisher = asyncio.create_task(publish_all())
    try:
        yield lambda fraction, text: loop.call_soon_threadsafe(queue.put_nowait, (fraction, text))
    finally:
        loop.call_soon_threadsafe(queue.put_nowait, None)
        await publisher


async def onboarding_segment(run_id: uuid.UUID, lace_id: uuid.UUID) -> None:
    graph, store = _graph(lace_id)
    await events.publish(run_id, "step", {"text": "Reading your website"})
    async with _progress_frames(run_id) as progress:
        result = await onboard(store, settings, progress=progress)
    await events.publish(run_id, "onboarded", result.model_dump(mode="json"))

    await events.publish(run_id, "step", {"text": "Writing to you"})
    await events.publish(run_id, "progress", {"fraction": WRITING_PROGRESS, "text": "Writing to you"})
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


def narration(content) -> str:
    """What the model wrote beside its tool calls, as one trail line."""
    text = " ".join(str(content or "").split())
    return text if len(text) <= NARRATION_CHARS else text[:NARRATION_CHARS - 1].rstrip() + "…"


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


def founder_message(text: str, attachments: list[dict] | None = None, draft: dict | None = None) -> HumanMessage:
    """The founder's words; with attachments, a note naming them so the Lace
    knows to read them; about a draft, its text as it stands and how to
    change it."""
    notes: list[str] = []
    meta: dict = {}
    if attachments:
        names = ", ".join(f"{a['filename']} (document id {a['id']})" for a in attachments)
        notes.append(f"[The founder attached: {names}. Read them with read_document.]")
        meta[ATTACHMENTS_KEY] = attachments
    if draft:
        subject = f"Subject: {draft['subject']}\n" if draft.get("subject") else ""
        notes.append(f"[This is about the draft {draft['id']} to {draft['recipient']} at {draft['company']} by "
                     f"{draft['channel']}, which reads now:\n{subject}{draft['body']}\n"
                     "Work on it with the founder: answer briefly, and when they want it changed, rewrite it with "
                     f"edit_draft (draft_id {draft['id']}) and say in a line what you changed.]")
        meta[DRAFT_KEY] = draft["id"]
    if not notes:
        return HumanMessage(content=text)
    note = "\n\n".join(notes)
    return HumanMessage(content=f"{text}\n\n{note}" if text else note, additional_kwargs={**meta, FOUNDER_TEXT_KEY: text})


def event_message(updates: list[str]) -> HumanMessage:
    """Updates delivered to the Lace as one message, flagged so the founder's
    view of the conversation leaves it out."""
    body = "\n".join(f"- {u}" for u in updates)
    return HumanMessage(
        content=("Updates for you to pass on (these are not from the founder):\n" + body
                 + "\n\nTell the founder what this means for them, briefly."),
        additional_kwargs={EVENT_FLAG: True},
    )


def _first_line(text: str) -> str:
    """A brief's opening line, without markdown emphasis, for its Feed item."""
    line = next((l.strip() for l in text.splitlines() if l.strip()), "")
    return line.strip("#*_ ")


def _brief_message(request: str) -> HumanMessage:
    """The brief request, flagged like an update: the founder sees the
    Lace's brief, not what it was asked."""
    return HumanMessage(content=request, additional_kwargs={EVENT_FLAG: True})


async def turn_segment(run_id: uuid.UUID, lace_id: uuid.UUID, message: HumanMessage,
                       jobs: LaceJobs | None = None) -> None:
    await _finish(run_id, await _converse(run_id, lace_id, message, jobs))


async def brief_segment(run_id: uuid.UUID, lace_id: uuid.UUID, brief_id: uuid.UUID, request: str,
                        jobs: LaceJobs | None = None) -> None:
    """The turn in which the Lace writes its brief. The brief is saved, and
    emailed if the founder asked, before the run completes."""
    reply = await _converse(run_id, lace_id, _brief_message(request), jobs)
    async with AsyncSessionLocal() as db, db.begin():
        await lace_briefs.mark_posted(db, brief_id, reply)
        # Its Feed item went up when the brief was due; one held back from an
        # older sweep may predate that.
        if not await lace_activity.fill_ref(db, "brief", brief_id, _first_line(reply)):
            await lace_activity.add(db, lace_id, "brief", lace_activity.BRIEF_TITLE, _first_line(reply),
                                    ref=("brief", brief_id))
    await lace_brief_email.email_brief(brief_id, datetime.now(UTC))
    await _finish(run_id, reply)


async def _converse(run_id: uuid.UUID, lace_id: uuid.UUID, message: HumanMessage, jobs: LaceJobs | None) -> str:
    """Run one turn, streaming its frames; returns the Lace's reply."""
    graph, _ = _graph(lace_id, jobs)
    relay = _TokenRelay(run_id)
    reply = ""
    blocks: list[dict] = []
    async for mode, chunk in graph.astream({"messages": [message]}, thread_config(lace_id),
                                           stream_mode=["updates", "custom"]):
        if mode == "custom":
            if "token" in chunk:
                relay.add(chunk["token"])
            elif chunk.get("reset"):
                # A retry or the next model starts the answer over: say so,
                # rather than wiping the text without a word.
                relay.reset()
                await events.publish(run_id, "step", {"text": RETRY_STEP})
            continue
        relay.flush()
        for node, output in chunk.items():
            for message in (output or {}).get("messages", []):
                if node == "agent" and message.tool_calls:
                    # Text before a tool call ("let me look that up") is not the
                    # reply: it leaves the reply box and stays in the trail.
                    relay.reset()
                    if said := narration(message.content):
                        await events.publish(run_id, "step", {"text": said})
                    for tool_call in message.tool_calls:
                        await events.publish(run_id, "step", {"text": step_text(tool_call)})
                elif node == "agent":
                    reply = str(message.content)
                elif isinstance(message, ToolMessage):
                    await events.publish(run_id, "tool_result", _tool_summary(message))
                    blocks += _ui_blocks(message)
    if blocks:
        await _attach_ui(graph, lace_id, blocks)
    return reply


# Where a reply keeps the cards and choices shown under it.
UI_KEY = "ui"
# The tools whose results put something under the reply.
_UI_TOOLS = frozenset({"ask_choice", "ask_checklist", "ask_form", "show", "suggest_replies"})
# The blocks the founder answers.
_QUESTION_TYPES = frozenset({"choices", "checklist", "form"})
_UI_BLOCK = TypeAdapter(UiBlock)


def _ui_blocks(message: ToolMessage) -> list[dict]:
    if message.name not in _UI_TOOLS:
        return []
    try:
        result = json.loads(str(message.content))
    except ValueError:
        return []
    return list((result.get("data") or {}).get("ui") or []) if result.get("ok") else []


async def _attach_ui(graph, lace_id: uuid.UUID, blocks: list[dict]) -> None:
    """Keep the turn's cards and choices on its final reply, in the thread,
    so they show with it whenever the conversation is read."""
    state = await graph.aget_state(thread_config(lace_id))
    reply = next((m for m in reversed(state.values.get("messages", [])) if isinstance(m, AIMessage)), None)
    if reply is None:
        return
    updated = reply.model_copy(update={"additional_kwargs": {**reply.additional_kwargs, UI_KEY: blocks}})
    await graph.aupdate_state(thread_config(lace_id), {"messages": [updated]}, as_node="agent")


def visible_messages(messages: list[AnyMessage]) -> list[dict]:
    """The conversation as the founder sees it: their messages and the Lace's
    replies (with any cards or choices), without tool calls, results or updates."""
    out = []
    about = None  # the draft the founder's latest message was about
    for m in messages:
        if isinstance(m, HumanMessage) and m.additional_kwargs.get(EVENT_FLAG):
            about = None  # the Lace answers an update, not the founder
        elif isinstance(m, HumanMessage):
            attached = m.additional_kwargs.get(ATTACHMENTS_KEY)
            content = m.additional_kwargs.get(FOUNDER_TEXT_KEY, str(m.content))
            answer = m.additional_kwargs.get(ANSWER_KEY)
            about = m.additional_kwargs.get(DRAFT_KEY)
            out.append({"role": "founder", "content": content, **({"documents": attached} if attached else {}),
                        **({"answer": answer} if answer else {}), **({"draft_id": about} if about else {})})
        elif isinstance(m, AIMessage) and not m.tool_calls:
            ui = m.additional_kwargs.get(UI_KEY)
            if str(m.content).strip() or ui:
                out.append({"role": "lace", "content": str(m.content), **({"ui": ui} if ui else {}),
                            **({"draft_id": about} if about else {})})
    return out


async def _thread(lace_id: uuid.UUID) -> list[AnyMessage]:
    graph, _ = _graph(lace_id)
    state = await graph.aget_state(thread_config(lace_id))
    return (state.values or {}).get("messages", []) if state else []


async def history(lace_id: uuid.UUID, limit: int) -> list[dict]:
    return visible_messages(await _thread(lace_id))[-limit:]


def open_question(messages: list[AnyMessage], block_id: str):
    """The question with this id, if it is under the latest reply and nobody
    has answered since; else None."""
    shown = visible_messages(messages)
    if not shown or shown[-1]["role"] != "lace":
        return None
    for block in shown[-1].get("ui") or []:
        if block.get("type") in _QUESTION_TYPES and block.get("id") == block_id:
            return _UI_BLOCK.validate_python(block)
    return None


async def answer_message(lace_id: uuid.UUID, answer: BlockAnswer) -> HumanMessage:
    """The founder's answer to a question under the Lace's latest reply, as
    their next message. Raises ConflictError when that question is no longer
    open, InvalidInputError when the answer does not fit it."""
    question = open_question(await _thread(lace_id), answer.block_id)
    if question is None:
        raise ConflictError("That question was already answered, or the conversation has moved on.")
    try:
        for_lace, for_founder = describe(question, answer)
    except AnswerError as exc:
        raise InvalidInputError(str(exc)) from exc
    return HumanMessage(content=for_lace, additional_kwargs={FOUNDER_TEXT_KEY: for_founder,
                                                             ANSWER_KEY: answer.model_dump()})
