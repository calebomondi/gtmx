"""The scheduled job that drafts a Lace's due follow-ups (services/follow_ups):
for each first email (or first follow-up) nobody answered in time, either the
reason it stops, or a follow-up written from the thread, saved as a draft in
the same thread for the founder to send. The Lace hears what was drafted."""

import asyncio
import uuid
from datetime import UTC, datetime

from agents.lace.graph import BRIEF_FACTS
from agents.lace.prompts import render_brief
from agents.pipelines.outreach.follow_up import FollowUpBrief, write_follow_up
from backend.app.database import models
from backend.app.database.connect import AsyncSessionLocal
from backend.app.database.lace_models import LaceAccount, LaceOutreach
from backend.app.runs import events
from backend.app.runs.lace_jobs import job_update, with_instructions
from backend.app.services import follow_ups, lace_activity, lace_instructions
from backend.app.services import outreach as outreach_service
from backend.app.services.lace_activity import names, plural
from backend.app.services.lace_store import DbLaceStore
from backend.app.services.runs import set_run_fields
from config import settings
from utils.log import logger
from utils.progress import report


async def follow_ups_job(run_id: uuid.UUID, lace_id: uuid.UUID, params: dict) -> None:
    now = datetime.now(UTC)
    async with AsyncSessionLocal() as db:
        run = await db.get(models.Run, run_id)
        due = await follow_ups.due(db, lace_id, now, settings.follow_ups_batch)
        user_id = run.user_id
    facts = await DbLaceStore(AsyncSessionLocal, lace_id).facts(None, BRIEF_FACTS)
    sender = await outreach_service.sender_for_user(user_id)
    async with AsyncSessionLocal() as db:
        note = with_instructions(None, await lace_instructions.for_job(db, lace_id, "outreach"))
    drafted: list[uuid.UUID] = []
    failed: list[uuid.UUID] = []
    with events.reporting_steps(run_id):
        report(f"Looking at {plural(len(due), 'email')} waiting for an answer")
        for message_id in [m.id for m in due]:
            outcome = await _one(run_id, message_id, facts, sender, note, now)
            if outcome is True:
                drafted.append(message_id)
            elif outcome is False:
                failed.append(message_id)
    async with AsyncSessionLocal() as db, db.begin():
        rows = [await db.get(LaceOutreach, i) for i in drafted]
        if rows:
            await job_update(db, lace_id, params, follow_ups_update([r.recipient_company or r.recipient_name or ""
                                                                     for r in rows]), run_id)
            await lace_activity.add(db, lace_id, "drafts_ready", f"{plural(len(rows), 'follow-up')} drafted for you to send",
                                    names([r.recipient_company or "" for r in rows]))
    await set_run_fields(models.Run, run_id, status="completed", finished_at=datetime.now(UTC),
                         progress={"due": len(due), "drafted": len(drafted), "failed": len(failed)})
    await events.publish(run_id, "complete", {"drafted": len(drafted)})


def _with_notes(note: str | None, account: LaceAccount | None) -> str | None:
    """The run's note, with what the founder wrote about this lead in their
    leads sheet."""
    if account is None or not account.founder_notes:
        return note
    return "\n".join(filter(None, [note, f"About {account.name}, from the founder's leads sheet: "
                                          f"{account.founder_notes}"]))


async def _one(run_id: uuid.UUID, message_id: uuid.UUID, facts, sender: str, note: str | None,
               now: datetime) -> bool | None:
    """Draft the follow-up to one email, or record why it stops. True when
    drafted, False when the writer failed (tried again at the next sweep),
    None when it stops or waits."""
    async with AsyncSessionLocal() as db, db.begin():
        message = await db.get(LaceOutreach, message_id)
        account = await db.get(LaceAccount, message.account_id) if message.account_id else None
        if (until := follow_ups.snoozed_until(account, now)) is not None:
            message.follow_up_due_at = until  # "not now": ask again then
            return None
        if (why := await follow_ups.stop_reason(db, message, account)) is not None:
            logger.info("No follow-up to message %s: %s", message_id, why)
            message.follow_up_due_at = None
            return None
        brief = FollowUpBrief(sender_name=sender, contact_name=message.recipient_name,
                              company=message.recipient_company or (account.name if account else ""),
                              offer=render_brief(facts), earlier=await follow_ups.earlier_bodies(db, message),
                              step=message.sequence_step + 1, note=_with_notes(note, account))
    try:
        written = await asyncio.to_thread(write_follow_up, brief)
    except Exception:  # noqa: BLE001 -- one email failing must not stop the others; retried next sweep
        logger.exception("Follow-up to message %s failed", message_id)
        return False
    async with AsyncSessionLocal() as db, db.begin():
        message = await db.get(LaceOutreach, message_id)
        if message.follow_up_due_at is None:  # handled meanwhile (a reply came in)
            return None
        db.add(follow_ups.follow_up_draft(message, written.body, run_id))
        message.follow_up_due_at = None
    return True


def follow_ups_update(companies: list[str]) -> str:
    return ("Follow-ups are drafted for emails nobody answered yet; they wait in Outreach, in the same threads, for "
            "the founder to review and send: " + ", ".join(c for c in companies if c) + ". Tell the founder briefly.")
