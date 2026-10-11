"""Active time from heartbeats: sessions, the credit cap, workspace visits."""

import asyncio
import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import select

from backend.app.database import models
from backend.app.database.connect import AsyncSessionLocal
from backend.app.services import activity
from backend.tests.helpers import make_user

T0 = datetime(2026, 10, 11, 9, 0, tzinfo=UTC)


async def _beat(user_id, workspace_id=None, *, at: int):
    async with AsyncSessionLocal() as db:
        await activity.record_heartbeat(
            db, user_id, uuid.UUID(workspace_id) if workspace_id else None, now=T0 + timedelta(seconds=at),
        )


async def _sessions(user_id):
    async with AsyncSessionLocal() as db:
        rows = await db.scalars(
            select(models.AppSession).where(models.AppSession.user_id == user_id).order_by(models.AppSession.id)
        )
        return [s.active_seconds for s in rows]


async def _workspace_rows(workspace_id):
    async with AsyncSessionLocal() as db:
        row = await db.scalar(
            select(models.WorkspaceActivity).where(models.WorkspaceActivity.workspace_id == uuid.UUID(workspace_id))
        )
        return (row.active_seconds, row.visits) if row else None


async def test_time_accrues_per_session_and_is_capped(user):
    await _beat(user.id, at=0)
    await _beat(user.id, at=60)
    await _beat(user.id, at=60)  # a second tab adds nothing
    await _beat(user.id, at=260)  # laptop asleep in between: capped at 120
    await _beat(user.id, at=260 + 600)  # past the gap: a new session
    await _beat(user.id, at=260 + 660)
    assert await _sessions(user.id) == [180, 60]


async def test_workspace_time_visits_and_last_activity(user, seed_workspace):
    a = seed_workspace(user.id, "Alpha")
    b = seed_workspace(user.id, "Beta")
    await _beat(user.id, a, at=0)
    await _beat(user.id, a, at=60)
    await _beat(user.id, b, at=90)
    await _beat(user.id, a, at=120)
    assert await _workspace_rows(a) == (90, 2)
    assert await _workspace_rows(b) == (30, 1)
    async with AsyncSessionLocal() as db:
        workspace = await db.get(models.Workspace, uuid.UUID(a))
    assert workspace.last_activity == T0 + timedelta(seconds=120)


async def test_simultaneous_pings_share_one_session_and_visit(user, seed_workspace):
    a = seed_workspace(user.id, "Alpha")
    await asyncio.gather(*(_beat(user.id, a, at=0) for _ in range(4)))
    assert await _sessions(user.id) == [0]
    assert await _workspace_rows(a) == (0, 1)


def test_heartbeat_api_rejects_another_users_workspace(client, seed_workspace):
    theirs = seed_workspace(make_user("Other").id, "Theirs")
    assert client.post("/api/v1/activity/heartbeat", json={"workspace_id": theirs}).status_code == 404
    response = client.post("/api/v1/activity/heartbeat", json={})
    assert response.status_code == 200
    assert response.json() == {"next_beat_s": 60}
