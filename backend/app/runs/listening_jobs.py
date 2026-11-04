"""The background listen on a Lace's social accounts: what was said since
the last listen (mentions on X, comments on the founder's Instagram and
Facebook posts), sorted, and passed to the Lace as an update: the leads worth
engaging, the feedback, the questions waiting for an answer. Replies are
proposed by the Lace and posted only on the founder's approval."""

import asyncio
import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import select

from agents.lace.apps import AppError
from agents.lace.graph import BRIEF_FACTS
from agents.lace.listening import sort_heard
from agents.lace.store import JobBlocked
from agents.schemas.listening import HeardItem
from backend.app.database import models
from backend.app.database.connect import AsyncSessionLocal
from backend.app.runs import events
from backend.app.runs.lace_jobs import job_activity, job_update, report_failure
from backend.app.services.inbox import timestamp
from backend.app.services.lace_activity import plural
from backend.app.services.lace_apps import DbLaceApps
from backend.app.services.lace_store import DbLaceStore
from backend.app.services.runs import set_run_fields
from utils.progress import report

# Recent posts whose comments are read, and how far back a first listen goes.
POSTS_READ = 5
FIRST_LISTEN_DAYS = 7
_NOTHING_ON = ("No social account is on for this Lace: connect X, Instagram or Facebook under Apps & accounts in "
               "its settings, and switch it on, to listen there.")
_SECTIONS = (("lead", "Leads worth engaging"), ("question", "Questions waiting for an answer"),
             ("feedback", "Feedback"), ("praise", "Praise"))
_LABELS = {"x": "X", "instagram": "Instagram", "facebook": "Facebook"}


async def _since(lace_id: uuid.UUID, run_id: uuid.UUID) -> datetime:
    """When the last finished listen started; a first one looks back a week."""
    async with AsyncSessionLocal() as db:
        last = await db.scalar(select(models.Run.started_at).where(
            models.Run.lace_id == lace_id, models.Run.kind == "lace_listening", models.Run.status == "completed",
            models.Run.id != run_id).order_by(models.Run.started_at.desc()).limit(1))
    return last or datetime.now(UTC) - timedelta(days=FIRST_LISTEN_DAYS)


async def _hear(apps: DbLaceApps) -> tuple[list[dict], list[str], list[str]]:
    """(what was said, the platforms read, those that failed and why)."""
    reads = {"x": apps.x_mentions(), "instagram": apps.my_comments("instagram", POSTS_READ),
             "facebook": apps.my_comments("facebook", POSTS_READ)}
    results = await asyncio.gather(*reads.values(), return_exceptions=True)
    heard, read, failed = [], [], []
    for platform, result in zip(reads, results):
        if isinstance(result, AppError):
            failed.append(f"{_LABELS[platform]} ({result})")
        elif isinstance(result, BaseException):
            raise result
        elif result is not None:
            read.append(platform)
            heard += [{"platform": platform, "author": r.get("handle") or r.get("author"), "text": r.get("text"),
                       "url": r.get("url") or r.get("post_url"), "date": r.get("date")} for r in result]
    return heard, read, failed


def listening_update(found: list[tuple[dict, HeardItem]], heard: int, read: list[str], failed: list[str]) -> str:
    where = ", ".join(_LABELS[p] for p in read)
    cant = f" Couldn't read {', '.join(failed)}." if failed else ""
    if not found:
        return (f"Listened on {where}: {plural(heard, 'new mention or comment', 'new mentions and comments')}, "
                f"nothing worth acting on.{cant}")
    lines = [f"Listened on {where}: {plural(heard, 'new mention or comment', 'new mentions and comments')}.{cant}"]
    for kind, title in _SECTIONS:
        picked = [(item, verdict) for item, verdict in found if verdict.kind == kind]
        if picked:
            lines.append(f"{title}:")
            lines += [f"- [{_LABELS[item['platform']]}] @{item['author'] or 'someone'}: {verdict.note or item['text']}"
                      f" ({item['url']})" for item, verdict in picked]
    lines.append("Tell the founder who is worth engaging and what customers are saying. Offer replies (reply_to_comment, "
                 "engage_on_x) for the questions and leads: they post only once the founder approves.")
    return "\n".join(lines)


async def listening_job(run_id: uuid.UUID, lace_id: uuid.UUID, params: dict) -> None:
    """Listen since the last listen and queue an update. A scheduled listen
    that heard nothing worth acting on says nothing."""
    apps = DbLaceApps(AsyncSessionLocal, lace_id)
    store = DbLaceStore(AsyncSessionLocal, lace_id)
    try:
        since = await _since(lace_id, run_id)
        with events.reporting_steps(run_id):
            report("Listening on your social accounts")
            said, read, failed = await _hear(apps)
            if not read and not failed:
                if params.get("scheduled"):  # nothing to listen on: not a failure
                    await _finish(run_id, 0, 0)
                    return
                raise JobBlocked(_NOTHING_ON)
            fresh = [item for item in said if not item["date"] or timestamp(item["date"]) > since]
            profile, facts = await asyncio.gather(store.profile(), store.facts(None, BRIEF_FACTS))
            found = await asyncio.to_thread(sort_heard, profile.startup_name or profile.website, facts, fresh)
    except Exception as exc:
        if not params.get("scheduled"):
            await report_failure(lace_id, "listen on social accounts", exc, params)
        raise
    async with AsyncSessionLocal() as db, db.begin():
        if found or not params.get("scheduled"):
            await job_update(db, lace_id, params, listening_update(found, len(fresh), read, failed))
        if found:
            leads = sum(verdict.kind == "lead" for _, verdict in found)
            await job_activity(db, lace_id, params, "comments_read",
                               f"Heard {plural(len(fresh), 'new mention or comment', 'new mentions and comments')}",
                               f"{plural(leads, 'lead')} worth engaging" if leads else None)
    await _finish(run_id, len(fresh), len(found))


async def _finish(run_id: uuid.UUID, heard: int, kept: int) -> None:
    await set_run_fields(models.Run, run_id, status="completed", finished_at=datetime.now(UTC),
                         progress={"heard": heard, "kept": kept})
    await events.publish(run_id, "complete", {"kept": kept})
