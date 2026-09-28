"""App-lifetime runtime for the GTMX agent: compiles the top-level graph once
with a durable AsyncSqliteSaver (same sqlite file as the app DB) so discovery
interrupts and phase progress survive per thread_id."""

from contextlib import AsyncExitStack

import aiosqlite
from langgraph.checkpoint.serde.jsonplus import JsonPlusSerializer
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver

from agents.gtmx_agent import build_agent

from utils.log import logger

# Session state is mostly plain dicts and strings, but the specialist team, the
# offer snapshot, the market/competition extractions and the ICP are pydantic
# models that get written into every checkpoint. LangGraph's msgpack decoder
# refuses unregistered types: today it only logs a warning, but it is scheduled
# to become a hard failure. Allowlisting the module's models keeps checkpoints
# readable across that change. Nested models (Competitor, Pricing, ...) are
# serialized as their own entries, so they need to be listed too.
_CHECKPOINT_TYPES = [("agents.states", name) for name in (
    "AccountList",
    "AccountRecord",
    "AccountDiscoveryQueries",
    "BuyerPersona",
    "CompetitionExtraction",
    "Competitor",
    "CompetitorLead",
    "CompetitorList",
    "ContactRecord",
    "DomainSpecialist",
    "FollowUp",
    "ICP",
    "IndepthIntakeStep",
    "IntakeStep",
    "MarketExtraction",
    "OfferDataSnapshot",
    "PainSignal",
    "Pricing",
    "SourceRecord",
    "SpecialistTeam",
    "SpecialistReply",
    "TargetChannel",
    "TriggerEvent",
)]


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
    _agent = build_agent(checkpointer=saver)
    logger.info("GTMX agent runtime ready (checkpointer=%s)", path)
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
