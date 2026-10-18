"""Running migrations in-process must not disable the app's logger (the test
session migrates at start, and every later log assertion then saw nothing)."""

from pathlib import Path

from alembic import command
from alembic.config import Config as AlembicConfig

from utils.log import logger

_ALEMBIC_INI = Path(__file__).resolve().parents[2] / "alembic.ini"


def test_app_logger_survives_a_migration_run():
    command.upgrade(AlembicConfig(str(_ALEMBIC_INI)), "head")  # already at head: only env.py's setup runs
    assert not logger.disabled
