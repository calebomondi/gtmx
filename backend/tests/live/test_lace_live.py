"""A Lace end to end against real services: the API creates it, it onboards
from a real website, then answers a founder message that needs web research.
Real Firecrawl, Exa, LLM ladder and Postgres checkpointer.

    uv run pytest -m live backend/tests/live/test_lace_live.py -s
"""

import json
import uuid

import pytest

from backend.app import agents_runtime
from backend.tests.test_runs import _wait_for_status
from config import settings

pytestmark = pytest.mark.live

API = "/api/v1"
WEBSITE = "linear.app"
ONBOARDING_TIMEOUT_S = 600
TURN_TIMEOUT_S = 300


@pytest.fixture
def runtime(client):
    client.portal.call(agents_runtime.start_agent_runtime, settings.database_url)
    yield
    client.portal.call(agents_runtime.stop_agent_runtime)


def _frames(client, run_id: str) -> list[dict]:
    with client.stream("GET", f"{API}/runs/{run_id}/events") as response:
        return [json.loads(line) for line in response.iter_lines() if line]


def test_lace_onboards_and_researches(client, runtime):
    created = client.post(f"{API}/laces", json={"name": "Ada", "website": WEBSITE}).json()
    lace_id, run_id = created["lace"]["id"], created["run_id"]
    run = client.portal.call(_wait_for_status, uuid.UUID(run_id), {"completed", "failed"}, ONBOARDING_TIMEOUT_S)
    assert run.status == "completed", run.error

    lace = client.get(f"{API}/laces/{lace_id}").json()
    facts = client.get(f"{API}/laces/{lace_id}/facts").json()
    [opening] = client.get(f"{API}/laces/{lace_id}/messages").json()
    print(f"\n--- {lace['startup_name']}: {len(facts)} facts\n--- OPENING\n{opening['content']}")
    assert lace["status"] == "active" and len(facts) >= 5 and opening["role"] == "lace"

    sent = client.post(f"{API}/laces/{lace_id}/messages", json={
        "text": "Who are our three closest competitors? Look them up and note what you find."}).json()
    run = client.portal.call(_wait_for_status, uuid.UUID(sent["run_id"]), {"completed", "failed"}, TURN_TIMEOUT_S)
    assert run.status == "completed", run.error

    frames = _frames(client, sent["run_id"])
    steps = [f["text"] for f in frames if f["type"] == "step"]
    reply = client.get(f"{API}/laces/{lace_id}/messages").json()[-1]
    print("--- STEPS\n" + "\n".join(steps) + f"\n--- REPLY\n{reply['content']}")
    assert steps and reply["role"] == "lace" and reply["content"].strip()
    after = client.get(f"{API}/laces/{lace_id}/facts?topic=competition").json()
    print(f"--- competition facts recorded: {len(after)}")


HUNT_TIMEOUT_S = 1800


def test_lace_hunts_competitors_and_reports_back(client, runtime, user):
    import psycopg

    from backend.app.runs import manager

    created = client.post(f"{API}/laces", json={"name": "Ada", "website": WEBSITE}).json()
    lace_id = uuid.UUID(created["lace"]["id"])
    run = client.portal.call(_wait_for_status, uuid.UUID(created["run_id"]), {"completed", "failed"}, ONBOARDING_TIMEOUT_S)
    assert run.status == "completed", run.error

    job_id = client.portal.call(manager.start_lace_job, "lace_competitors", user.id, lace_id, {"focus": None}).id
    job = client.portal.call(_wait_for_status, uuid.UUID(job_id), {"completed", "failed"}, HUNT_TIMEOUT_S)
    assert job.status == "completed", job.error
    # The wake turn starts just after the job marks itself completed.
    wake = client.portal.call(_first_turn, lace_id)
    with psycopg.connect(settings.database_url) as conn:
        rows = conn.execute("SELECT name, website, summary FROM lace_competitors WHERE lace_id = %s", (lace_id,)).fetchall()
    print(f"\n--- {len(rows)} competitors, job progress {job.progress}")
    for name, website, summary in rows:
        print(f"  {name} ({website}): {(summary or '')[:100]}")
    assert rows and wake, "no competitors saved, or the Lace was not woken"
    turn = client.portal.call(_wait_for_status, wake, {"completed", "failed"}, TURN_TIMEOUT_S)
    assert turn.status == "completed", turn.error
    print("--- THE LACE SAYS\n" + client.get(f"{API}/laces/{lace_id}/messages").json()[-1]["content"])


