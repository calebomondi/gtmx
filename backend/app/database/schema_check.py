"""Startup guard: refuse to serve against a database that is not migrated to
the latest Alembic revision. The app never creates or alters tables itself."""

from pathlib import Path

from alembic.config import Config as AlembicConfig
from alembic.runtime.migration import MigrationContext
from alembic.script import ScriptDirectory
from sqlalchemy.ext.asyncio import AsyncEngine

_ALEMBIC_INI = Path(__file__).resolve().parents[3] / "alembic.ini"


class SchemaOutOfDateError(RuntimeError):
    pass


def _code_heads() -> set[str]:
    return set(ScriptDirectory.from_config(AlembicConfig(str(_ALEMBIC_INI))).get_heads())


async def ensure_schema_at_head(engine: AsyncEngine) -> None:
    async with engine.connect() as conn:
        db_heads = await conn.run_sync(
            lambda sync_conn: set(MigrationContext.configure(sync_conn).get_current_heads())
        )
    code_heads = _code_heads()
    if db_heads != code_heads:
        raise SchemaOutOfDateError(
            f"Database schema is at {sorted(db_heads) or 'no revision'}, "
            f"code expects {sorted(code_heads)}. Run: uv run alembic upgrade head"
        )
