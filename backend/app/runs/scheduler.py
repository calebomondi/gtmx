"""In-process scheduler: keeps every active workspace's and Lace's competitor
monitoring fresh, and syncs replies to sent outreach from users' Gmail. Single-instance
by design for launch (one backend process); a multi-instance deployment needs
a leader lock or an external scheduler."""

import asyncio
from datetime import UTC, datetime, timedelta

from sqlalchemy import func, or_, select

from agents.lace.brief import brief_request
from agents.lace.store import JobRefused
from backend.app.database import models
from backend.app.database.connect import AsyncSessionLocal
from backend.app.database.lace_models import Lace, LaceBrief
from backend.app.runs import background, manager
from backend.app.services import inbox as inbox_service
from backend.app.services import lace_briefs, lace_competitors, lace_opportunities, social_inbox
from backend.app.services.errors import RateLimitedError
from backend.app.services.runs import TERMINAL_STATUSES
from config import settings
from utils.log import logger

_tasks: list[asyncio.Task] = []
# A brief that could not be posted within this long is dropped for the next one.
_PENDING_BRIEF_MAX_AGE = timedelta(hours=12)


async def _stale_workspaces() -> list[tuple]:
    """(workspace_id, user_id) of live workspaces with a competitor that was
    never checked or is past the max age, and no monitor run in flight."""
    cutoff = datetime.now(UTC) - timedelta(hours=settings.monitor_max_age_h)
    in_flight = select(models.Run.workspace_id).where(
        models.Run.kind == "monitor", models.Run.status.not_in(TERMINAL_STATUSES),
    )
    async with AsyncSessionLocal() as db:
        rows = await db.execute(
            select(models.Workspace.id, models.Workspace.user_id)
            .join(models.Competitor, models.Competitor.workspace_id == models.Workspace.id)
            .where(
                models.Workspace.archived.is_(False),
                or_(models.Competitor.last_checked_at.is_(None), models.Competitor.last_checked_at < cutoff),
                models.Workspace.id.not_in(in_flight),
            )
            .group_by(models.Workspace.id, models.Workspace.user_id)
            .having(func.count(models.Competitor.id) > 0)
        )
        return list(rows.all())


async def sweep_laces() -> int:
    """Start a competitor check for each Lace with stale competitors."""
    async with AsyncSessionLocal() as db:
        due = await lace_competitors.laces_due_for_monitoring(db, timedelta(hours=settings.monitor_max_age_h))
    started = 0
    for lace_id, user_id in due:
        try:
            await manager.start_lace_job("lace_monitor", user_id, lace_id, {"scheduled": True})
            started += 1
        except JobRefused:
            continue  # already checking, or this user hit the daily cap; try next sweep
    return started


async def sweep_lace_opportunities() -> int:
    """Start the weekly opportunity search for each Lace that is due."""
    async with AsyncSessionLocal() as db:
        due = await lace_opportunities.laces_due_for_scan(db, timedelta(days=settings.lace_opportunity_scan_days))
    started = 0
    for lace_id, user_id in due:
        try:
            await manager.start_lace_job("lace_opportunities", user_id, lace_id, {"scheduled": True})
            started += 1
        except JobRefused:
            continue  # this user hit the daily cap; try next sweep
    return started


