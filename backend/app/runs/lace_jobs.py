"""Lace background jobs: work too long for one turn, started from the Lace's
tools (or the scheduler) through the run manager.

Each job saves what it found and queues one update (lace_events) in the same
transaction; the run manager then wakes the Lace to tell the founder. A job
that fails for a reason the founder can fix (JobBlocked) says so as is.
"""

import asyncio
import uuid
from datetime import UTC, datetime

from agents.lace import icp as lace_icp
from agents.lace.accounts import find_accounts
from agents.lace.graph import BRIEF_FACTS
from agents.lace.competitors import change_fact, find_competitors, material, offer_for_monitor
from agents.lace.contacts import complete_contacts, contact_status
from agents.lace.accounts import record_brief
from agents.lace.opportunities import find_opportunities
from agents.lace.outreach import Recipient, draft_first_touch, recipient_for, research_by_domain
from agents.lace.prompts import render_brief, render_icp
from agents.pipelines.outreach import gtm_replies
from agents.lace.store import JobBlocked
from agents.pipelines.monitor import check_competitor
from agents.schemas.accounts import AccountRecord
from agents.schemas.opportunities import OPPORTUNITY_KINDS
from backend.app.database import models
from backend.app.database.connect import AsyncSessionLocal
from backend.app.database.lace_models import LaceAccount, LaceOutreach
from backend.app.runs import events
from backend.app.runs.errors import user_facing_error

from backend.app.services import lace_accounts, lace_activity, lace_competitors, lace_contacts, lace_events, lace_opportunities, lace_outreach
from backend.app.services.lace_activity import names, plural
from backend.app.services.lace_contacts import contact_key
from backend.app.services import calendar as calendar_service
from backend.app.services import outreach as outreach_service
from backend.app.services.competitors import domain_key
from backend.app.services.lace_store import DbLaceStore
from backend.app.services.runs import set_run_fields
from config import settings
from utils.log import logger
from utils.progress import report

# Replies read per round, and rounds per run (a run picks up replies that
# arrive while it works).
REPLIES_BATCH = 10
MAX_REPLY_ROUNDS = 3

# Accounts one drafting run writes to, how many at once, and the competitors
# the drafts may compare against.
DRAFTS_BATCH = 5
DRAFTS_CONCURRENCY = 3
COMPETITORS_FOR_DRAFTS = 8

# Accounts one contact search covers, and how many at once.
CONTACTS_BATCH = 20
CONTACTS_CONCURRENCY = 4

# Competitors one monitoring run checks, and how many at once.
MONITOR_BATCH = 15
MONITOR_CONCURRENCY = 4

async def report_failure(lace_id: uuid.UUID, what: str, exc: Exception) -> None:
    """Tell the Lace and the founder's Feed that a search failed, and why."""
    reason = _failure(exc)
    async with AsyncSessionLocal() as db, db.begin():
        await lace_events.add(db, lace_id, f"The {what} failed: {reason}")
        await lace_activity.add(db, lace_id, "job_failed", f"The {what} failed", reason)


def _failure(exc: Exception) -> str:
    """Why a job failed, as the Lace will tell it: a reason the founder can fix
    as is, anything else in general terms."""
    return str(exc) if isinstance(exc, JobBlocked) else user_facing_error(exc)


async def competitors_job(run_id: uuid.UUID, lace_id: uuid.UUID, params: dict) -> None:
    """Hunt for the Lace's competitors, save them, and queue an update telling
    the Lace what came of it, in the same transaction as the results. A failed
    hunt queues an update too, so the founder hears either way."""
    store = DbLaceStore(AsyncSessionLocal, lace_id)
    profile, facts = await asyncio.gather(store.profile(), store.facts(None, BRIEF_FACTS))
    try:
        with events.reporting_steps(run_id):
            found = await asyncio.to_thread(find_competitors, profile, facts, params.get("focus"))
    except Exception as exc:
        await report_failure(lace_id, "competitor search", exc)
        raise
    async with AsyncSessionLocal() as db, db.begin():
        new, refreshed = await lace_competitors.upsert_found(db, lace_id, run_id, found)
        await lace_events.add(db, lace_id, competitors_update(found, new, refreshed))
        if new:
            await lace_activity.add(db, lace_id, "competitors_found", f"Found {plural(new, 'new competitor')}",
                                    names([p.name for p in found]))
    await set_run_fields(models.Run, run_id, status="completed", finished_at=datetime.now(UTC),
                         progress={"found": len(found), "new": new, "refreshed": refreshed})
    await events.publish(run_id, "complete", {"found": len(found)})


