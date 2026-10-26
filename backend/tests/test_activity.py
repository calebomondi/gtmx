"""Active time from heartbeats: sessions and the credit cap."""

import asyncio
from datetime import UTC, datetime, timedelta

from sqlalchemy import select

from backend.app.database import models
from backend.app.database.connect import AsyncSessionLocal
from backend.app.services import activity

T0 = datetime(2026, 10, 11, 9, 0, tzinfo=UTC)


async def _beat(user_id, *, at: int):
    async with AsyncSessionLocal() as db:
        await activity.record_heartbeat(db, user_id, now=T0 + timedelta(seconds=at))


async def _sessions(user_id):
    async with AsyncSessionLocal() as db:
        rows = await db.scalars(
            select(models.AppSession).where(models.AppSession.user_id == user_id).order_by(models.AppSession.id)
        )
        return [s.active_seconds for s in rows]


async def test_time_accrues_per_session_and_is_capped(user):
    await _beat(user.id, at=0)
    await _beat(user.id, at=60)
    await _beat(user.id, at=60)  # a second tab adds nothing
    await _beat(user.id, at=260)  # laptop asleep in between: capped at 120
    await _beat(user.id, at=260 + 600)  # past the gap: a new session
    await _beat(user.id, at=260 + 660)
    assert await _sessions(user.id) == [180, 60]


async def test_simultaneous_pings_share_one_session(user):
    await asyncio.gather(*(_beat(user.id, at=0) for _ in range(4)))
    assert await _sessions(user.id) == [0]


def test_heartbeat_api(client):
    response = client.post("/api/v1/activity/heartbeat")
    assert response.status_code == 200
    assert response.json() == {"next_beat_s": 60}
