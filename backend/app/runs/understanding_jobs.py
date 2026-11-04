"""Refreshing what a Lace knows about its startup: it reads the site again and
looks the startup up on the web, as onboarding did, and what the site said
before gives way to what it says now. What the founder said or confirmed is
never touched."""

import uuid
from datetime import UTC, datetime

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from agents.lace.onboarding import onboard
from agents.schemas.lace import Fact, NewFact
from backend.app.database import models
from backend.app.database.connect import AsyncSessionLocal
from backend.app.database.lace_models import LaceFact
from backend.app.runs import events
from backend.app.runs.lace_jobs import job_update, report_failure
from backend.app.services.lace_activity import plural
from backend.app.services.lace_store import DbLaceStore
from backend.app.services.runs import set_run_fields
from config import settings
from utils.progress import report

# Current facts compared against when skipping ones already known.
KNOWN_FACTS = 500


def _key(claim: str) -> str:
    return " ".join(claim.lower().split()).rstrip(".")


class _NewOnly(DbLaceStore):
    """The Lace's store, recording only facts it doesn't already hold, so a
    second read of the same page or press story doesn't note it twice. What
    it skipped is `restated`: still true, so kept."""

    def __init__(self, lace_id: uuid.UUID, known: set[str]):
        super().__init__(AsyncSessionLocal, lace_id)
        self._known = known
        self.restated: set[str] = set()
        self.recorded = 0

    async def record_fact(self, fact: NewFact) -> Fact | None:
        key = _key(fact.claim)
        if key in self._known:
            self.restated.add(key)
            return None
        self._known.add(key)
        self.recorded += 1
        return await super().record_fact(fact)


async def _retire_old_site_facts(db: AsyncSession, lace_id: uuid.UUID, before: datetime,
                                 restated: set[str]) -> int:
    """Retract what the site said before this read and no longer says,
    unless the founder confirmed it. Returns how many."""
    old = (await db.execute(select(LaceFact.id, LaceFact.claim).where(
        LaceFact.lace_id == lace_id, LaceFact.origin == "crawl", LaceFact.recorded_at < before,
        LaceFact.confirmed_at.is_(None), LaceFact.retracted_at.is_(None), LaceFact.superseded_by_id.is_(None),
    ))).all()
    gone = [fact_id for fact_id, claim in old if _key(claim) not in restated]
    if gone:
        await db.execute(update(LaceFact).where(LaceFact.id.in_(gone)).values(retracted_at=func.now()))
    return len(gone)


def refresh_update(pages: int, noted: int, from_web: int, retired: int) -> str:
    web = f", {from_web} of them from elsewhere on the web" if from_web else ""
    replaced = f" They replace {plural(retired, 'older note')} from the site." if retired else ""
    return (f"Re-reading the site ({plural(pages, 'page')}) and looking the startup up again noted "
            f"{plural(noted, 'new thing')}{web}.{replaced} Tell the founder in a few words what changed that "
            "matters, if anything, and ask them to correct what's wrong.")


async def refresh_job(run_id: uuid.UUID, lace_id: uuid.UUID, params: dict) -> None:
    """Read the site and the web again; keep what is new, retire the site's
    older unconfirmed facts, and queue an update. A site that can't be read
    changes nothing."""
    started = datetime.now(UTC)
    known = {_key(f.claim) for f in await DbLaceStore(AsyncSessionLocal, lace_id).facts(None, KNOWN_FACTS)}
    store = _NewOnly(lace_id, known)
    try:
        with events.reporting_steps(run_id):
            report("Reading your site again")
            result = await onboard(store, settings)
    except Exception as exc:
        await report_failure(lace_id, "re-read of the site", exc, params)
        raise
    async with AsyncSessionLocal() as db, db.begin():
        if result.site_unreadable:
            await job_update(db, lace_id, params, "The site could not be read this time, so what you knew about the "
                             "startup stays as it was. Tell the founder, and offer to try again later.")
            retired = 0
        else:
            retired = await _retire_old_site_facts(db, lace_id, started, store.restated)
            await job_update(db, lace_id, params, refresh_update(len(result.pages_read), store.recorded,
                                                                 result.from_web, retired))
    await set_run_fields(models.Run, run_id, status="completed", finished_at=datetime.now(UTC),
                         progress={"pages": len(result.pages_read), "new": store.recorded, "retired": retired})
    await events.publish(run_id, "complete", {"new": store.recorded})
