"""Persists the agents' per-call LLM usage records (agents.llm.set_usage_sink).

The sink is called synchronously from agent worker threads, so it writes with
a small thread-safe psycopg pool rather than the async SQLAlchemy engine.
"""

from psycopg_pool import ConnectionPool

from agents.llm import main as llm
from config import settings

_pool: ConnectionPool | None = None

_INSERT = (
    "INSERT INTO llm_calls (run_id, log_label, provider, model, input_tokens, output_tokens, seconds, ok)"
    " VALUES (%(run_id)s, %(log_label)s, %(provider)s, %(model)s, %(input_tokens)s, %(output_tokens)s,"
    " %(seconds)s, %(ok)s)"
)


def _record(call: dict) -> None:
    with _pool.connection() as conn:
        conn.execute(_INSERT, call)


def start() -> None:
    global _pool
    _pool = ConnectionPool(settings.database_url, min_size=1, max_size=4, open=True,
                           kwargs={"autocommit": True, "prepare_threshold": None})
    llm.set_usage_sink(_record)


def stop() -> None:
    global _pool
    llm.set_usage_sink(None)
    if _pool is not None:
        _pool.close()
        _pool = None
