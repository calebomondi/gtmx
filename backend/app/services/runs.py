"""Status bookkeeping for background agent runs (competitor and account runs).
Interim: the run manager (launch plan phase 4) replaces this module."""

import uuid
from typing import TypeVar

from backend.app.database import models
from backend.app.database.connect import AsyncSessionLocal

RunModel = TypeVar("RunModel", models.CompetitorRun, models.AccountRun)


async def set_run_fields(model: type[RunModel], run_id: uuid.UUID, **fields) -> RunModel | None:
    """Write run-status fields in their own short-lived session.

    One session per transition, not one held across the run: the agent takes
    minutes of network and LLM time, and a session checked out that long sits
    idle on a pooled connection. Returns None when the run is gone (its
    workspace was deleted mid-flight), so the caller can stop.
    """
    async with AsyncSessionLocal() as db:
        async with db.begin():
            run = await db.get(model, run_id)
            if run is None:
                return None
            for field, value in fields.items():
                setattr(run, field, value)
            return run