async def monitor_job(run_id: uuid.UUID, lace_id: uuid.UUID, params: dict) -> None:
    """Check the tracked competitors for moves since their last check. Each
    firm's baseline is saved as it is checked. Material changes become sourced
    facts and one queued update; when nothing material changed, the founder
    is not told anything."""
    store = DbLaceStore(AsyncSessionLocal, lace_id)
    profile, facts = await asyncio.gather(store.profile(), store.facts(None, BRIEF_FACTS))
    our_offer, offer_detail = offer_for_monitor(profile, facts)
    async with AsyncSessionLocal() as db:
        due = [(c.id, c.name, c.website, c.monitor_state)
               for c in await lace_competitors.due_for_check(db, lace_id, MONITOR_BATCH)]
    slots = asyncio.Semaphore(MONITOR_CONCURRENCY)

    async def check_one(competitor_id, name, website, previous) -> tuple[str, list]:
        async with slots:
            state, changes = await asyncio.to_thread(check_competitor.check, name, website, previous, our_offer,
                                                     None, offer_detail)
        moves = material(changes)
        async with AsyncSessionLocal() as db, db.begin():
            await lace_competitors.save_check(db, competitor_id, state)
            await lace_competitors.add_moves(db, lace_id, competitor_id, run_id, moves)
        return name, moves

    with events.reporting_steps(run_id):
        report(f"Checking {len(due)} competitors for changes")
        results = await asyncio.gather(*(check_one(*row) for row in due))

    moves = [(name, change) for name, changes in results for change in changes]
    for name, change in moves:
        fact = change_fact(name, change)
        if fact is not None:
            await store.record_fact(fact)
    if moves:
        async with AsyncSessionLocal() as db, db.begin():
            await lace_events.add(db, lace_id, monitor_update(moves))
            await lace_activity.add(db, lace_id, "competitor_moves", f"{plural(len(moves), 'competitor move')} that matter",
                                    "\n".join(f"{name}: {c.title}" for name, c in moves))
    await set_run_fields(models.Run, run_id, status="completed", finished_at=datetime.now(UTC),
                         progress={"checked": len(due), "changes": len(moves)})
    await events.publish(run_id, "complete", {"checked": len(due), "changes": len(moves)})


# Facts and competitors an ideal customer profile is drawn from.
ICP_FACTS = 150
ICP_COMPETITORS = 50


async def _define_icp(store: DbLaceStore, guidance: str | None):
    """Work out the ideal customer profile and save it. A long structured
    call (minutes on a large model), so it only ever runs in a job."""
    report("Working out who your ideal customers are")
    profile, facts, rivals = await asyncio.gather(
        store.profile(), store.facts(None, ICP_FACTS), store.competitors(ICP_COMPETITORS))
    icp = await asyncio.to_thread(lace_icp.define_icp, profile, facts, rivals, guidance)
    await store.save_icp(icp)
    return icp


async def icp_job(run_id: uuid.UUID, lace_id: uuid.UUID, params: dict) -> None:
    """Work out (or rework) the ideal customer profile and queue an update
    with its gist."""
    store = DbLaceStore(AsyncSessionLocal, lace_id)
    try:
        with events.reporting_steps(run_id):
            icp = await _define_icp(store, params.get("guidance"))
    except Exception as exc:
        await report_failure(lace_id, "work out the ideal customer profile", exc)
        raise
    async with AsyncSessionLocal() as db, db.begin():
        await lace_events.add(db, lace_id, "The ideal customer profile is saved. Its gist:\n" + render_icp(icp)
                              + "\nTell the founder who it says to sell to, briefly, and offer to look for those customers.")
    await set_run_fields(models.Run, run_id, status="completed", finished_at=datetime.now(UTC))
    await events.publish(run_id, "complete", {})


