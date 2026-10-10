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
    return AuthUser(id=uuid.uuid4(), email="owner@example.com", name="Owner", avatar_url=None)


@pytest.fixture
def client(user: AuthUser):
    """The real API router, signed in as `user`. NullPool because TestClient
    runs requests on its own event loop and pooled async connections must not
    cross loops."""
    engine = create_async_engine(settings.sqlalchemy_database_url, poolclass=NullPool)
    sessions = async_sessionmaker(engine, expire_on_commit=False)

    async def _get_db():
        async with sessions() as session:
            yield session

    app = FastAPI()
    app.include_router(api_router, prefix=settings.api_v1_str)
    app.dependency_overrides[get_db] = _get_db
    app.dependency_overrides[require_user] = lambda: user
    with TestClient(app, base_url="http://test") as test_client:
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
