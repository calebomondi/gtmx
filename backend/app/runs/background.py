"""Background run kinds: no questions, one segment from start to finish. The
runner does the agent work and the database writes; this records the outcome
on the run and publishes it, so all kinds share one lifecycle (manager)."""

import asyncio
import uuid
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime, timedelta

from sqlalchemy import select

from agents.concurrency import ContextThreadPoolExecutor
from agents.pipelines.chat import workspace_chat
from agents.pipelines.monitor import check_competitor
from agents.pipelines.monitor import socials as competitor_socials
from agents.pipelines.outreach import gtm_specialist
from backend.app.account_runner import run_account_discovery_for_workspace
from backend.app.competitor_runner import research_competitor_site, run_competitor_discovery
from backend.app.database import models
from backend.app.database.connect import AsyncSessionLocal
from backend.app.runs import events, signals
from backend.app.services import chat as chat_service
from backend.app.services import competitors as competitor_service
from backend.app.services import outreach as outreach_service
from backend.app.services import specialists as specialist_service
from backend.app.services.errors import RateLimitedError
from config import settings
from utils.log import logger


async def _finish(run_id: uuid.UUID, outcome: dict) -> None:
    # Status and outcome in one transaction: a poll must never see "completed"
    # before the counts it reports are written.
    async with AsyncSessionLocal() as db:
        async with db.begin():
            run = await db.get(models.Run, run_id)
            if run is not None:
                run.status, run.finished_at = "completed", datetime.now(UTC)
                run.progress = {**(run.progress or {}), **outcome}
    await events.publish(run_id, "complete", outcome)


async def _start_monitoring(run_id: uuid.UUID, workspace_id: uuid.UUID) -> None:
    """New rivals get their baseline and social stats now, not at the next
    scheduler sweep up to an hour later."""
    if not settings.monitor_enabled:
        return
    from backend.app.runs import manager  # manager imports this module

    async with AsyncSessionLocal() as db:
        user_id = (await db.get(models.Run, run_id)).user_id
        if await competitor_service.active_monitor_run(db, workspace_id):
            return
    try:
        await manager.start_background("monitor", user_id, workspace_id)
    except RateLimitedError:
        logger.info("Monitoring for workspace %s waits for the next sweep (daily cap)", workspace_id)


async def competitors(run_id: uuid.UUID, workspace_id: uuid.UUID, _params: dict) -> None:
    await _finish(run_id, await run_competitor_discovery(workspace_id=workspace_id, run_id=run_id))
    await signals.competitors_found(run_id)
    await _start_monitoring(run_id, workspace_id)


async def accounts(run_id: uuid.UUID, workspace_id: uuid.UUID, _params: dict) -> None:
    await _finish(run_id, await run_account_discovery_for_workspace(workspace_id=workspace_id, run_id=run_id))
    await signals.accounts_found(run_id)


async def competitor_research(run_id: uuid.UUID, workspace_id: uuid.UUID, params: dict) -> None:
    """Fill in one manually added competitor from its own website. A failure
    leaves the row's `unsourced_fields` as the honest record."""
    researched = await research_competitor_site(
        workspace_id=workspace_id, competitor_id=uuid.UUID(params["competitor_id"]),
    )
    await _finish(run_id, {"researched": bool(researched)})
    await _start_monitoring(run_id, workspace_id)


async def chat(run_id: uuid.UUID, workspace_id: uuid.UUID, params: dict) -> None:
    """Answer the user's latest chat message and store the reply."""
    async with AsyncSessionLocal() as db:
        run = await db.get(models.Run, run_id)
        history = [(m.role, m.content) for m in await chat_service.list_messages(db, workspace_id)]
        context, offer_name = await chat_service.workspace_context(db, workspace_id)
    question, prior = history[-1][1], history[:-1][-chat_service.HISTORY_TURNS:]
    reply = await asyncio.to_thread(workspace_chat.answer, question, context, prior, offer_name)
    async with AsyncSessionLocal() as db:
        message = await chat_service.add_assistant_message(db, workspace_id, run.user_id, run_id, reply)
    await _finish(run_id, {"message_id": str(message.id)})


_DRAFT_WORKERS = 4