async def accounts_job(run_id: uuid.UUID, lace_id: uuid.UUID, params: dict) -> None:
    """Search for target accounts on the Lace's ICP (working one out first
    when there is none), save them with their fit cases, and queue an update,
    in one transaction. The startup's own site and every competitor on file
    (tracked or dismissed) are never targets. A failed search queues an
    update too."""
    store = DbLaceStore(AsyncSessionLocal, lace_id)
    profile, facts, icp = await asyncio.gather(store.profile(), store.facts(None, BRIEF_FACTS), store.icp())
    try:
        async with AsyncSessionLocal() as db:
            exclude = [domain_key(profile.website), *await lace_competitors.all_domains(db, lace_id)]
        with events.reporting_steps(run_id):
            if icp is None:
                icp = await _define_icp(store, None)
            found = await asyncio.to_thread(find_accounts, profile, facts, icp, exclude, params.get("country"))
    except Exception as exc:
        await report_failure(lace_id, "search for target accounts", exc)
        raise
    async with AsyncSessionLocal() as db, db.begin():
        new, refreshed = await lace_accounts.upsert_found(db, lace_id, run_id, found)
        await lace_events.add(db, lace_id, accounts_update(found, new, refreshed, params.get("country")))
        if new:
            await lace_activity.add(db, lace_id, "accounts_found", f"Found {plural(new, 'new target account')}",
                                    names([record.name for record, _ in found]))
    await set_run_fields(models.Run, run_id, status="completed", finished_at=datetime.now(UTC),
                         progress={"found": len(found), "new": new, "refreshed": refreshed})
    await events.publish(run_id, "complete", {"found": len(found)})


async def contacts_job(run_id: uuid.UUID, lace_id: uuid.UUID, params: dict) -> None:
    """Find who to contact at target accounts, saving each account as it is
    done, and queue one update saying who can be reached and who cannot."""
    icp = await DbLaceStore(AsyncSessionLocal, lace_id).icp()
    titles = list(icp.buyer_titles) if icp else []
    ids = [uuid.UUID(i) for i in params.get("account_ids") or [] if _is_uuid(i)]
    async with AsyncSessionLocal() as db:
        due = [(a.id, AccountRecord.model_validate(a.record))
               for a in await lace_accounts.due_for_contacts(db, lace_id, ids or None, CONTACTS_BATCH)]
    slots = asyncio.Semaphore(CONTACTS_CONCURRENCY)

    async def search(account_id, record):
        async with slots:
            done = await asyncio.to_thread(complete_contacts, record, titles, settings)
        async with AsyncSessionLocal() as db, db.begin():
            await lace_accounts.save_contacts(db, account_id, done)
        return done

    with events.reporting_steps(run_id):
        report(f"Looking for contacts at {len(due)} accounts")
        results = await asyncio.gather(*(search(*row) for row in due))
    reachable = [r.name for r in results if contact_status(r) == "person"]
    async with AsyncSessionLocal() as db, db.begin():
        await lace_events.add(db, lace_id, contacts_update(results))
        if reachable:
            await lace_activity.add(db, lace_id, "contacts_found",
                                    f"Found people to contact at {plural(len(reachable), 'account')}", names(reachable))
    counts = {s: sum(contact_status(r) == s for r in results) for s in ("person", "organisation", "none")}
    await set_run_fields(models.Run, run_id, status="completed", finished_at=datetime.now(UTC),
                         progress={"searched": len(results), **counts})
    await events.publish(run_id, "complete", {"searched": len(results)})


def _is_uuid(value: str) -> bool:
    try:
        uuid.UUID(value)
    except ValueError:
        return False
    return True