async def sweep_briefs(now: datetime | None = None) -> int:
    """Post each Lace's brief when it is due in the founder's timezone. A Lace
    with nothing to tell gets none; one that is mid-conversation gets it at the
    next sweep. Returns how many briefs were started."""
    now = now or datetime.now(UTC)
    to_post: list[tuple] = []
    async with AsyncSessionLocal() as db:
        for lace in await lace_briefs.due_laces(db, now):
            since = lace_briefs.since_for(lace, now)
            digest = await lace_briefs.digest(db, lace.id, since, now.astimezone(lace_briefs.zone(lace.timezone)).date())
            lace.last_brief_at = now
            if digest:
                brief = LaceBrief(lace_id=lace.id, digest=digest)
                db.add(brief)
                await db.flush()
                to_post.append((lace.user_id, lace.id, brief.id, brief_request(digest, lace.brief_frequency,
                                                                              _since_label(since, lace))))
        # Briefs still waiting from an earlier sweep (the Lace was busy then).
        waiting = (await db.execute(select(LaceBrief, Lace).join(Lace, Lace.id == LaceBrief.lace_id).where(
            LaceBrief.posted_at.is_(None), LaceBrief.created_at >= now - _PENDING_BRIEF_MAX_AGE))).all()
        await db.commit()
    queued = {brief_id for _, _, brief_id, _ in to_post}
    to_post += [(lace.user_id, lace.id, brief.id, brief_request(brief.digest, lace.brief_frequency,
                                                                "since the last brief"))
                for brief, lace in waiting if brief.id not in queued]
    started = 0
    for user_id, lace_id, brief_id, request in to_post:
        if await manager.post_brief(user_id, lace_id, brief_id, request):
            started += 1
    return started


def _since_label(since: datetime, lace: Lace) -> str:
    return "since " + since.astimezone(lace_briefs.zone(lace.timezone)).strftime("%a %d %b, %H:%M")


async def sweep() -> int:
    """Start a monitor run for each stale workspace and each stale Lace.
    Returns how many started."""
    started = await sweep_laces() + await sweep_lace_opportunities() + await sweep_briefs()
    for workspace_id, user_id in await _stale_workspaces():
        try:
            await manager.start_background("monitor", user_id, workspace_id)
            started += 1
        except RateLimitedError:
            continue  # this user hit the daily cap; try again next sweep
    return started


async def sync_lace_channels() -> int:
    """Read new DMs to the founders' linked Instagram and Facebook accounts;
    each Lace that received some reads and answers them. Returns how many arrived."""
    async with AsyncSessionLocal() as db:
        received = await social_inbox.sync_all(db)
    for lace_id, (user_id, _count) in received.items():
        try:
            await manager.start_lace_job("lace_reply", user_id, lace_id, {})
        except JobRefused as exc:
            logger.info("Reading DMs for Lace %s waits: %s", lace_id, exc)
    return sum(count for _user, count in received.values())


async def sync_inboxes() -> int:
    """Sync every user with recent sends, and every linked DM inbox. Returns
    how many replies and DMs arrived."""
    async with AsyncSessionLocal() as db:
        users = await inbox_service.users_to_sync(db)
    arrived = 0
    for user_id in users:
        try:
            async with AsyncSessionLocal() as db:
                result = await inbox_service.sync_user(db, user_id)
            await background.after_inbox_sync(result)
            arrived += len(result.replies)
        except Exception:  # noqa: BLE001 -- one user's mailbox must not stop the rest
            logger.exception("Inbox sync failed for user %s", user_id)
    return arrived + await sync_lace_channels()


async def _loop(job, name: str, interval_s: float) -> None:
    await asyncio.sleep(settings.monitor_initial_delay_s)
    while True:
        try:
            count = await job()
            if count:
                logger.info("%s: %d", name, count)
        except Exception:  # noqa: BLE001 -- the scheduler must outlive one bad sweep
            logger.exception("%s failed", name)
        await asyncio.sleep(interval_s)


def start() -> None:
    if _tasks:
        return
    if settings.monitor_enabled:
        _tasks.append(asyncio.create_task(
            _loop(sweep, "Monitoring sweep", settings.monitor_scan_interval_s), name="monitor-scheduler"))
    if settings.inbox_sync_enabled:
        _tasks.append(asyncio.create_task(
            _loop(sync_inboxes, "Inbox sync", settings.inbox_sync_interval_s), name="inbox-scheduler"))


async def stop() -> None:
    for task in _tasks:
        task.cancel()
    await asyncio.gather(*_tasks, return_exceptions=True)
    _tasks.clear()
