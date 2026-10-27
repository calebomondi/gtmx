"""Persists usage records for cost reporting: every LLM call attempt
(agents.llm.set_usage_sink) and every paid Exa / Bright Data call
(utils.usage.set_sink).

Both sinks are called synchronously from agent worker threads, so they write
with a small thread-safe psycopg pool rather than the async SQLAlchemy engine.
The run is read from the same context variable for both, so a call made
inside a run is attributed to it.
"""

from psycopg_pool import ConnectionPool

from agents.llm import main as llm
from backend.app.database.connect import NO_PREPARED_STATEMENTS
from config import settings
from utils import usage as api_usage
from utils.log import current_run_id

_pool: ConnectionPool | None = None

_INSERT_LLM = (
    "INSERT INTO llm_calls (run_id, log_label, provider, model, input_tokens, output_tokens, seconds, ok)"
    " VALUES (%(run_id)s, %(log_label)s, %(provider)s, %(model)s, %(input_tokens)s, %(output_tokens)s,"
    " %(seconds)s, %(ok)s)"
)
_INSERT_API = (
    "INSERT INTO api_calls (run_id, provider, operation, seconds, ok)"
    " VALUES (%(run_id)s, %(provider)s, %(operation)s, %(seconds)s, %(ok)s)"
)


def _record_llm(call: dict) -> None:
    with _pool.connection() as conn:
        conn.execute(_INSERT_LLM, call)


def _record_api(call: dict) -> None:
    with _pool.connection() as conn:
        conn.execute(_INSERT_API, {**call, "run_id": current_run_id.get()})


def start() -> None:
    global _pool
    _pool = ConnectionPool(settings.database_url, min_size=1, max_size=settings.usage_pool_size, open=True,
                           kwargs={"autocommit": True, **NO_PREPARED_STATEMENTS})
    llm.set_usage_sink(_record_llm)
    api_usage.set_sink(_record_api)


def stop() -> None:
    global _pool
    llm.set_usage_sink(None)
    api_usage.set_sink(None)
    if _pool is not None:
        _pool.close()
        _pool = None