async def drafts_job(run_id: uuid.UUID, lace_id: uuid.UUID, params: dict) -> None:
    """Draft a first message to each account through v1's GTM pipeline, save
    the drafts for the founder to review, and queue an update. Nothing is
    sent: sending is the founder's own action."""
    store = DbLaceStore(AsyncSessionLocal, lace_id)
    profile, facts, rivals = await asyncio.gather(
        store.profile(), store.facts(None, BRIEF_FACTS), store.competitors(COMPETITORS_FOR_DRAFTS))
    ids = [uuid.UUID(i) for i in params.get("account_ids") or [] if _is_uuid(i)]
    async with AsyncSessionLocal() as db:
        run = await db.get(models.Run, run_id)
        user_id = run.user_id
        accounts = [(a.id, a.name, AccountRecord.model_validate(a.record))
                    for a in await lace_outreach.accounts_to_draft(db, lace_id, ids or None, DRAFTS_BATCH)]
        cleared = await lace_contacts.approved_keys(db, [account_id for account_id, _, _ in accounts])
    sender = await outreach_service.sender_for_user(user_id)
    person, note = params.get("person"), params.get("note")
    if person:
        # The founder asked for this one person, on this channel (and approved
        # them in asking).
        awaiting: list[str] = []
        targets = [(account_id, name, record,
                    Recipient(person["channel"], person.get("name"), person.get("title"), person["address"]))
                   for account_id, name, record in accounts]
    else:
        # Only people the founder approved are written to. An account whose
        # people all wait for approval waits too, rather than falling back to
        # its pages.
        awaiting = [name for account_id, name, record in accounts
                    if record.key_contacts and not cleared.get(account_id)]
        targets = [(account_id, name, record, recipient_for(approved_only(record, cleared.get(account_id, set()))))
                   for account_id, name, record in accounts if name not in awaiting]
    unreachable = [name for _, name, _, recipient in targets if recipient is None]
    failed: list[str] = []
    slots = asyncio.Semaphore(DRAFTS_CONCURRENCY)

    async def draft(account_id, name, record, recipient) -> LaceOutreach | None:
        async with slots:
            try:
                written = await asyncio.to_thread(draft_first_touch, profile, facts, rivals, record, recipient, sender,
                                                  note=note)
            except Exception:  # noqa: BLE001 -- one account failing must not lose the other drafts
                logger.exception("Drafting to %s failed", name)
                failed.append(name)
                return None
        # The id is set here, not at flush, so the update can name it.
        return LaceOutreach(id=uuid.uuid4(), lace_id=lace_id, user_id=user_id, account_id=account_id, run_id=run_id,
                            channel=recipient.channel, recipient_name=recipient.name, recipient_company=name[:255],
                            recipient_address=recipient.address, subject=written.subject or None, body=written.body)

    with events.reporting_steps(run_id):
        report(f"Drafting messages to {len(targets) - len(unreachable)} accounts")
        drafts = [d for d in await asyncio.gather(*(draft(*t) for t in targets if t[3] is not None)) if d]
    async with AsyncSessionLocal() as db, db.begin():
        db.add_all(drafts)
        await lace_events.add(db, lace_id, drafts_update(drafts, unreachable, failed, awaiting))
        if drafts:
            await lace_activity.add(db, lace_id, "drafts_ready", f"{plural(len(drafts), 'message')} drafted for you to send",
                                    names([d.recipient_company for d in drafts]))
    await set_run_fields(models.Run, run_id, status="completed", finished_at=datetime.now(UTC),
                         progress={"drafted": len(drafts), "unreachable": len(unreachable)})
    await events.publish(run_id, "complete", {"drafted": len(drafts)})


def approved_only(record: AccountRecord, keys: set[str]) -> AccountRecord:
    """The record with only the people the founder approved."""
    return record.model_copy(update={"key_contacts": [c for c in record.key_contacts if contact_key(c) in keys]})


def drafts_update(drafts: list[LaceOutreach], unreachable: list[str], failed: list[str],
                  awaiting: list[str]) -> str:
    if not drafts and not unreachable and not failed and not awaiting:
        return "There was no account to draft for: every target with someone to reach already has a message."
    lines = [f"{d.recipient_company} [draft {d.id}]: to {d.recipient_name or d.recipient_address} by {d.channel}"
             + (f', subject "{d.subject}"' if d.subject else "") for d in drafts]
    if unreachable:
        lines.append("Not drafted, nobody to reach yet (use find_contacts): " + ", ".join(unreachable))
    if failed:
        lines.append("Drafting failed for (try again later): " + ", ".join(failed))
    if awaiting:
        lines.append("Not drafted, their people wait for the founder to approve them (in Contacts, or on the "
                     "account's card): " + ", ".join(awaiting))
    head = ("Drafted first messages; they wait in Outreach for the founder to review, edit and send:" if drafts
            else "No message was drafted:")
    return head + "\n" + "\n".join(lines)


