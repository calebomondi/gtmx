"""A new Lace starts its first searches once it has read its site, and the
team can have it read the site again: what the site no longer says goes,
what the founder said or confirmed stays."""

import asyncio
import uuid

import psycopg
from langchain_core.messages import AIMessage

from agents.schemas.icp import ICP
from agents.schemas.lace import NewFact, OnboardingResult
from backend.app.runs import lace_jobs, manager, understanding_jobs
from backend.tests.test_lace_jobs import RIVAL, _runs, _wait_for_turns
from backend.tests.test_laces_api import API, lace_runtime  # noqa: F401 -- fixture
from backend.tests.test_runs import _wait_for_status
from config import settings


def _new_lace(client) -> str:
    body = client.post(f"{API}/laces", json={"name": "Ada", "website": "acme.test"}).json()
    client.portal.call(_wait_for_status, uuid.UUID(body["run_id"]), {"completed"})
    return body["lace"]["id"]


def _facts(lace_id: str) -> dict[str, str]:
    """Current facts, claim -> origin."""
    with psycopg.connect(settings.database_url) as conn:
        return dict(conn.execute("SELECT claim, origin FROM lace_facts WHERE lace_id = %s AND retracted_at IS NULL"
                                 " AND superseded_by_id IS NULL", (lace_id,)).fetchall())


async def _first_run(lace_id: str, kind: str, timeout: float = 5.0):
    """The Lace's first run of a kind, once its onboarding's follow-up started it."""
    async with asyncio.timeout(timeout):
        while not (runs := await _runs(lace_id, kind)):
            await asyncio.sleep(0.05)
    return runs[0]


def test_a_new_lace_starts_its_competitor_search(client, lace_runtime, real_settle_in, monkeypatch):  # noqa: F811
    monkeypatch.setattr(lace_jobs, "find_competitors", lambda profile, facts, focus: [RIVAL])
    lace_runtime.extend(AIMessage(content="Noted.") for _ in range(4))
    lace = _new_lace(client)
    hunt = client.portal.call(_first_run, lace, "lace_competitors")
    client.portal.call(_wait_for_status, hunt.id, {"completed"})
    # Who buys isn't known yet, so no ideal customer profile is guessed at.
    assert client.portal.call(_runs, lace, "lace_icp") == []
    client.portal.call(_wait_for_turns, lace, 1)


def test_settling_in_starts_only_what_is_missing(client, lace_runtime, user, monkeypatch):  # noqa: F811
    lace = _new_lace(client)
    started: list[str] = []

    async def start(kind, user_id, lace_id, params):
        started.append(kind)
    monkeypatch.setattr(manager, "start_lace_job", start)
    with psycopg.connect(settings.database_url, autocommit=True) as conn:
        for claim in ("Clinic groups in Kenya buy from us.", "Aga Khan Clinics was our first customer."):
            conn.execute("INSERT INTO lace_facts (id, lace_id, topic, claim, confidence, origin) VALUES"
                         " (%s, %s, 'customers', %s, 'high', 'user')", (uuid.uuid4(), lace, claim))
    assert client.portal.call(_real(), user.id, uuid.UUID(lace)) == ["lace_competitors", "lace_icp"]
    with psycopg.connect(settings.database_url, autocommit=True) as conn:
        conn.execute("INSERT INTO lace_competitors (id, lace_id, name, website, domain_key, status)"
                     " VALUES (%s, %s, 'Rival', 'https://rival.test', 'rival.test', 'suggested')", (uuid.uuid4(), lace))
        conn.execute("UPDATE laces SET icp = %s WHERE id = %s",
                     (ICP(buyer_type="b2b", industries=["Clinics"]).model_dump_json(), lace))
    assert client.portal.call(_real(), user.id, uuid.UUID(lace)) == []


def _real():
    from backend.tests.conftest import _SETTLE_IN
    return _SETTLE_IN


def test_reading_the_site_again_keeps_what_still_holds(client, lace_runtime, monkeypatch):  # noqa: F811
    lace = _new_lace(client)  # its site said "Acme sells payroll to clinics."
    with psycopg.connect(settings.database_url, autocommit=True) as conn:
        for claim, origin, confirmed in (("Plans start at $20 a month.", "crawl", False),
                                         ("Acme has 12 staff.", "crawl", True),
                                         ("We sell to clinic groups.", "user", False)):
            source = None if origin == "user" else "https://acme.test/"
            conn.execute("INSERT INTO lace_facts (id, lace_id, topic, claim, source_url, confidence, origin, confirmed_at)"
                         " VALUES (%s, %s, 'offer', %s, %s, 'high', %s, CASE WHEN %s THEN now() END)",
                         (uuid.uuid4(), lace, claim, source, origin, confirmed))

    async def read_again(store, cfg):
        await store.record_fact(NewFact(topic="offer", claim="Acme sells payroll to clinics", source_url="https://acme.test/",
                                        confidence="high", origin="crawl"))  # still on the site
        await store.record_fact(NewFact(topic="pricing", claim="Plans start at $25 a month.",
                                        source_url="https://acme.test/pricing", confidence="high", origin="crawl"))
        return OnboardingResult(startup_name="Acme", pages_read=["https://acme.test/"], pages_failed=[],
                                facts_recorded=2, open_questions=[])
    monkeypatch.setattr(understanding_jobs, "onboard", read_again)
    lace_runtime.append(AIMessage(content="Your pricing changed to $25."))

    started = client.post(f"{API}/laces/{lace}/understanding/refresh")
    assert started.status_code == 202
    run = client.portal.call(_wait_for_status, uuid.UUID(started.json()["run_id"]), {"completed"})
    assert run.progress == {"pages": 1, "new": 1, "retired": 1}
    assert _facts(lace) == {"Acme sells payroll to clinics.": "crawl", "Acme has 12 staff.": "crawl",
                            "We sell to clinic groups.": "user", "Plans start at $25 a month.": "crawl"}
    turns = client.portal.call(_wait_for_turns, lace, 1)
    assert "replace 1 older note from the site" in turns[-1].input["updates"][0]


def test_an_unreadable_site_changes_nothing(client, lace_runtime, monkeypatch):  # noqa: F811
    lace = _new_lace(client)
    before = _facts(lace)

    async def unreadable(store, cfg):
        return OnboardingResult(startup_name=None, pages_read=[], pages_failed=["https://acme.test"],
                                facts_recorded=0, open_questions=[])
    monkeypatch.setattr(understanding_jobs, "onboard", unreadable)
    lace_runtime.append(AIMessage(content="I couldn't read the site."))
    started = client.post(f"{API}/laces/{lace}/understanding/refresh")
    client.portal.call(_wait_for_status, uuid.UUID(started.json()["run_id"]), {"completed"})
    assert _facts(lace) == before
    turns = client.portal.call(_wait_for_turns, lace, 1)
    assert "could not be read this time" in turns[-1].input["updates"][0]
