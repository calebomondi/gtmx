"""In-process scheduler: keeps every active Lace's competitor monitoring,
opportunity and regulation searches, tracked bills and briefs going, and syncs replies to sent outreach
from users' Gmail and linked DM inboxes. Single-instance
by design for launch (one backend process); a multi-instance deployment needs
a leader lock or an external scheduler."""

import asyncio
from datetime import UTC, datetime

from sqlalchemy import select

from agents.lace.brief import brief_request
from agents.lace.store import JobRefused
from backend.app.database.connect import AsyncSessionLocal
from backend.app.database.lace_models import Lace, LaceBrief
from backend.app.runs import manager
from backend.app.services import inbox as inbox_service
from backend.app.services import lace_activity, lace_brief_email, lace_briefs, lace_competitors, lace_opportunities, lace_regulations, social_inbox
from backend.app.services.lace_activity import BRIEF_TITLE, BRIEF_WRITING
from config import settings
from data_sources.legislation import mzalendo
from utils.log import logger

_tasks: list[asyncio.Task] = []


async def sweep_laces() -> int:
    """Start a competitor check for each Lace whose competitors were not
    checked within its watch interval."""
    async with AsyncSessionLocal() as db:
        due = await lace_competitors.laces_due_for_monitoring(db)
    started = 0
    for lace_id, user_id in due:
        try:
            await manager.start_lace_job("lace_monitor", user_id, lace_id, {"scheduled": True})
            started += 1
        except JobRefused:
            continue  # already checking, or this user hit the daily cap; try next sweep
    return started


async def sweep_lace_opportunities() -> int:
    """Start an opportunity search for each Lace due one by its watch interval."""
    async with AsyncSessionLocal() as db:
        due = await lace_opportunities.laces_due_for_scan(db)
    started = 0
    for lace_id, user_id in due:
        try:
            await manager.start_lace_job("lace_opportunities", user_id, lace_id, {"scheduled": True})
            started += 1
        except JobRefused:
            continue  # this user hit the daily cap; try next sweep
    return started


async def sweep_lace_regulations() -> int:
    """Start a regulations search for each Lace with a confirmed jurisdiction
    that is due one."""
    async with AsyncSessionLocal() as db:
        due = await lace_regulations.laces_due_for_search(db)
    started = 0
    for lace_id, user_id in due:
        try:
            await manager.start_lace_job("lace_regulations", user_id, lace_id, {"scheduled": True})
            started += 1
        except JobRefused:
            continue  # this user hit the daily cap; try next sweep
    return started


async def check_bills(now: datetime | None = None) -> int:
    """Read where each tracked Kenyan bill now stands, once per check interval,
    from one read of the tracker for every Lace. Returns how many moved."""
    now = now or datetime.now(UTC)
    async with AsyncSessionLocal() as db:
        bills = await lace_regulations.bills_due_for_check(db, now)
        if not bills:
            return 0
        try:
            tracker = await asyncio.to_thread(mzalendo.bill_stages, lace_regulations.houses_of(bills))
        except mzalendo.MzalendoError as exc:
            logger.warning("Bill check skipped, tried again next sweep: %s", exc)
            return 0
        moves = await lace_regulations.apply_stages(db, bills, tracker, now)
        await db.commit()
    return len(moves)


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
                # On the Feed straight away; filled in once the Lace has written it.
                await lace_activity.add(db, lace.id, "brief", BRIEF_TITLE, BRIEF_WRITING, ref=("brief", brief.id))
                to_post.append((lace.user_id, lace.id, brief.id, brief_request(digest, lace.brief_frequency,
                                                                              _since_label(since, lace))))
        # Briefs still waiting from an earlier sweep (the Lace was busy then).
        waiting = (await db.execute(select(LaceBrief, Lace).join(Lace, Lace.id == LaceBrief.lace_id).where(
            LaceBrief.posted_at.is_(None), LaceBrief.created_at >= now - lace_briefs.PENDING_MAX_AGE))).all()
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
    """Start each Lace's due monitoring, opportunity and regulation searches
    and brief, read tracked bills' stages, and email briefs held back.
    Returns how many runs started."""
    started = (await sweep_laces() + await sweep_lace_opportunities() + await sweep_lace_regulations()
               + await sweep_briefs())
    await check_bills()
    await lace_brief_email.email_waiting(datetime.now(UTC))
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


async def _read_replies(replies) -> None:
    """One reading run per Lace that got replies; its update tells the founder."""
    for lace_id, user_id in {(m.lace_id, m.user_id) for m in replies}:
        try:
            await manager.start_lace_job("lace_reply", user_id, lace_id, {})
        except JobRefused as exc:
            logger.info("Reading replies for Lace %s waits: %s", lace_id, exc)


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
            await _read_replies(result.replies)
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
