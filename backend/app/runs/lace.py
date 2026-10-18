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
from agents.lace.accounts import find_accounts
from agents.lace.competitors import change_fact, find_competitors, material, offer_for_monitor
from agents.lace.onboarding import onboard, opening_message
from agents.lace.store import JobBlocked, LaceJobs
from agents.pipelines.monitor import check_competitor
from agents.lace.prompts import system_prompt
from backend.app.agents_runtime import get_checkpointer
from backend.app.database import models
from backend.app.database.connect import AsyncSessionLocal
from backend.app.database.lace_models import Lace
from backend.app.runs import events
from backend.app.runs.errors import user_facing_error
from backend.app.services import lace_accounts, lace_competitors, lace_events
from backend.app.services.competitors import domain_key
from backend.app.services.lace_store import DbLaceStore
from backend.app.services.runs import set_run_fields
from config import settings
from utils.progress import report

# Competitors one monitoring run checks, and how many at once.
MONITOR_BATCH = 15
MONITOR_CONCURRENCY = 4

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


def _failure(exc: Exception) -> str:
    """Why a job failed, as the Lace will tell it: a reason the founder can fix
    as is, anything else in general terms."""
    return str(exc) if isinstance(exc, JobBlocked) else user_facing_error(exc)


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


async def competitors_job(run_id: uuid.UUID, lace_id: uuid.UUID, params: dict) -> None:
    """Hunt for the Lace's competitors, save them, and queue an update telling
    the Lace what came of it, in the same transaction as the results. A failed
    hunt queues an update too, so the founder hears either way."""
    store = DbLaceStore(AsyncSessionLocal, lace_id)
    profile, facts = await asyncio.gather(store.profile(), store.facts(None, BRIEF_FACTS))
    try:
        with events.reporting_steps(run_id):
            found = await asyncio.to_thread(find_competitors, profile, facts, params.get("focus"))
    except Exception as exc:
        async with AsyncSessionLocal() as db, db.begin():
            await lace_events.add(db, lace_id, f"The competitor search failed: {_failure(exc)}")
        raise
    async with AsyncSessionLocal() as db, db.begin():
        new, refreshed = await lace_competitors.upsert_found(db, lace_id, run_id, found)
        await lace_events.add(db, lace_id, competitors_update(found, new, refreshed))
    await set_run_fields(models.Run, run_id, status="completed", finished_at=datetime.now(UTC),
                         progress={"found": len(found), "new": new, "refreshed": refreshed})
    await events.publish(run_id, "complete", {"found": len(found)})


async def monitor_job(run_id: uuid.UUID, lace_id: uuid.UUID, params: dict) -> None:
    """Check the tracked competitors for moves since their last check. Each
    firm's baseline is saved as it is checked. Material changes become sourced
    facts and one queued update; when nothing material changed, the founder
    is not told anything."""
    store = DbLaceStore(AsyncSessionLocal, lace_id)
    profile, facts = await asyncio.gather(store.profile(), store.facts(None, BRIEF_FACTS))
    our_offer, offer_detail = offer_for_monitor(profile, facts)
    async with AsyncSessionLocal() as db:
        due = [(c.id, c.name, c.website, c.monitor_state)
               for c in await lace_competitors.due_for_check(db, lace_id, MONITOR_BATCH)]
    slots = asyncio.Semaphore(MONITOR_CONCURRENCY)

    async def check_one(competitor_id, name, website, previous) -> tuple[str, list]:
        async with slots:
            state, changes = await asyncio.to_thread(check_competitor.check, name, website, previous, our_offer,
                                                     None, offer_detail)
        async with AsyncSessionLocal() as db, db.begin():
            await lace_competitors.save_check(db, competitor_id, state)
        return name, material(changes)

    with events.reporting_steps(run_id):
        report(f"Checking {len(due)} competitors for changes")
        results = await asyncio.gather(*(check_one(*row) for row in due))

    moves = [(name, change) for name, changes in results for change in changes]
    for name, change in moves:
        fact = change_fact(name, change)
        if fact is not None:
            await store.record_fact(fact)
    if moves:
        async with AsyncSessionLocal() as db, db.begin():
            await lace_events.add(db, lace_id, monitor_update(moves))
    await set_run_fields(models.Run, run_id, status="completed", finished_at=datetime.now(UTC),
                         progress={"checked": len(due), "changes": len(moves)})
    await events.publish(run_id, "complete", {"checked": len(due), "changes": len(moves)})


async def accounts_job(run_id: uuid.UUID, lace_id: uuid.UUID, params: dict) -> None:
    """Search for target accounts on the Lace's ICP, save them with their fit
    cases, and queue an update, in one transaction. The startup's own site and
    every competitor on file (tracked or dismissed) are never targets. A failed
    search queues an update too."""
    store = DbLaceStore(AsyncSessionLocal, lace_id)
    profile, facts, icp = await asyncio.gather(store.profile(), store.facts(None, BRIEF_FACTS), store.icp())
    try:
        if icp is None:
            raise JobBlocked("There is no ideal customer profile to search on yet.")
        async with AsyncSessionLocal() as db:
            exclude = [domain_key(profile.website), *await lace_competitors.all_domains(db, lace_id)]
        with events.reporting_steps(run_id):
            found = await asyncio.to_thread(find_accounts, profile, facts, icp, exclude, params.get("country"))
    except Exception as exc:
        async with AsyncSessionLocal() as db, db.begin():
            await lace_events.add(db, lace_id, f"The search for target accounts failed: {_failure(exc)}")
        raise
    async with AsyncSessionLocal() as db, db.begin():
        new, refreshed = await lace_accounts.upsert_found(db, lace_id, run_id, found)
        await lace_events.add(db, lace_id, accounts_update(found, new, refreshed, params.get("country")))
    await set_run_fields(models.Run, run_id, status="completed", finished_at=datetime.now(UTC),
                         progress={"found": len(found), "new": new, "refreshed": refreshed})
    await events.publish(run_id, "complete", {"found": len(found)})


def accounts_update(found: list, new: int, refreshed: int, country: str | None) -> str:
    where = f" in {country}" if country else ""
    if not found:
        return (f"The search for target accounts{where} finished without finding an account with a current, "
                "verifiable reason to buy.")
    lines = []
    for record, fit in found:
        line = f"{record.name} ({record.website or record.account_type})"
        if record.trigger_event:
            line += f": {record.trigger_event.event}"
        if fit:
            line += f". Need: {fit.need} [{fit.strength} fit]"
        lines.append(line)
    return (f"The search for target accounts{where} finished: {len(found)} accounts ({new} new, {refreshed} "
            "already on file), each with a current trigger:\n" + "\n".join(lines)
            + "\nThey are saved; use list_accounts for the full cases.")


def monitor_update(moves: list) -> str:
    lines = []
    for name, c in moves:
        line = f"{name} [{c.kind}, {c.importance}]: {c.title}. {c.summary}"
        if c.implication:
            line += f" What it means for us: {c.implication}"
        if c.counter_move:
            line += f" Suggested move: {c.counter_move}"
        if c.source_url:
            line += f" (source: {c.source_url})"
        lines.append(line)
    return "Competitor monitoring found changes that matter:\n" + "\n".join(lines)


def competitors_update(found: list, new: int, refreshed: int) -> str:
    if not found:
        return ("The competitor search finished without finding a company that passed the checks "
                "(a real website, competing for the same buyers).")
    names = ", ".join(f"{p.name} ({p.website})" for p in found)
    return (f"The competitor search finished: {len(found)} competitors ({new} new, {refreshed} already tracked): "
            f"{names}. Their profiles are saved; use list_competitors for details.")


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
