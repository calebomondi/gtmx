"""The background search for the laws, regulations, bills and filing
obligations that apply to a Lace's startup, where a founder confirmed it is
registered and operates. What it finds waits as suggestions; the Lace hears
about them in an update."""

import asyncio
import uuid
from datetime import UTC, datetime

from agents.lace.graph import BRIEF_FACTS
from agents.lace.regulations import find_regulations
from agents.lace.store import JobBlocked
from agents.schemas.regulations import Regulation
from backend.app.database import models
from backend.app.database.connect import AsyncSessionLocal
from backend.app.runs import events
from backend.app.runs.lace_jobs import good_fits, job_activity, job_update, private_to, report_failure
from backend.app.services import lace_regulations
from backend.app.services.lace_activity import names, plural
from backend.app.services.lace_store import DbLaceStore
from backend.app.services.runs import set_run_fields
from config import settings
from utils.progress import report

NOT_CONFIRMED = ("No one has confirmed where the startup is registered and operates yet. Ask the founder, then "
                 "record it with set_jurisdiction and search again.")


def regulations_update(found: list[Regulation], new: int, weak: int, places: list[str]) -> str:
    """The update the Lace reads: each find with why it applies and what to do."""
    where = ", ".join(places)
    if not found:
        left = f" It left out {plural(weak, 'loose match', 'loose matches')}." if weak else ""
        return (f"The search for laws and regulations in {where} found nothing on official sources that clearly "
                f"applies.{left} Say so plainly; don't guess at what might apply.")
    lines = []
    for r in sorted(found, key=lambda r: (r.kind != "bill", r.next_date or "9999")):
        stage = f", {r.stage.replace('_', ' ')}" if r.stage else ""
        when = f" Next date: {r.next_date}." if r.next_date else ""
        lines.append(f"[{r.kind}, {r.jurisdiction}{stage}] {r.title}: {r.why_it_applies} To do: {r.what_to_do}"
                     f"{when} ({r.url})")
    return (f"The search for laws and regulations in {where} found {len(found)} that apply ({new} new):\n"
            + "\n".join(lines)
            + "\nNew ones are suggestions: tell the founder what each means for us, with its source, and ask which "
              "to track (ids from list_regulations, status suggested). It is information, not legal advice.")


async def regulations_job(run_id: uuid.UUID, lace_id: uuid.UUID, params: dict) -> None:
    """Search where the startup is registered and operates, save what is cited
    and applies, and queue an update. A scheduled search that found nothing
    new says nothing."""
    store = DbLaceStore(AsyncSessionLocal, lace_id)
    profile, facts, place = await asyncio.gather(store.profile(), store.facts(None, BRIEF_FACTS), store.jurisdiction())
    try:
        if not place.confirmed:
            raise JobBlocked(NOT_CONFIRMED)
        with events.reporting_steps(run_id):
            report("Looking for the laws and regulations in " + ", ".join(place.places))
            found = await asyncio.to_thread(find_regulations, profile, facts, place.registered_in, place.operates_in,
                                            settings)
    except Exception as exc:
        await report_failure(lace_id, "search for laws and regulations", exc, params)
        raise
    found, weak = good_fits(found, lambda r: r.relevance)
    async with AsyncSessionLocal() as db, db.begin():
        new, refreshed = await lace_regulations.upsert_found(db, lace_id, run_id, found, private_to(params))
        if new or not params.get("scheduled"):
            await job_update(db, lace_id, params, regulations_update(found, new, len(weak), place.places), run_id)
        if new:
            await job_activity(db, lace_id, params, "regulations_found",
                               f"Found {plural(new, 'law or regulation', 'laws and regulations')} that "
                               + ("applies" if new == 1 else "apply"),
                               names([r.title for r in found]))
    await set_run_fields(models.Run, run_id, status="completed", finished_at=datetime.now(UTC),
                         progress={"found": len(found), "new": new, "refreshed": refreshed})
    await events.publish(run_id, "complete", {"found": len(found)})