async def _first_turn(lace_id: uuid.UUID, timeout: float = 30.0) -> uuid.UUID:
    import asyncio

    from sqlalchemy import select

    from backend.app.database import models
    from backend.app.database.connect import AsyncSessionLocal
    async with asyncio.timeout(timeout):
        while True:
            async with AsyncSessionLocal() as db:
                run_id = await db.scalar(select(models.Run.id).where(
                    models.Run.lace_id == lace_id, models.Run.kind == "lace_turn"))
            if run_id:
                return run_id
            await asyncio.sleep(0.2)


MONITOR_TIMEOUT_S = 900


def test_lace_monitors_competitors(client, runtime, user):
    import psycopg

    from backend.app.runs import manager

    created = client.post(f"{API}/laces", json={"name": "Ada", "website": WEBSITE}).json()
    lace_id = uuid.UUID(created["lace"]["id"])
    run = client.portal.call(_wait_for_status, uuid.UUID(created["run_id"]), {"completed", "failed"}, ONBOARDING_TIMEOUT_S)
    assert run.status == "completed", run.error
    with psycopg.connect(settings.database_url, autocommit=True) as conn:
        for name, site in (("Jira", "https://www.atlassian.com/software/jira"), ("ClickUp", "https://clickup.com")):
            conn.execute("INSERT INTO lace_competitors (id, lace_id, name, website, domain_key) VALUES (%s, %s, %s, %s, %s)",
                         (uuid.uuid4(), lace_id, name, site, name.lower()))

    job = client.portal.call(manager.start_lace_job, "lace_monitor", user.id, lace_id, {})
    job = client.portal.call(_wait_for_status, job.id, {"completed", "failed"}, MONITOR_TIMEOUT_S)
    assert job.status == "completed", job.error
    print(f"\n--- monitor: {job.progress}")
    with psycopg.connect(settings.database_url) as conn:
        for claim, url in conn.execute("SELECT claim, source_url FROM lace_facts WHERE origin = 'monitor'"):
            print(f"  FACT {claim}  <- {url}")
        checked = conn.execute("SELECT count(*) FROM lace_competitors WHERE monitor_state IS NOT NULL").fetchone()[0]
    assert checked == 2
    if job.progress["changes"]:
        turn = client.portal.call(_wait_for_status, client.portal.call(_first_turn, lace_id), {"completed", "failed"},
                                  TURN_TIMEOUT_S)
        assert turn.status == "completed", turn.error
        print("--- THE LACE SAYS\n" + client.get(f"{API}/laces/{lace_id}/messages").json()[-1]["content"])


ACCOUNTS_TIMEOUT_S = 1800