def contacts_update(results: list[AccountRecord]) -> str:
    if not results:
        return "The contact search had no accounts to look at: every target account was already searched."
    lines = []
    for r in results:
        status = contact_status(r)
        people = [c for c in r.key_contacts if c.name and (c.email or c.linkedin)]
        if status == "person":
            who = "; ".join(f"{c.name}{f' ({c.title})' if c.title else ''}: {c.email or c.linkedin}" for c in people[:2])
            lines.append(f"{r.name}: {who}")
        elif status == "organisation":
            reach = ", ".join([*(c.email for c in r.key_contacts if c.email), *sorted(r.socials)]) or "its own pages"
            lines.append(f"{r.name}: no named person found; reachable through {reach}")
        else:
            lines.append(f"{r.name}: could not find anyone to contact, nor any page of its own")
    return ("The contact search finished:\n" + "\n".join(lines)
            + "\nDrafts go only to people the founder approves: show these accounts so they can approve them.")


def accounts_update(found: list, new: int, refreshed: int, country: str | None) -> str:
    where = f" in {country}" if country else ""
    if not found:
        return (f"The search for target accounts{where} finished without finding an account with a current, "
                "verifiable reason to buy.")
    lines = []
    for record, fit in found:
        line = f"{record.name} ({record.website or record.account_type})"
        if record.trigger_event:
            line += f": {record.trigger_event.event}"
        if fit:
            line += f". Need: {fit.need} [{fit.strength} fit]"
        lines.append(line)
    return (f"The search for target accounts{where} finished: {len(found)} accounts ({new} new, {refreshed} "
            "already on file), each with a current trigger:\n" + "\n".join(lines)
            + "\nNew ones wait for the founder to save or dismiss: show them (ids from list_suggestions); once saved, find_contacts finds who to reach.")


def monitor_update(moves: list) -> str:
    lines = []
    for name, c in moves:
        line = f"{name} [{c.kind}, {c.importance}]: {c.title}. {c.summary}"
        if c.implication:
            line += f" What it means for us: {c.implication}"
        if c.counter_move:
            line += f" Suggested move: {c.counter_move}"
        if c.source_url:
            line += f" (source: {c.source_url})"
        lines.append(line)
    return "Competitor monitoring found changes that matter:\n" + "\n".join(lines)


def competitors_update(found: list, new: int, refreshed: int) -> str:
    if not found:
        return ("The competitor search finished without finding a company that passed the checks "
                "(a real website, competing for the same buyers).")
    names = ", ".join(f"{p.name} ({p.website})" for p in found)
    return (f"The competitor search finished: {len(found)} competitors ({new} new, {refreshed} already tracked): "
            f"{names}. New ones wait for the founder to save or dismiss: show them (ids from list_suggestions).")


async def reply_job(run_id: uuid.UUID, lace_id: uuid.UUID, params: dict) -> None:
    """Read each reply that came in and draft the answer through v1's reply
    pipeline (classify, consult, write, check), offering free calendar slots.
    The answer waits as a draft in the same thread; nothing is sent. Loops
    until no reply is left unread, so ones arriving mid-run are not missed."""
    store = DbLaceStore(AsyncSessionLocal, lace_id)
    profile, facts, rivals = await asyncio.gather(
        store.profile(), store.facts(None, BRIEF_FACTS), store.competitors(COMPETITORS_FOR_DRAFTS))
    offer = render_brief([f for f in facts if f.topic in ("offer", "pricing", "customers", "positioning")])
    research = research_by_domain(facts, rivals)
    handled: list[str] = []
    for _ in range(MAX_REPLY_ROUNDS):
        # Short sessions around the reads and each write; none is held open
        # across a model call.
        async with AsyncSessionLocal() as db:
            pending = await lace_outreach.unhandled_replies(db, lace_id, REPLIES_BATCH)
            if not pending:
                break
            user_id = pending[0].user_id
            slots, timezone = await calendar_service.free_slots(db, await db.get(models.Lace, lace_id))
            work = []
            for reply in pending:
                conversation = await lace_outreach.thread(db, reply)
                account = await db.get(LaceAccount, reply.account_id) if reply.account_id else None
                # A DM to the founder's own account may come from someone who is
                # no target account yet.
                who = reply.recipient_company or f"{reply.recipient_name or 'Someone'} on {reply.channel}"
                work.append((reply.id, reply.recipient_name, conversation, account.record if account else None, who))
        sender = await outreach_service.sender_for_user(user_id)
        for reply_id, contact, conversation, record, company in work:
            brief = gtm_replies.ReplyBrief(
                sender_name=sender, contact_name=contact, offer=offer,
                account=record_brief(AccountRecord.model_validate(record)) if record else company,
                thread=[("them" if m.direction == "inbound" else "us", m.body) for m in conversation
                        if m.status not in ("draft", "failed")],
                research=research, free_slots=slots, timezone=timezone,
            )
            result = await asyncio.to_thread(gtm_replies.draft_reply, brief)
            async with AsyncSessionLocal() as db, db.begin():
                reply = await db.get(LaceOutreach, reply_id)
                draft = await lace_outreach.record_reading(
                    db, reply, result.analysis.intent, result.draft.body if result.draft else None, run_id)
                handled.append(reply_update_line(reply, result.analysis, draft is not None))
                await lace_activity.add(db, lace_id, "reply_received", f"{company} replied ({result.analysis.intent})",
                                        result.analysis.summary, ref=("outreach", reply.id))
    if handled:
        async with AsyncSessionLocal() as db, db.begin():
            await lace_events.add(db, lace_id, "Messages to the founder came in:\n" + "\n".join(handled))
    await set_run_fields(models.Run, run_id, status="completed", finished_at=datetime.now(UTC),
                         progress={"replies": len(handled)})
    await events.publish(run_id, "complete", {"replies": len(handled)})


