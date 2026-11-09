"""The job that learns the startup's real customers (services/customer_learning):
reads each one's site into a sourced customer fact. When it learned any, the
run manager reworks the ideal customer profile from them (manager._after_customers)."""

import asyncio
import uuid
from datetime import UTC, datetime

from agents.lace.customers import customer_fact, describe_customer
from backend.app.database import models
from backend.app.database.connect import AsyncSessionLocal
from backend.app.runs import events
from backend.app.runs.lace_jobs import job_update
from backend.app.services import customer_learning
from backend.app.services.lace_activity import plural
from backend.app.services.lace_store import DbLaceStore
from backend.app.services.runs import set_run_fields
from config import settings
from utils.log import logger
from utils.progress import report


async def customers_job(run_id: uuid.UUID, lace_id: uuid.UUID, params: dict) -> None:
    store = DbLaceStore(AsyncSessionLocal, lace_id)
    profile = await store.profile()
    async with AsyncSessionLocal() as db:
        customers = await customer_learning.to_learn(db, lace_id, settings.customers_per_run)
    learned: list[str] = []
    with events.reporting_steps(run_id):
        report(f"Reading {plural(len(customers), 'customer')}' websites")
        for name, website in customers:
            try:
                traits = await asyncio.to_thread(describe_customer, name, website,
                                                 profile.startup_name or profile.website, settings)
            except Exception:  # noqa: BLE001 -- one customer failing must not lose the others
                logger.exception("Reading customer %s failed", website)
                continue
            if traits is not None:
                await store.record_fact(customer_fact(name, website, traits))
                learned.append(name)
    if learned or not params.get("scheduled"):
        async with AsyncSessionLocal() as db, db.begin():
            await job_update(db, lace_id, params, customers_update(learned, len(customers)), run_id)
    await set_run_fields(models.Run, run_id, status="completed", finished_at=datetime.now(UTC),
                         progress={"customers": len(customers), "learned": len(learned)})
    await events.publish(run_id, "complete", {"learned": len(learned)})


def customers_update(learned: list[str], tried: int) -> str:
    if not tried:
        return ("There was no customer to learn from: none is in the founder's CRM as a customer or marked as one "
                "with a website, or all were learned already. Ask the founder for a few past customers and their "
                "websites, or to mark leads as customers.")
    if not learned:
        return "None of the customers' websites could be read, so nothing was learned from them."
    return (f"Learned what {plural(len(learned), 'customer')} {'is' if len(learned) == 1 else 'are'} from their "
            f"websites ({', '.join(learned)}); they are facts under customers now. The ideal customer profile is "
            "being reworked from them: tell the founder briefly.")
