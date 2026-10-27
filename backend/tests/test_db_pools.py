"""Every connection pool the API opens must work behind Supabase's transaction
pooler, which can't keep a prepared statement between transactions."""

from sqlalchemy import text

from backend.app import agents_runtime, usage
from backend.app.database.connect import engine
from config import settings


async def test_sqlalchemy_connections_never_prepare():
    async with engine.connect() as conn:
        await conn.execute(text("SELECT 1"))
        raw = await conn.get_raw_connection()
        assert raw.driver_connection.prepare_threshold is None


def test_usage_connections_never_prepare():
    usage.start()
    try:
        with usage._pool.connection() as conn:
            assert conn.prepare_threshold is None
    finally:
        usage.stop()


async def test_checkpointer_connections_never_prepare():
    await agents_runtime.start_agent_runtime(settings.database_url)
    try:
        async with agents_runtime._pool.connection() as conn:
            assert conn.prepare_threshold is None
    finally:
        await agents_runtime.stop_agent_runtime()
