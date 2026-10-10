"""Backend test fixtures: a migrated Postgres test database, wiped between
tests, and an API client authenticated as a fixed user."""

import uuid
from pathlib import Path

import psycopg
import pytest
from alembic import command
from alembic.config import Config as AlembicConfig
from fastapi import FastAPI
from fastapi.testclient import TestClient
from psycopg import sql
from psycopg.conninfo import conninfo_to_dict, make_conninfo
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from backend.app.api.deps import AuthUser, require_user
from backend.app.api.v1.routes import api_router
from backend.app.database import models  # noqa: F401 -- registers every table on Base.metadata
from backend.app.database.connect import Base, get_db
from backend.app.main import add_service_error_handlers
from backend.tests.helpers import make_user
from config import settings

_ALEMBIC_INI = Path(__file__).resolve().parents[2] / "alembic.ini"


def _create_database_if_missing() -> None:
    dbname = conninfo_to_dict(settings.database_url)["dbname"]
    admin = make_conninfo(settings.database_url, dbname="postgres")
    with psycopg.connect(admin, autocommit=True) as conn:
        exists = conn.execute("SELECT 1 FROM pg_database WHERE datname = %s", (dbname,)).fetchone()
        if not exists:
            conn.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(dbname)))


@pytest.fixture(scope="session", autouse=True)
def migrated_database():
    """Bring the test database to the Alembic head once per session, through
    the same migrations production runs."""
    _create_database_if_missing()
    command.upgrade(AlembicConfig(str(_ALEMBIC_INI)), "head")


@pytest.fixture(autouse=True)
def clean_tables():
    yield
    tables = sql.SQL(", ").join(sql.Identifier(t.name) for t in Base.metadata.sorted_tables)
    with psycopg.connect(settings.database_url, autocommit=True) as conn:
        conn.execute(sql.SQL("TRUNCATE {} RESTART IDENTITY CASCADE").format(tables))


@pytest.fixture
def user() -> AuthUser:
    return make_user("Owner")


@pytest.fixture
def client(user: AuthUser):
    """The real API router, signed in as `user`; `client.sign_in(other)` switches
    the caller mid-test. NullPool because TestClient runs requests on its own
    event loop and pooled async connections must not cross loops."""
    engine = create_async_engine(settings.sqlalchemy_database_url, poolclass=NullPool)
    sessions = async_sessionmaker(engine, expire_on_commit=False)

    async def _get_db():
        async with sessions() as session:
            yield session

    app = FastAPI()
    app.include_router(api_router, prefix=settings.api_v1_str)
    add_service_error_handlers(app)
    app.dependency_overrides[get_db] = _get_db
    signed_in = {"user": user}
    app.dependency_overrides[require_user] = lambda: signed_in["user"]
    with TestClient(app, base_url="http://test") as test_client:
        test_client.sign_in = lambda who: signed_in.update(user=who)
        yield test_client


@pytest.fixture
def seed_workspace():
    """Insert a bare workspace row directly (workspaces are normally created
    by a discovery run, which these tests don't drive)."""
    def _seed(user_id: uuid.UUID, name: str) -> str:
        with psycopg.connect(settings.database_url, autocommit=True) as conn:
            row = conn.execute(
                "INSERT INTO workspaces (id, user_id, name) VALUES (%s, %s, %s) RETURNING id",
                (uuid.uuid4(), user_id, name),
            ).fetchone()
        return str(row[0])
    return _seed


@pytest.fixture
def owned(client, user, seed_workspace):
    """A workspace, project, competitor, account and one run of each kind, all
    owned by `user`."""
    workspace_id = seed_workspace(user.id, "Owner Workspace")
    project = client.post(f"{settings.api_v1_str}/projects/user/{user.id}", json={"name": "owner project"}).json()
    competitor = client.post(
        f"{settings.api_v1_str}/workspaces/{workspace_id}/competitors",
        json={"website": "rival.example", "deep_research": False},
    ).json()
    with psycopg.connect(settings.database_url, autocommit=True) as conn:
        account_id = conn.execute(
            "INSERT INTO accounts (id, workspace_id, name, account_type, tech_stack, recent_news, key_contacts,"
            " pain_signals, hiring_signals, sources, source_queries, why_selected, why_reach_out)"
            " VALUES (%s, %s, 'Acme', 'company', '[]', '[]', '[]', '[]', '[]', '[]', '[]', '[]', '[]') RETURNING id",
            (uuid.uuid4(), workspace_id),
        ).fetchone()[0]
        competitor_run_id = conn.execute(
            "INSERT INTO competitor_runs (id, workspace_id, status, candidates_seen, found, dropped, archetypes_targeted)"
            " VALUES (%s, %s, 'completed', 0, 0, 0, 0) RETURNING id",
            (uuid.uuid4(), workspace_id),
        ).fetchone()[0]
        account_run_id = conn.execute(
            "INSERT INTO account_runs (id, workspace_id, status, candidates_seen, found)"
            " VALUES (%s, %s, 'completed', 0, 0) RETURNING id",
            (uuid.uuid4(), workspace_id),
        ).fetchone()[0]
    return {
        "workspace": workspace_id,
        "project": project["id"],
        "competitor": competitor["id"],
        "account": str(account_id),
        "competitor_run": str(competitor_run_id),
        "account_run": str(account_run_id),
    }
