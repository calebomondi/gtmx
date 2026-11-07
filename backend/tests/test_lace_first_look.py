"""A new Lace's first look (its top competitors, ideal customer and top
opportunities) waits for the founder's first reply, and it does no scheduled
work on its first day. The team can have it read the site again: what the
site no longer says goes, what the founder said or confirmed stays."""

import asyncio
import uuid
from datetime import UTC, datetime

import psycopg
from langchain_core.messages import AIMessage

from agents.schemas.icp import ICP
from agents.schemas.lace import NewFact, OnboardingResult
from backend.app.database.connect import AsyncSessionLocal
from backend.app.runs import lace_jobs, manager, understanding_jobs
from backend.app.services import lace_briefs, lace_listening, lace_opportunities
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
    """The Lace's first run of a kind, once something started it."""
    async with asyncio.timeout(timeout):
        while not (runs := await _runs(lace_id, kind)):
            await asyncio.sleep(0.05)
    return runs[0]


_BUYERS = ("Clinic groups in Kenya buy from us.", "Aga Khan Clinics was our first customer.")


def _knows_buyers(lace_id: str) -> None:
    with psycopg.connect(settings.database_url, autocommit=True) as conn:
        for claim in _BUYERS:
            conn.execute("INSERT INTO lace_facts (id, lace_id, topic, claim, confidence, origin) VALUES"
                         " (%s, %s, 'customers', %s, 'high', 'user')", (uuid.uuid4(), lace_id, claim))


def _founder_turn(lace_id: str, user_id) -> None:
    """A finished reply in the team's chat, as if the founder had written."""
    with psycopg.connect(settings.database_url, autocommit=True) as conn:
        conn.execute("INSERT INTO runs (id, user_id, lace_id, kind, status, input) VALUES"
                     " (%s, %s, %s, 'lace_turn', 'completed', '{\"text\": \"hi\"}')",
                     (uuid.uuid4(), user_id, lace_id))


def test_the_first_look_waits_for_the_founders_first_reply(client, lace_runtime, real_first_look,  # noqa: F811
                                                            monkeypatch):
    monkeypatch.setattr(lace_jobs, "find_competitors", lambda *args, **kwargs: [RIVAL])
    monkeypatch.setattr(lace_jobs.lace_icp, "define_icp",
                        lambda profile, facts, rivals, guidance: ICP(buyer_type="b2b", industries=["Clinics"]))
    monkeypatch.setattr(lace_jobs, "find_opportunities", lambda *args, **kwargs: [])
    lace_runtime.extend(AIMessage(content="Noted.") for _ in range(6))
    lace = _new_lace(client)
    _knows_buyers(lace)
    # The welcome alone starts nothing.
    for kind in ("lace_competitors", "lace_icp", "lace_opportunities"):
        assert client.portal.call(_runs, lace, kind) == []

    client.post(f"{API}/laces/{lace}/messages", json={"text": "Right, and we sell to clinic groups."})
    hunt = client.portal.call(_first_run, lace, "lace_competitors")
    assert hunt.input == {"focus": None, "first_look": True, "limit": manager.FIRST_LOOK_LIMIT}
    icp = client.portal.call(_first_run, lace, "lace_icp")
    assert icp.input == {"guidance": None, "first_look": True}
    # Its profile saved, the top opportunities for it are next.
    scan = client.portal.call(_first_run, lace, "lace_opportunities")
    assert scan.input == {"first_look": True, "limit": manager.FIRST_LOOK_LIMIT}
    for run in (hunt, icp, scan):
        client.portal.call(_wait_for_status, run.id, {"completed"})

    client.post(f"{API}/laces/{lace}/messages", json={"text": "Thanks!"})
    client.portal.call(_wait_for_turns, lace, 2)
    for kind in ("lace_competitors", "lace_icp", "lace_opportunities"):
        assert len(client.portal.call(_runs, lace, kind)) == 1


def test_the_first_look_starts_only_what_is_missing(client, lace_runtime, user, monkeypatch):  # noqa: F811
    lace = _new_lace(client)
    started: list[str] = []

    async def start(kind, user_id, lace_id, params):
        started.append(kind)
    monkeypatch.setattr(manager, "start_lace_job", start)

    def first_look() -> list[str]:
        started.clear()
        client.portal.call(_real(), user.id, uuid.UUID(lace))
        return list(started)

    assert first_look() == []  # no reply yet
    _founder_turn(lace, user.id)
    assert first_look() == ["lace_competitors"]  # who buys isn't known: no profile guessed at
    _knows_buyers(lace)
    assert first_look() == ["lace_competitors", "lace_icp"]
    # The founder asked for competitors themselves, and a profile is on file.
    with psycopg.connect(settings.database_url, autocommit=True) as conn:
        conn.execute("INSERT INTO runs (id, user_id, lace_id, kind, status) VALUES"
                     " (%s, %s, %s, 'lace_competitors', 'completed')", (uuid.uuid4(), user.id, lace))
        conn.execute("UPDATE laces SET icp = %s WHERE id = %s",
                     (ICP(buyer_type="b2b", industries=["Clinics"]).model_dump_json(), lace))
    assert first_look() == ["lace_opportunities"]
    # Only on the first reply.
    _founder_turn(lace, user.id)
    assert first_look() == []


def test_a_new_lace_has_no_scheduled_work_on_its_first_day(client, lace_runtime, user):  # noqa: F811
    lace = _new_lace(client)
    with psycopg.connect(settings.database_url, autocommit=True) as conn:
        conn.execute("UPDATE laces SET icp = %s, brief_hour = 0 WHERE id = %s",
                     (ICP(buyer_type="b2b", industries=["Clinics"]).model_dump_json(), lace))

    async def due() -> dict[str, bool]:
        now = datetime.now(UTC)
        async with AsyncSessionLocal() as db:
            return {"brief": lace in [str(x.id) for x in await lace_briefs.due_laces(db, now)],
                    "listening": lace in [str(i) for i, _ in await lace_listening.laces_due(db, now)],
                    "opportunities": lace in [str(i) for i, _ in await lace_opportunities.laces_due_for_scan(db, now)]}

    assert client.portal.call(due) == {"brief": False, "listening": False, "opportunities": False}
    with psycopg.connect(settings.database_url, autocommit=True) as conn:
        conn.execute("UPDATE laces SET created_at = now() - interval '2 days' WHERE id = %s", (lace,))
    assert client.portal.call(due) == {"brief": True, "listening": True, "opportunities": True}


def _real():
    from backend.tests.conftest import _FIRST_LOOK
    return _FIRST_LOOK


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
