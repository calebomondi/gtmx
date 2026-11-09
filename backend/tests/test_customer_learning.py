"""Learning from the startup's real customers: CRM customers and leads marked
as customers, each read once from its site into a customer fact, after which
the ideal customer profile is reworked from them; and a CRM sync that brings
new customers starts the learning on its own."""

import asyncio
import uuid

import psycopg
from langchain_core.messages import AIMessage

from agents.schemas.icp import ICP, CustomerTraits
from backend.app.database.connect import AsyncSessionLocal
from backend.app.runs import customer_jobs, lace_jobs, manager, scheduler
from backend.app.services import crm_sync, customer_learning
from backend.tests.test_lace_jobs import _runs, _wait_for_turns, lace  # noqa: F401 -- fixture
from backend.tests.test_laces_api import lace_runtime  # noqa: F401 -- fixture
from backend.tests.test_runs import _wait_for_status
from config import settings


def _seed(lace_id) -> None:
    with psycopg.connect(settings.database_url, autocommit=True) as conn:
        for company, domain, status in (("Acme Clinics", "acme.test", "customer"), ("Beta", "beta.test", "open_deal"),
                                        ("Old Co", "old.test", "customer")):
            conn.execute("INSERT INTO lace_crm_records (id, lace_id, crm, kind, company, domain, status) VALUES"
                         " (%s, %s, 'zoho', 'company', %s, %s, %s)", (uuid.uuid4(), lace_id, company, domain, status))
        conn.execute("INSERT INTO lace_accounts (id, lace_id, key, name, account_type, record, website, temperature)"
                     " VALUES (%s, %s, 'mwanga.test', 'Mwanga Pharmacy', 'company', '{}', 'https://www.mwanga.test',"
                     " 'customer')", (uuid.uuid4(), lace_id))
        # Old Co was learned already.
        conn.execute("INSERT INTO lace_facts (id, lace_id, topic, claim, source_url, confidence, origin) VALUES"
                     " (%s, %s, 'customers', 'Customer Old Co: ...', 'https://old.test', 'medium', 'research')",
                     (uuid.uuid4(), lace_id))


async def _to_learn(lace_id, limit=10):
    async with AsyncSessionLocal() as db:
        return await customer_learning.to_learn(db, uuid.UUID(lace_id), limit)


def test_customers_to_learn_come_from_the_crm_and_the_founder(client, lace):  # noqa: F811
    _seed(lace)
    assert client.portal.call(_to_learn, lace) == [("Acme Clinics", "https://acme.test"),
                                                    ("Mwanga Pharmacy", "https://www.mwanga.test")]
    assert len(client.portal.call(_to_learn, lace, 1)) == 1


def test_learning_records_customers_then_reworks_the_icp(client, lace, lace_runtime, user, monkeypatch):  # noqa: F811
    _seed(lace)
    read = []

    def describe(name, website, startup, cfg):
        read.append(website)
        return CustomerTraits(what_they_do=f"{name} runs clinics.", location="Nairobi")
    monkeypatch.setattr(customer_jobs, "describe_customer", describe)
    guidance = []

    def define_icp(profile, facts, rivals, given):
        guidance.append((given, [f.claim for f in facts if f.topic == "customers"]))
        return ICP(buyer_type="b2b", industries=["Clinics"])
    monkeypatch.setattr(lace_jobs.lace_icp, "define_icp", define_icp)
    lace_runtime.extend(AIMessage(content="Noted.") for _ in range(3))

    run = client.portal.call(manager.start_lace_job, "lace_customers", user.id, uuid.UUID(lace), {})
    run = client.portal.call(_wait_for_status, run.id, {"completed"})
    assert run.progress == {"customers": 2, "learned": 2}
    assert read == ["https://acme.test", "https://www.mwanga.test"]
    icp = client.portal.call(_wait_for_icp, lace)
    client.portal.call(_wait_for_status, icp.id, {"completed"})
    given, customers = guidance[0]
    assert given == customer_learning.ICP_GUIDANCE
    assert "Customer Acme Clinics: Acme Clinics runs clinics (Nairobi)." in customers
    turns = client.portal.call(_wait_for_turns, lace, 1)
    assert any("Learned what 2 customers are" in u for t in turns for u in (t.input or {}).get("updates", []))
    # Learned once: nothing is left to read.
    assert client.portal.call(_to_learn, lace) == []


async def _wait_for_icp(lace_id):
    async with asyncio.timeout(10):
        while not (runs := await _runs(lace_id, "lace_icp")):
            await asyncio.sleep(0.05)
    return runs[0]


def test_with_no_customers_the_founder_is_asked_for_some(client, lace, lace_runtime, user):  # noqa: F811
    lace_runtime.append(AIMessage(content="Which customers should I learn from?"))
    run = client.portal.call(manager.start_lace_job, "lace_customers", user.id, uuid.UUID(lace), {})
    client.portal.call(_wait_for_status, run.id, {"completed"})
    update = client.portal.call(_wait_for_turns, lace, 1)[-1].input["updates"][0]
    assert "There was no customer to learn from" in update
    assert client.portal.call(_runs, lace, "lace_icp") == []


def test_a_crm_sync_with_new_customers_starts_the_learning(client, lace, user, monkeypatch):  # noqa: F811
    _seed(lace)
    with psycopg.connect(settings.database_url, autocommit=True) as conn:
        conn.execute("UPDATE laces SET status = 'active', crm_synced_at = NULL WHERE id = %s", (lace,))

    async def sync(lace_id, now=None):
        return 3
    monkeypatch.setattr(crm_sync, "sync_lace", sync)
    monkeypatch.setattr(customer_jobs, "describe_customer", lambda *a: None)
    assert client.portal.call(scheduler.sync_crms) >= 1
    [run] = client.portal.call(_runs, lace, "lace_customers")
    assert run.input == {"scheduled": True}
    client.portal.call(_wait_for_status, run.id, {"completed"})
