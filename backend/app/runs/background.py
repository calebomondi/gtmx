"""Background run kinds: no questions, one segment from start to finish. The
runner does the agent work and the database writes; this records the outcome
on the run and publishes it, so all kinds share one lifecycle (manager)."""

import asyncio
import uuid
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime, timedelta

from sqlalchemy import select

from agents.concurrency import ContextThreadPoolExecutor
from agents.helpers import offer_label
from agents.pipelines.accounts import competitor_clients
from agents.pipelines.accounts import fit as account_fit
from agents.pipelines.chat import workspace_chat
from agents.pipelines.monitor import check_competitor
from agents.pipelines.monitor import socials as competitor_socials
from agents.pipelines.outreach import gtm_replies, gtm_specialist
from agents.lace.store import JobRefused
from agents.schemas.monitor import CompetitorChange
from backend.app.account_runner import run_account_discovery_for_workspace
from backend.app.competitor_runner import research_competitor_site, run_competitor_discovery
from backend.app.database import models
from backend.app.database.connect import AsyncSessionLocal
from backend.app.runs import events, signals
from backend.app.services import accounts as account_service
from backend.app.services import calendar as calendar_service
from backend.app.services import chat as chat_service
from backend.app.services import competitors as competitor_service
from backend.app.services import outreach as outreach_service
from backend.app.services import specialists as specialist_service
from backend.app.services.errors import RateLimitedError
from backend.app.services.inbox import SyncResult
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
    with events.reporting_steps(run_id):
        outcome = await run_competitor_discovery(workspace_id=workspace_id, run_id=run_id)
    await _finish(run_id, outcome)
    await signals.competitors_found(run_id)
    await _start_monitoring(run_id, workspace_id)


async def accounts(run_id: uuid.UUID, workspace_id: uuid.UUID, _params: dict) -> None:
    with events.reporting_steps(run_id):
        outcome = await run_account_discovery_for_workspace(workspace_id=workspace_id, run_id=run_id)
        outcome["suggested"] = await _suggest_competitor_clients(workspace_id, run_id)
        # The feed's opportunity cards lead with the fit, so assess it first.
        outcome["assessed"] = await _assess_fits(workspace_id)
    await _finish(run_id, outcome)
    await signals.accounts_found(run_id)
    await signals.competitor_clients_found(run_id)


_CLIENT_COMPETITORS = 8  # tracked competitors whose clients one run looks for


def _in_geos(country: str | None, geos: list[str], competitor_local: bool) -> bool:
    """A client counts when it is in the ICP's countries, or, with no country
    stated, when its competitor works there."""
    if not geos:
        return True
    if not country:
        return competitor_local
    return any(g.lower() in country.lower() or country.lower() in g.lower() for g in geos)


async def _client_reach(db, workspace_id: uuid.UUID) -> list[str] | None:
    """The ICP's countries, for placing a competitor's clients; None for a
    consumer offer, which has no client roster to read."""
    insights = await db.scalar(
        select(models.ProductProfile.insights).where(models.ProductProfile.workspace_id == workspace_id)
    ) or {}
    icp = insights.get("icp") or {}
    if (icp.get("buyer_type") or "b2b").lower() == "b2c":
        return None
    return [g for g in icp.get("geo") or [] if isinstance(g, str)]


def _works_in(competitor: models.Competitor, geos: list[str]) -> bool:
    where = " ".join(filter(None, [competitor.headquarters, competitor.geography_scope])).lower()
    return any(g.lower() in where for g in geos)


async def _suggest_competitor_clients(workspace_id: uuid.UUID, run_id: uuid.UUID) -> int:
    """Suggest the named clients of tracked competitors as accounts: they
    already buy what the offer sells. Consumer offers have no client roster
    to read, so they are skipped."""
    async with AsyncSessionLocal() as db:
        geos = await _client_reach(db, workspace_id)
        competitors = (await db.execute(
            select(models.Competitor).where(models.Competitor.workspace_id == workspace_id)
            .order_by(models.Competitor.first_seen_at.desc()).limit(_CLIENT_COMPETITORS)
        )).scalars().all()
        targets = [(c.id, c.name, c.website, list(c.notable_customers or [])) for c in competitors if c.website]
    if geos is None or not targets:
        return 0

    def find(target):
        _id, name, website, known = target
        try:
            return competitor_clients.find(name, website, known)
        except Exception:  # noqa: BLE001 -- one competitor failing must not stop the rest
            logger.exception("Finding the clients of %s failed", name)
            return []

    def find_all():
        with ContextThreadPoolExecutor(max_workers=_FIT_WORKERS) as pool:
            return list(pool.map(find, targets))
    found = await asyncio.to_thread(find_all)

    added = 0
    async with AsyncSessionLocal() as db:
        for (competitor_id, *_), clients in zip(targets, found):
            competitor = await db.get(models.Competitor, competitor_id)
            if competitor is None:
                continue
            kept = [c.model_dump() for c in clients if _in_geos(c.country, geos, _works_in(competitor, geos))]
            if kept:
                added += await account_service.suggest_clients(db, workspace_id, run_id, competitor, kept)
    return added


