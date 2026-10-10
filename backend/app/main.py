import uuid

from fastapi import FastAPI
from contextlib import asynccontextmanager
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import inspect as sa_inspect, select, text

from backend.app.config.settings import settings
from backend.app.api.v1.routes import api_router
from backend.app.database import models  # noqa: F401
from backend.app.database.connect import Base, engine, AsyncSessionLocal
from backend.app import agents_runtime


def _ensure_workspace_columns(sync_conn):
    """Dev has no alembic and create_all never adds columns to existing tables
    — add newer columns to pre-existing databases."""
    inspector = sa_inspect(sync_conn)
    columns = {col["name"] for col in inspector.get_columns("workspaces")}
    if "name" not in columns:
        sync_conn.execute(text("ALTER TABLE workspaces ADD COLUMN name VARCHAR(100)"))
    if "pinned" not in columns:
        sync_conn.execute(
            text("ALTER TABLE workspaces ADD COLUMN pinned BOOLEAN NOT NULL DEFAULT 0")
        )
    if "project_id" not in columns:
        sync_conn.execute(
            text("ALTER TABLE workspaces ADD COLUMN project_id VARCHAR(36)")
        )
    if "archived" not in columns:
        sync_conn.execute(
            text("ALTER TABLE workspaces ADD COLUMN archived BOOLEAN NOT NULL DEFAULT 0")
        )
    if "archived_at" not in columns:
        sync_conn.execute(text("ALTER TABLE workspaces ADD COLUMN archived_at DATETIME"))
    profile_columns = {
        col["name"] for col in inspector.get_columns("product_profiles")
    }
    if "insights" not in profile_columns:
        sync_conn.execute(
            text("ALTER TABLE product_profiles ADD COLUMN insights JSON")
        )


def _ensure_competitor_columns(sync_conn):
    """Same gap as above, for the competitors tables.

    Split out rather than folded into `_ensure_workspace_columns` because it is a
    different concern with a different failure mode: these tables are new, so
    create_all builds them whole and this only ever runs against a database that
    already has them from an earlier build of the same feature.

    `notes` is the only column that has been added after the tables first
    shipped. It is nullable with no default, so the ALTER is additive and
    existing rows read back as NULL -- which is correct, since a note is
    something the user writes and a pre-existing row has none.
    """
    inspector = sa_inspect(sync_conn)
    tables = set(inspector.get_table_names())
    if "competitors" not in tables:
        return  # brand new database; create_all already made the full table
    columns = {col["name"] for col in inspector.get_columns("competitors")}
    if "notes" not in columns:
        sync_conn.execute(text("ALTER TABLE competitors ADD COLUMN notes TEXT"))


@asynccontextmanager
async def lifespan(app: FastAPI):
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
        await connection.run_sync(_ensure_workspace_columns)
        await connection.run_sync(_ensure_competitor_columns)
    await agents_runtime.start_agent_runtime(settings.DATABASE_URL)
    try:
        yield
    finally:
        await agents_runtime.stop_agent_runtime()

def create_application() -> FastAPI:
    # FastAPI instance
    application = FastAPI(
        title= settings.PROJECT_NAME,
        lifespan=lifespan
    )
    # CORS — only relevant when the API and frontend live on different origins.
    # Same-origin deployments (dev proxy / reverse proxy) do not require it.
    if settings.ALLOWED_ORIGINS:
        application.add_middleware(
            CORSMiddleware,
            allow_origins=settings.ALLOWED_ORIGINS,
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"]
        )
    # Include routers
    application.include_router(api_router, prefix=settings.API_V1_STR)

    @application.get("/health", tags=["ops"])
    async def health():
        """Liveness/readiness for local tooling and the dev loop.

        Reports the two dependencies an agent run actually needs, so a failing
        run can be told apart from a failing environment.
        """
        checks = {"database": "ok", "agent_runtime": "ok"}
        status = 200
        try:
            async with AsyncSessionLocal() as db:
                await db.execute(text("SELECT 1"))
        except Exception as exc:
            checks["database"] = f"error: {exc}"
            status = 503
        try:
            agents_runtime.get_agent()
        except Exception as exc:
            checks["agent_runtime"] = f"error: {exc}"
            status = 503
        return JSONResponse(
            status_code=status,
            content={"status": "ok" if status == 200 else "degraded", **checks},
        )

    return application


app = create_application()
