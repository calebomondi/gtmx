"""The run manager: runs are owned by the server, persist every frame, fail
loudly without leaking internals, can be cancelled, and are failed after a
restart instead of being left running."""

import asyncio

import pytest

from backend.app.database import models
from backend.app.database.connect import AsyncSessionLocal
from backend.app.runs import events, manager
from backend.app.services.errors import NotFoundError
from backend.tests.helpers import make_user


async def _wait_for_status(run_id, statuses, timeout=5.0):
    async with asyncio.timeout(timeout):
        while True:
            async with AsyncSessionLocal() as db:
                run = await db.get(models.Run, run_id)
            if run.status in statuses:
                return run
            await asyncio.sleep(0.02)


async def _frames(run_id, after=0):
    out = []
    async with asyncio.timeout(5):
        async for frame in events.subscribe(run_id, after):
            out.append(frame)
            if frame["type"] in events.TERMINAL_FRAME_TYPES:
                return out


async def _run(owner, kind="lace_monitor") -> models.Run:
    async with AsyncSessionLocal() as db:
        run = models.Run(user_id=owner.id, kind=kind, status="running")
        db.add(run)
        await db.commit()
    return run


async def test_frames_replay_after_a_cursor():
    run = await _run(make_user("Owner"))
    for step in ("one", "two"):
        await events.publish(run.id, "step", {"text": step})
    await events.publish(run.id, "complete", {})
    everything = await _frames(run.id)
    assert [f["type"] for f in everything] == ["step", "step", "complete"]
    rest = await _frames(run.id, after=everything[0]["event_id"])
    assert [f.get("text") for f in rest] == ["two", None]
    ids = [f["event_id"] for f in everything]
    assert ids == sorted(set(ids))  # monotonic, no duplicates


async def test_failure_is_recorded_without_leaking_internals():
    owner = make_user("Owner")
    run = await _run(owner)

    async def explode():
        raise RuntimeError("provider exploded with secret details")

    manager._spawn(run.id, owner.id, explode(), timeout_s=5)
    failed = await _wait_for_status(run.id, {"failed"})
    assert "secret" not in failed.error
    assert (await _frames(run.id))[-1]["type"] == "error"


async def test_cancel_and_restart_recovery():
    owner, intruder = make_user("Owner"), make_user("Intruder")
    run = await _run(owner)
    manager._spawn(run.id, owner.id, asyncio.sleep(60), timeout_s=120)
    with pytest.raises(NotFoundError):
        await manager.cancel(intruder.id, run.id)
    cancelled = await manager.cancel(owner.id, run.id)
    assert cancelled.status == "cancelled" and run.id not in manager._tasks
    assert (await _frames(run.id))[-1]["type"] == "cancelled"

    # A run left `running` by a dead process is failed on the next boot.
    stranded = await _run(owner)
    await manager.recover_after_restart()
    async with AsyncSessionLocal() as db:
        assert (await db.get(models.Run, stranded.id)).status == "failed"