async def _suggest_from_client_moves(workspace_id: uuid.UUID, run_id: uuid.UUID,
                                     moves: list[tuple[uuid.UUID, CompetitorChange]]) -> int:
    """A client a competitor just won, showcased or upset is a prospect too:
    suggest it, then make the case for it."""
    if not moves:
        return 0
    added = 0
    async with AsyncSessionLocal() as db:
        geos = await _client_reach(db, workspace_id)
        if geos is None:
            return 0
        for competitor_id, change in moves:
            competitor = await db.get(models.Competitor, competitor_id)
            if competitor is None or not _in_geos(change.client_country or None, geos, _works_in(competitor, geos)):
                continue
            added += await account_service.suggest_clients(db, workspace_id, run_id, competitor, [{
                "name": change.client_name, "country": change.client_country or None, "relationship": "announced_deal",
                "evidence": change.summary, "source_url": change.source_url or competitor.website,
            }])
    if added:
        await _assess_fits(workspace_id)
    return added


_FIT_WORKERS = 4


async def _assess_fits(workspace_id: uuid.UUID) -> int:
    """Make the case for each account not yet assessed: its need, the
    capability that answers it, the payoff and the angle. Returns how many
    were assessed; one account failing leaves its fit empty for next time."""
    async with AsyncSessionLocal() as db:
        pending = [(a.id, outreach_service.account_brief(a)) for a in await account_service.without_fit(db, workspace_id)]
        if not pending:
            return 0
        context = await specialist_service.load(db, workspace_id)
        offer = await outreach_service.offer_context(db, workspace_id)
    seller = offer_label(context.company_name, context.offer_name)

    def assess(item):
        account_id, brief = item
        try:
            return account_id, account_fit.assess(offer, brief, seller).model_dump()
        except Exception:  # noqa: BLE001 -- one account failing must not stop the rest
            logger.exception("Assessing fit for account %s failed", account_id)
            return account_id, None

    def assess_all():
        with ContextThreadPoolExecutor(max_workers=_FIT_WORKERS) as pool:
            return list(pool.map(assess, pending))
    fits = {account_id: fit for account_id, fit in await asyncio.to_thread(assess_all) if fit}
    async with AsyncSessionLocal() as db:
        await account_service.save_fits(db, fits)
    return len(fits)


async def account_fits(run_id: uuid.UUID, workspace_id: uuid.UUID, _params: dict) -> None:
    """Assess fit for accounts found before fit existed (or whose assessment failed)."""
    await _finish(run_id, {"assessed": await _assess_fits(workspace_id)})


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
        specialists = await specialist_service.load(db, workspace_id)
    context = workspace_chat.ChatContext(
        offer_name=specialists.offer_name, offer=specialists.offer, team=specialists.team, research=specialists.research,
    )
    question, prior = history[-1][1], history[:-1][-chat_service.HISTORY_TURNS:]
    reply = await asyncio.to_thread(workspace_chat.reply, question, prior, context)
    async with AsyncSessionLocal() as db:
        message = await chat_service.add_assistant_message(
            db, workspace_id, run.user_id, run_id, reply.content, reply.domain, reply.suggestions,
        )
    await _finish(run_id, {"message_id": str(message.id), "specialist": reply.domain})


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
            account_type=account.account_type or "company", seller=context.company_name,
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


_MEETING_MINUTES = 30


async def outreach_reply(run_id: uuid.UUID, workspace_id: uuid.UUID, params: dict) -> None:
    """The GTM specialist reads a reply and drafts the answer, consulting the
    team and offering free calendar slots. The user approves every send, and
    a meeting reaches Calendar only from the user's click."""
    async with AsyncSessionLocal() as db:
        reply = await db.get(models.OutreachMessage, uuid.UUID(params["message_id"]))
        conversation = await outreach_service.thread(db, reply)
        account = await db.get(models.Account, reply.account_id) if reply.account_id else None
        context = await specialist_service.load(db, workspace_id)
        offer = await outreach_service.offer_context(db, workspace_id)
        slots, timezone = await calendar_service.free_slots(db, reply.user_id)
    brief = gtm_replies.ReplyBrief(
        sender_name=params.get("sender") or "Me", contact_name=reply.recipient_name, offer=offer,
        account=outreach_service.account_brief(account) if account else reply.recipient_company,
        thread=[("them" if m.direction == "inbound" else "us", m.body) for m in conversation
                if m.status not in ("draft", "failed")],
        team=context.team, research=context.research, free_slots=slots, timezone=timezone,
    )
    result = await asyncio.to_thread(gtm_replies.draft_reply, brief)

    async with AsyncSessionLocal() as db:
        reply = await db.get(models.OutreachMessage, reply.id)
        reply.intent = result.analysis.intent
        await db.commit()
        if result.analysis.intent == "unsubscribe":
            await outreach_service.mark_do_not_contact(db, reply.account_id)
        draft = None
        if result.draft is not None:
            draft = await outreach_service.add_reply_draft(
                db, reply, result.draft.body, _meeting(result.analysis.agreed_time, timezone, reply, context.offer_name),
                run_id,
            )
    await _finish(run_id, {"intent": result.analysis.intent, "drafted": draft is not None})
    if draft is not None:
        await signals.reply_drafted(run_id, reply.recipient_name or reply.recipient_address or "", result.analysis.intent)