def test_lace_finds_customers_in_kenya(client, runtime, user):
    import psycopg

    from backend.app.runs import manager

    created = client.post(f"{API}/laces", json={"name": "Ada", "website": "shangalabs.com"}).json()
    lace_id = uuid.UUID(created["lace"]["id"])
    run = client.portal.call(_wait_for_status, uuid.UUID(created["run_id"]), {"completed", "failed"}, ONBOARDING_TIMEOUT_S)
    assert run.status == "completed", run.error

    sent = client.post(f"{API}/laces/{lace_id}/messages", json={
        "text": "Work out our ideal customer profile. We sell to companies in Kenya."}).json()
    turn = client.portal.call(_wait_for_status, uuid.UUID(sent["run_id"]), {"completed", "failed"}, TURN_TIMEOUT_S)
    assert turn.status == "completed", turn.error
    with psycopg.connect(settings.database_url) as conn:
        icp = conn.execute("SELECT icp FROM laces WHERE id = %s", (lace_id,)).fetchone()[0]
    print(f"\n--- ICP industries {icp and icp.get('industries')}, geo {icp and icp.get('geo')}, beachhead {icp and icp.get('beachhead')}")
    assert icp

    job = client.portal.call(manager.start_lace_job, "lace_accounts", user.id, lace_id, {"country": "Kenya"})
    job = client.portal.call(_wait_for_status, job.id, {"completed", "failed"}, ACCOUNTS_TIMEOUT_S)
    assert job.status == "completed", job.error
    accounts = client.get(f"{API}/laces/{lace_id}/accounts").json()
    print(f"--- {len(accounts)} accounts, {job.progress}")
    for a in accounts:
        case = a["case"] or {}
        print(f"  {a['name']} [{a['geo']}] ({a['website']}) {case.get('strength')}: WHY NOW {(a['trigger'] or {}).get('event')}"
              f" | NEED {case.get('need')}")
    assert accounts and all(a["trigger"] for a in accounts)


CONTACTS_TIMEOUT_S = 1200
KENYAN_ACCOUNTS = [("Enzi E-Mobility", "https://enzimotors.com"), ("SunCulture", "https://sunculture.com"),
                   ("Reflex Technologies", "https://reflextechnologies.co.ke"), ("Synnefa", "https://synnefa.io")]


def test_lace_finds_contacts_at_real_accounts(client, runtime, user):
    import json

    import psycopg

    from agents.schemas.accounts import AccountRecord, TriggerEvent
    from backend.app.runs import manager

    with psycopg.connect(settings.database_url, autocommit=True) as conn:
        lace_id = conn.execute(
            "INSERT INTO laces (id, user_id, name, website, startup_name, status, icp) VALUES"
            " (%s, %s, 'Ada', 'https://shangalabs.com', 'Shanga Labs', 'active', %s) RETURNING id",
            (uuid.uuid4(), user.id, json.dumps({"buyer_type": "b2b", "geo": ["Kenya"],
                                                "buyer_titles": ["CEO", "CTO", "Head of Engineering"]})),
        ).fetchone()[0]
        for name, site in KENYAN_ACCOUNTS:
            record = AccountRecord(name=name, website=site, domain=site.split("//")[1], geo="Kenya",
                                   trigger_event=TriggerEvent(event="Growing", signal_type="hiring_post", source=site))
            conn.execute("INSERT INTO lace_accounts (id, lace_id, key, name, account_type, website, record)"
                         " VALUES (%s, %s, %s, %s, 'company', %s, %s)",
                         (uuid.uuid4(), lace_id, site.split("//")[1], name, site, json.dumps(record.model_dump(mode="json"))))

    job = client.portal.call(manager.start_lace_job, "lace_contacts", user.id, lace_id, {})
    job = client.portal.call(_wait_for_status, job.id, {"completed", "failed"}, CONTACTS_TIMEOUT_S)
    assert job.status == "completed", job.error
    print(f"\n--- contacts: {job.progress}")
    for a in client.get(f"{API}/laces/{lace_id}/accounts").json():
        people = [f"{c['name']} ({c['title']}) {c['email'] or c['linkedin']}" for c in a["contacts"] if c["name"]]
        emails = [c["email"] for c in a["contacts"] if not c["name"] and c["email"]]
        print(f"  {a['name']}: {a['contact_status']} | people {people} | emails {emails} | channels {a['channels']}")
    assert job.progress["searched"] == len(KENYAN_ACCOUNTS)
    # Wait for the Lace to report, so teardown never stops the loop mid-turn.
    turn = client.portal.call(_wait_for_status, client.portal.call(_first_turn, lace_id), {"completed", "failed"},
                              TURN_TIMEOUT_S)
    assert turn.status == "completed", turn.error
    print("--- THE LACE SAYS\n" + client.get(f"{API}/laces/{lace_id}/messages").json()[-1]["content"])
