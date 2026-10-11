"""Concurrent discovery load test (plan 7.3).

Runs N real discovery runs at once through the real run manager, as N
distinct users, answering each interview question automatically. Reports
per-run time and outcome, event-loop lag (anything blocking the loop shows
up here), DB pool use, thread count, and LLM call failures/fallbacks.

Spends real LLM and search credit. Run with the scheduler off:

    MONITOR_ENABLED=false uv run python -m scripts.load_test --runs 10

Test users are random ids; --cleanup deletes their workspaces and runs.
"""

import argparse
import asyncio
import faulthandler
import signal
import statistics
import threading
import time
import uuid
from datetime import UTC, datetime

from sqlalchemy import delete, func, select

from backend.app.database import models
from backend.app.database.connect import AsyncSessionLocal, engine
from backend.app.main import app
from backend.app.runs import manager
from backend.app.schemas.agents import DiscoveryRequest
from backend.app.services.runs import TERMINAL_STATUSES
from utils.log import logger

OFFERS = [
    ("Linear", "https://linear.app"), ("Cal.com", "https://cal.com"), ("Plausible", "https://plausible.io"),
    ("Resend", "https://resend.com"), ("PostHog", "https://posthog.com"), ("Tally", "https://tally.so"),
    ("Raycast", "https://www.raycast.com"), ("Loom", "https://www.loom.com"), ("Attio", "https://attio.com"),
    ("Clay", "https://www.clay.com"), ("Pitch", "https://pitch.com"), ("Fathom", "https://fathom.video"),
]
CONFIRM = "Yes, that's right. Please continue."
MAX_ANSWERS = 8
POLL_S = 2.0
LAG_SAMPLE_S = 0.25


async def _last_interrupt(run_id: uuid.UUID) -> dict:
    async with AsyncSessionLocal() as db:
        event = await db.scalar(
            select(models.RunEvent).where(models.RunEvent.run_id == run_id, models.RunEvent.type == "interrupt")
            .order_by(models.RunEvent.id.desc())
        )
    return event.payload if event else {}


async def _drive(user_id: uuid.UUID, name: str, url: str, unexpected: list) -> dict:
    started = time.monotonic()
    run = await manager.start_discovery(
        user_id, DiscoveryRequest(product_name=name, product_url=url, target_geo=["United States"]),
    )
    answers = 0
    while True:
        await asyncio.sleep(POLL_S)
        async with AsyncSessionLocal() as db:
            current = await db.get(models.Run, run.id)
        if current.status in TERMINAL_STATUSES:
            break
        if current.status == "awaiting_input":
            if answers >= MAX_ANSWERS:
                await manager.cancel(user_id, run.id)
                break
            question = await _last_interrupt(run.id)
            if question.get("interrupt_type") != "product_service_description_confirmation":
                unexpected.append((name, question.get("interrupt_type"), (question.get("question") or "")[:120]))
            await manager.answer(user_id, run.id, CONFIRM)
            answers += 1
    return {"name": name, "run_id": run.id, "status": current.status, "error": current.error,
            "answers": answers, "seconds": round(time.monotonic() - started)}


async def _sample(stop: asyncio.Event, lags: list, pool: list, threads: list) -> None:
    while not stop.is_set():
        before = time.monotonic()
        await asyncio.sleep(LAG_SAMPLE_S)
        lags.append(time.monotonic() - before - LAG_SAMPLE_S)
        pool.append(engine.pool.checkedout())
        threads.append(threading.active_count())


async def _llm_summary(since: datetime, run_ids: list) -> list:
    async with AsyncSessionLocal() as db:
        return (await db.execute(
            select(models.LlmCall.provider, models.LlmCall.model, func.count(),
                   func.count().filter(models.LlmCall.ok.is_(False)), func.avg(models.LlmCall.seconds))
            .where(models.LlmCall.created_at >= since, models.LlmCall.run_id.in_(run_ids))
            .group_by(models.LlmCall.provider, models.LlmCall.model)
        )).all()


async def _cleanup(user_ids: list) -> None:
    async with AsyncSessionLocal() as db:
        await db.execute(delete(models.Run).where(models.Run.user_id.in_(user_ids)))
        await db.execute(delete(models.Workspace).where(models.Workspace.user_id.in_(user_ids)))
        await db.commit()


async def main(runs: int, cleanup: bool) -> None:
    since = datetime.now(UTC)
    users = [uuid.uuid4() for _ in range(runs)]
    unexpected: list = []
    lags: list = []
    pool: list = []
    threads: list = []
    async with app.router.lifespan_context(app):
        stop = asyncio.Event()
        sampler = asyncio.create_task(_sample(stop, lags, pool, threads))
        wall = time.monotonic()
        results = await asyncio.gather(
            *(_drive(u, *OFFERS[i % len(OFFERS)], unexpected) for i, u in enumerate(users)),
            return_exceptions=True,
        )
        wall = time.monotonic() - wall
        stop.set()
        await sampler
        done = [r for r in results if isinstance(r, dict)]
        llm = await _llm_summary(since, [r["run_id"] for r in done])
        if cleanup:
            await _cleanup(users)

    print(f"\n=== {runs} concurrent discovery runs, wall {wall:.0f}s ===")
    for r in results:
        if isinstance(r, dict):
            print(f"{r['name']:<10} {r['status']:<10} {r['seconds']:>4}s answers={r['answers']} {r['error'] or ''}")
        else:
            print(f"driver error: {r!r}")
    secs = [r["seconds"] for r in done if r["status"] == "completed"]
    if secs:
        print(f"completed {len(secs)}/{runs}: median {statistics.median(secs)}s, max {max(secs)}s")
    lags.sort()
    if lags:
        print(f"event-loop lag: p50 {lags[len(lags) // 2] * 1000:.0f}ms, p99 {lags[int(len(lags) * 0.99)] * 1000:.0f}ms, "
              f"max {lags[-1] * 1000:.0f}ms")
    print(f"DB connections checked out: max {max(pool, default=0)}; threads: max {max(threads, default=0)}")
    for provider, model, calls, failed, avg_s in llm:
        print(f"LLM {provider}/{model}: {calls} calls, {failed} failed, avg {avg_s:.1f}s")
    for item in unexpected:
        print(f"unexpected question: {item}")
    logger.info("Load test finished")


if __name__ == "__main__":
    # `kill -USR1 <pid>` writes every thread's stack to stderr: how a stall is
    # diagnosed without a debugger attached.
    faulthandler.register(signal.SIGUSR1, all_threads=True)
    parser = argparse.ArgumentParser()
    parser.add_argument("--runs", type=int, default=10)
    parser.add_argument("--cleanup", action="store_true")
    args = parser.parse_args()
    asyncio.run(main(args.runs, args.cleanup))