def reply_update_line(reply: LaceOutreach, analysis, drafted: bool) -> str:
    where = f"at {reply.recipient_company}" if reply.recipient_company else f"by {reply.channel} DM"
    who = f"{reply.recipient_name or reply.recipient_address} {where}"
    line = f"{who} replied ({analysis.intent}): {analysis.summary}"
    if analysis.intent == "unsubscribe":
        return line + " They asked not to be contacted; nothing more will be drafted or sent to them."
    if drafted:
        return line + " An answer is drafted in Outreach for the founder to review and send."
    return line + " No answer is needed."


async def opportunities_job(run_id: uuid.UUID, lace_id: uuid.UUID, params: dict) -> None:
    """Search for opportunities, save the sourced, open ones, and queue an
    update. A scheduled search that found nothing new says nothing."""
    store = DbLaceStore(AsyncSessionLocal, lace_id)
    profile, facts, icp = await asyncio.gather(store.profile(), store.facts(None, BRIEF_FACTS), store.icp())
    kinds = [k for k in params.get("kinds") or OPPORTUNITY_KINDS if k in OPPORTUNITY_KINDS]
    try:
        with events.reporting_steps(run_id):
            report("Looking for " + ", ".join(kinds) + " opportunities")
            found = await asyncio.to_thread(find_opportunities, profile, facts, icp, settings, kinds)
    except Exception as exc:
        await report_failure(lace_id, "opportunity search", exc)
        raise
    async with AsyncSessionLocal() as db, db.begin():
        new, refreshed = await lace_opportunities.upsert_found(db, lace_id, run_id, found)
        if new or not params.get("scheduled"):
            await lace_events.add(db, lace_id, opportunities_update(found, new))
        if new:
            await lace_activity.add(db, lace_id, "opportunities_found", f"Found {plural(new, 'new opportunity', 'new opportunities')}",
                                    names([o.title for o in found]))
    await set_run_fields(models.Run, run_id, status="completed", finished_at=datetime.now(UTC),
                         progress={"found": len(found), "new": new, "refreshed": refreshed})
    await events.publish(run_id, "complete", {"found": len(found)})


def opportunities_update(found: list, new: int) -> str:
    if not found:
        return "The opportunity search finished without finding anything current that fits."
    lines = []
    for o in sorted(found, key=lambda o: o.deadline or o.date or "9999"):
        when = f" (deadline {o.deadline})" if o.deadline else f" ({o.date})" if o.date else ""
        lines.append(f"[{o.kind}] {o.title}{when}: {o.why_it_fits} Next step: {o.how_to_act} ({o.url})")
    return (f"The opportunity search found {len(found)} open opportunities ({new} new):\n" + "\n".join(lines)
            + "\nNew ones wait for the founder to save or dismiss: show them (ids from list_suggestions).")