async def outreach_drafts(run_id: uuid.UUID, workspace_id: uuid.UUID, params: dict) -> None:
    """The GTM specialist drafts one message per account; the user reviews
    every one. A single-account request may name the recipient to write to."""
    channel, sender = params["channel"], params.get("sender") or ""
    override = params.get("recipient") or {}
    async with AsyncSessionLocal() as db:
        run = await db.get(models.Run, run_id)
        accounts = await outreach_service.accounts_for_drafting(
            db, workspace_id, [uuid.UUID(a) for a in params["account_ids"]],
        )
        context = await specialist_service.load(db, workspace_id)
        offer = await outreach_service.offer_context(db, workspace_id)
    targets = []
    for account in accounts:
        name, address = outreach_service.recipient_for(account, channel)
        if override and len(accounts) == 1:
            name, address = override.get("name") or name, override.get("address") or address
        targets.append((account, name, address))

    def write(target):
        account, name, _address = target
        brief = gtm_specialist.OutreachBrief(
            channel=channel, sender_name=sender, offer=offer, account=outreach_service.account_brief(account),
            contact_name=name, contact_title=outreach_service.contact_title(account, name),
            website=account.website, trigger_source=(account.trigger_event or {}).get("source"),
            team=context.team, research=context.research,
        )
        return gtm_specialist.write_first_touch(brief, context.offer_name or "our offer")

    def draft_all():
        with ContextThreadPoolExecutor(max_workers=_DRAFT_WORKERS) as pool:
            return list(pool.map(write, targets))
    drafts = await asyncio.to_thread(draft_all)

    async with AsyncSessionLocal() as db:
        db.add_all([
            models.OutreachMessage(
                workspace_id=workspace_id, user_id=run.user_id, account_id=account.id, run_id=run_id,
                channel=channel, recipient_name=name, recipient_company=account.name,
                recipient_address=address, subject=d.subject or None, body=d.body,
            )
            for (account, name, address), d in zip(targets, drafts)
        ])
        await db.commit()
    await _finish(run_id, {"drafted": len(drafts)})
    await signals.outreach_drafted(run_id, len(drafts))


_MONITOR_WORKERS = 4


async def monitor(run_id: uuid.UUID, workspace_id: uuid.UUID, _params: dict) -> None:
    """Re-check every tracked competitor; changes become feed signals. Social
    stats ride along when they are older than `socials_max_age_h`."""
    async with AsyncSessionLocal() as db:
        competitors = (await db.execute(
            select(models.Competitor).where(models.Competitor.workspace_id == workspace_id)
        )).scalars().all()
        offer = (await chat_service.workspace_context(db, workspace_id))[1]
    socials_cutoff = datetime.now(UTC) - timedelta(hours=settings.socials_max_age_h)
    targets = [
        (c.id, c.name, c.website, c.monitor_state, list(c.tracking_sources or []), c.social_profiles,
         c.socials_checked_at is None or c.socials_checked_at < socials_cutoff)
        for c in competitors
    ]

    def check_one(target):
        _id, name, website, previous, tracking, prev_socials, socials_due = target
        # Socials first: their new posts are part of what the check compares.
        try:
            socials = competitor_socials.refresh(name, website, tracking, prev_socials) if socials_due else None
        except Exception:  # noqa: BLE001 -- one rival failing must not stop the rest
            logger.exception("Refreshing socials for %s failed", name)
            socials = None
        try:
            checked = check_competitor.check(name, website, previous, offer, posts=_recent_posts(socials))
        except Exception:  # noqa: BLE001
            logger.exception("Monitoring %s failed", name)
            checked = None
        return checked, socials

    def check_all():
        with ContextThreadPoolExecutor(max_workers=_MONITOR_WORKERS) as pool:
            return list(pool.map(check_one, targets))
    results = await asyncio.to_thread(check_all)

    now = datetime.now(UTC)
    found, first_checked = [], []
    async with AsyncSessionLocal() as db:
        for (competitor_id, name, website, *_), (checked, socials) in zip(targets, results):
            competitor = await db.get(models.Competitor, competitor_id)
            if competitor is None:
                continue
            if checked is not None:
                state, changes = checked
                if not competitor.monitor_state:
                    first_checked.append(name)
                competitor.monitor_state = state
                competitor.last_checked_at = now
                found += [(name, website, change) for change in changes if change.importance != "low"]
            if socials is not None:
                profiles, discovered = socials
                competitor.social_profiles = profiles
                competitor.socials_checked_at = now
                if discovered:  # read off their own site, so as sure as a handle gets
                    competitor.tracking_sources = [*competitor.tracking_sources, *(
                        {"kind": kind, "value": url, "confidence": "high"} for kind, url in discovered.items()
                    )]
        await db.commit()
    await _finish(run_id, {
        "checked": sum(c is not None for c, _ in results),
        "socials": sum(s is not None for _, s in results),
        "changes": len(found),
    })
    if first_checked:
        await signals.monitoring_started(run_id, first_checked)
    await signals.competitor_changes(run_id, found)


_POSTS_PER_PLATFORM = 3


def _recent_posts(socials: tuple[dict, dict] | None) -> list[dict]:
    """The newest posts from freshly scraped profiles, tagged by platform."""
    if not socials:
        return []
    return [
        {**post, "platform": platform}
        for platform, profile in socials[0].items()
        for post in (profile.get("recent_posts") or [])[:_POSTS_PER_PLATFORM]
    ]


EXECUTORS: dict[str, Callable[[uuid.UUID, uuid.UUID, dict], Awaitable[None]]] = {
    "competitors": competitors,
    "accounts": accounts,
    "competitor_research": competitor_research,
    "chat": chat,
    "outreach_drafts": outreach_drafts,
    "monitor": monitor,
}