def _meeting(agreed_time: str, timezone: str, reply: models.OutreachMessage, offer_name: str) -> dict | None:
    """The meeting to offer adding to Calendar, when the contact agreed a time."""
    try:
        start = datetime.fromisoformat(agreed_time) if agreed_time else None
    except ValueError:
        return None
    if start is None:
        return None
    end = start + timedelta(minutes=_MEETING_MINUTES)
    return {
        "start": start.isoformat(), "end": end.isoformat(), "timezone": timezone or "UTC",
        "title": f"{offer_name or 'Intro'} x {reply.recipient_company}".strip(), "attendee": reply.recipient_address,
    }


async def after_inbox_sync(result) -> None:
    """Workspace replies and bounces: feed signals, and a reply draft for each
    new reply. A Lace's replies: one reading run per Lace, whose update tells
    the founder."""
    from backend.app.runs import manager  # manager imports this module

    lace_replies = [m for m in result.replies if isinstance(m, models.LaceOutreach)]
    workspace = SyncResult(replies=[m for m in result.replies if isinstance(m, models.OutreachMessage)],
                           bounced=[m for m in result.bounced if isinstance(m, models.OutreachMessage)])
    await signals.inbox_synced(workspace)
    for lace_id, user_id in {(m.lace_id, m.user_id) for m in lace_replies}:
        try:
            await manager.start_lace_job("lace_reply", user_id, lace_id, {})
        except JobRefused as exc:
            logger.info("Reading replies for Lace %s waits: %s", lace_id, exc)

    for reply in workspace.replies:
        try:
            await manager.start_background(
                "outreach_reply", reply.user_id, reply.workspace_id,
                params={"message_id": str(reply.id), "sender": await outreach_service.sender_for_user(reply.user_id)},
            )
        except RateLimitedError:
            logger.info("Reply drafting for user %s waits: daily cap reached", reply.user_id)


_MONITOR_WORKERS = 4


async def monitor(run_id: uuid.UUID, workspace_id: uuid.UUID, _params: dict) -> None:
    """Re-check every tracked competitor; changes become feed signals. Social
    stats ride along when they are older than `socials_max_age_h`."""
    async with AsyncSessionLocal() as db:
        competitors = (await db.execute(
            select(models.Competitor).where(models.Competitor.workspace_id == workspace_id)
        )).scalars().all()
        context = await specialist_service.load(db, workspace_id)
    offer, offer_detail = context.offer_name, context.offer
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
            checked = check_competitor.check(name, website, previous, offer, posts=_recent_posts(socials),
                                             offer_detail=offer_detail)
        except Exception:  # noqa: BLE001
            logger.exception("Monitoring %s failed", name)
            checked = None
        return checked, socials

    def check_all():
        with ContextThreadPoolExecutor(max_workers=_MONITOR_WORKERS) as pool:
            return list(pool.map(check_one, targets))
    results = await asyncio.to_thread(check_all)

    now = datetime.now(UTC)
    found, first_checked, client_moves = [], [], []
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
                material = [change for change in changes if change.importance != "low"]
                found += [(name, website, change) for change in material]
                client_moves += [(competitor_id, c) for c in material if c.kind == "client" and c.client_name.strip()]
            if socials is not None:
                profiles, discovered = socials
                competitor.social_profiles = profiles
                competitor.socials_checked_at = now
                if discovered:  # read off their own site, so as sure as a handle gets
                    competitor.tracking_sources = [*competitor.tracking_sources, *(
                        {"kind": kind, "value": url, "confidence": "high"} for kind, url in discovered.items()
                    )]
        await db.commit()
    suggested = await _suggest_from_client_moves(workspace_id, run_id, client_moves)
    await _finish(run_id, {
        "checked": sum(c is not None for c, _ in results),
        "socials": sum(s is not None for _, s in results),
        "changes": len(found),
        "suggested": suggested,
    })
    if first_checked:
        await signals.monitoring_started(run_id, first_checked)
    await signals.competitor_changes(run_id, found)
    await signals.competitor_clients_found(run_id)


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
    "outreach_reply": outreach_reply,
    "monitor": monitor,
    "account_fit": account_fits,
}
