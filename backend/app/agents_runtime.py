"""App-lifetime runtime for the Lace graphs: one durable AsyncPostgresSaver
(same database as the app) that every Lace's conversation thread is
checkpointed in. The graphs themselves compile per run around one Lace's
store."""

import enum
import importlib
import inspect
import pkgutil

from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from langgraph.checkpoint.serde.jsonplus import JsonPlusSerializer
from psycopg.rows import dict_row
from psycopg_pool import AsyncConnectionPool
from pydantic import BaseModel

import agents.schemas

from config import settings
from utils.log import logger

# A Lace's thread carries messages, but our own pydantic models can reach a
# checkpoint too. LangGraph's msgpack decoder refuses
# unregistered types: today it only logs a warning, but it is scheduled to
# become a hard failure. Allowlisting the modules' models keeps checkpoints
# readable across that change. Nested models (Competitor, Pricing, Specialist,
# ResearchTask, ...) are serialized as their own entries, so deriving the whole
# set rather than listing only the top-level ones is what covers them.
#
# Every module in the agents.schemas package is scanned, discovered rather than
# listed, so a new schema module is covered without touching this file.
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
_CHECKPOINT_MODULES = tuple(
    importlib.import_module(f"agents.schemas.{info.name}")
    for info in pkgutil.iter_modules(agents.schemas.__path__)
)
_CHECKPOINT_TYPES = [
    (module.__name__, name)
    for module in _CHECKPOINT_MODULES
    for name, obj in inspect.getmembers(module, inspect.isclass)
    if issubclass(obj, (BaseModel, enum.Enum))
    and obj.__module__ == module.__name__
]



_pool: AsyncConnectionPool | None = None
_saver: AsyncPostgresSaver | None = None


async def start_agent_runtime(database_url: str) -> AsyncPostgresSaver:
    """Open the checkpointer pool and ensure its tables. Idempotent."""
    global _pool, _saver
    if _saver is not None:
        return _saver

    pool = AsyncConnectionPool(
        conninfo=database_url,
        # Opened up front, never grown under load: opening a connection
        # resolves the host on the event loop's default thread pool, which
        # concurrent graph nodes can fill, and a checkpoint write waiting on a
        # new connection then deadlocks every run (seen at 10 concurrent runs).
        # Checkpoint reads/writes are short, so a small pool serves many runs.
        min_size=settings.checkpointer_pool_size,
        max_size=settings.checkpointer_pool_size,
        open=False,
        # The settings AsyncPostgresSaver requires. prepare_threshold=None
        # disables server-side prepared statements, which Supabase's
        # transaction-mode pooler does not support.
        kwargs={"autocommit": True, "prepare_threshold": None, "row_factory": dict_row},
    )
    try:
        await pool.open(wait=True)
        saver = AsyncPostgresSaver(
            pool,
            # Session state carries our own pydantic models. Without this they
            # log a deserialization warning on every checkpoint read, and a
            # future LangGraph turns that into a hard block.
            serde=JsonPlusSerializer(allowed_msgpack_modules=_CHECKPOINT_TYPES),
        )
        await saver.setup()
    except Exception:
        await pool.close()
        raise

    _pool = pool
    _saver = saver
    logger.info("Agent runtime ready (checkpointer=postgres)")
    return saver


async def stop_agent_runtime():
    global _pool, _saver
    if _pool is not None:
        await _pool.close()
        _pool = None
    _saver = None


def get_checkpointer() -> AsyncPostgresSaver:
    if _saver is None:
        raise RuntimeError("Agent runtime not started — lifespan did not run")
    return _saver
