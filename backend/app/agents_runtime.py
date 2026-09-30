"""App-lifetime runtime for the discovery agent: compiles the top-level graph
once with a durable AsyncSqliteSaver (same sqlite file as the app DB) so
discovery interrupts and phase progress survive per thread_id."""

import enum
import inspect
from contextlib import AsyncExitStack

import aiosqlite
from langgraph.checkpoint.serde.jsonplus import JsonPlusSerializer
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
from pydantic import BaseModel

import agents.states
import agents.sub_agents.schema_states
from agents.discovery_agent import build_discovery_agent

from utils.log import logger

# Session state is mostly plain dicts and strings, but the specialist team, the
# market/competition extractions and the ICP are pydantic models that get
# written into every checkpoint. LangGraph's msgpack decoder refuses
# unregistered types: today it only logs a warning, but it is scheduled to
# become a hard failure. Allowlisting the modules' models keeps checkpoints
# readable across that change. Nested models (Competitor, Pricing, Specialist,
# ResearchTask, ...) are serialized as their own entries, so deriving the whole
# set rather than listing only the top-level ones is what covers them.
#
# Two modules, because the discovery agent's session models live in
# agents.sub_agents.schema_states (Specialist, Perspectives, TaskList, ...)
# while MarketExtraction/CompetitionExtraction/ICP stay in agents.states.
#
# Derived, not hand-listed: a literal list silently drifts as soon as anyone
# adds a model, which is exactly how BuyerType and ProductCategory came to be
# missing -- MarketExtraction holds both, so every market phase logged
# "Blocked deserialization" on read-back.
#
# The `__module__` guard is load-bearing. `inspect.getmembers` also returns
# BaseModel and Enum, which are only *imported* into these modules; admitting
# them would allowlist pydantic.main and enum. Over-admitting a type that never
# reaches a checkpoint is harmless -- this list exists to avoid the warnings and
# the future hard block, it is not a trust boundary.
_CHECKPOINT_MODULES = (agents.states, agents.sub_agents.schema_states)
_CHECKPOINT_TYPES = [
    (module.__name__, name)
    for module in _CHECKPOINT_MODULES
    for name, obj in inspect.getmembers(module, inspect.isclass)
    if issubclass(obj, (BaseModel, enum.Enum))
    and obj.__module__ == module.__name__
]


def sqlite_path_from_database_url(url: str) -> str:
    """Extract the plain file path from a sqlalchemy sqlite URL, e.g.
    'sqlite+aiosqlite:///./blog.db' -> './blog.db'."""
    prefix = "sqlite+aiosqlite:///"
    if url.startswith(prefix):
        return url[len(prefix):]
    raise ValueError(f"Unsupported DATABASE_URL for the agent runtime: {url}")


_agent = None
_stack: AsyncExitStack | None = None


async def start_agent_runtime(database_url: str):
    """Open the checkpointer connection and compile the agent. Idempotent."""
    global _agent, _stack
    if _agent is not None:
        return _agent

    path = sqlite_path_from_database_url(database_url)
    stack = AsyncExitStack()
    try:
        conn = await stack.enter_async_context(aiosqlite.connect(path))
        # WAL keeps checkpoint writes from blocking the app's own sqlite writes.
        await conn.execute("PRAGMA journal_mode=WAL")
        saver = AsyncSqliteSaver(
            conn,
            # Session state carries our own pydantic models. Without this they
            # log a deserialization warning on every checkpoint read, and a
            # future LangGraph turns that into a hard block.
            serde=JsonPlusSerializer(allowed_msgpack_modules=_CHECKPOINT_TYPES),
        )
    except Exception:
        await stack.aclose()
        raise

    _stack = stack
    _agent = build_discovery_agent(checkpointer=saver)
    logger.info("Discovery agent runtime ready (checkpointer=%s)", path)
    return _agent


async def stop_agent_runtime():
    global _agent, _stack
    if _stack is not None:
        await _stack.aclose()
        _stack = None
    _agent = None


def get_agent():
    if _agent is None:
        raise RuntimeError("Agent runtime not started — lifespan did not run")
    return _agent
