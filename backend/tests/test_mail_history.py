"""Earlier mail with a lead in the founder's Gmail: before a first email is
drafted, a lead the founder has emailed before starts warm, and its draft is
written as a follow-on rather than a cold introduction."""

import uuid

import psycopg
from langchain_core.messages import AIMessage

from agents.lace.apps import AppError
from agents.schemas.accounts import AccountRecord, ContactRecord, TriggerEvent
from backend.app.runs import manager
from backend.app.services import lace_apps, mail_history
from backend.tests.test_lace_jobs import lace  # noqa: F401 -- fixture
from backend.tests.test_lace_outreach import _account, _stub_writer
from backend.tests.test_laces_api import lace_runtime  # noqa: F401 -- fixture
from backend.tests.test_runs import _wait_for_status
from config import settings

MAILS = [{"thread_id": "t1", "from": "jane@alpha.test", "subject": "Pilot next steps", "date": "2026-09-01",
          "snippet": "..."},
         {"thread_id": "t2", "from": "me@startup.test", "subject": "Intro", "date": "2026-08-20", "snippet": "..."}]


def _mailbox(monkeypatch, by_domain: dict) -> list[str]:
    """The founder's Gmail, answering searches by the domain they ask about."""
    asked: list[str] = []

    async def search(self, query, days):
        asked.append(query)
        domain = query.split("from:")[1].split(" ")[0]
        answer = by_domain.get(domain, [])
        if isinstance(answer, Exception):
            raise answer
        return answer
    monkeypatch.setattr(lace_apps.DbLaceApps, "email_search", search)
    return asked


def _record(name: str, website: str | None = None) -> AccountRecord:
    return AccountRecord(name=name, website=website,
                         trigger_event=TriggerEvent(event="Raised", signal_type="funding_round", source="https://n.test"))


async def test_earlier_mail_is_found_by_the_leads_domain(real_mail_history, monkeypatch):
    asked = _mailbox(monkeypatch, {"alpha.test": MAILS, "beta.test": AppError("Only the owner's Gmail.")})
    found = await mail_history.earlier_mail(uuid.uuid4(), uuid.uuid4(), [
        (a := uuid.uuid4(), _record("Alpha", "https://www.alpha.test/")),
        (uuid.uuid4(), _record("Beta", "beta.test")),
        (uuid.uuid4(), _record("No site"))])
    assert found == {a: MAILS}
    assert asked == ["(from:alpha.test OR to:alpha.test)", "(from:beta.test OR to:beta.test)"]


def test_the_note_says_it_is_a_follow_on():
    note = mail_history.follow_on_note("Alpha", MAILS)
    assert "2 earlier emails" in note and '"Pilot next steps"' in note and "not a cold introduction" in note


def test_a_lead_emailed_before_starts_warm_and_gets_a_follow_on(client, lace, lace_runtime, user,  # noqa: F811
                                                                real_mail_history, monkeypatch):
    written = _stub_writer(monkeypatch)
    _mailbox(monkeypatch, {"alpha.test": MAILS})
    alpha = _account(lace, "Alpha", [ContactRecord(name="Jane", email="jane@alpha.test")])
    omega = _account(lace, "Omega", [ContactRecord(name="Olu", email="olu@omega.test")])
    lace_runtime.append(AIMessage(content="Two drafts are ready."))

    run = client.portal.call(manager.start_lace_job, "lace_drafts", user.id, uuid.UUID(lace), {})
    client.portal.call(_wait_for_status, run.id, {"completed"})
    notes = {w[0]: (w[3] if len(w) > 3 else None) for w in written}
    assert "not a cold introduction" in notes["Alpha"] and notes["Omega"] is None
    with psycopg.connect(settings.database_url) as conn:
        rows = dict(conn.execute("SELECT id, temperature || ': ' || coalesce(temperature_reason, '') FROM lace_accounts"
                                 " WHERE id IN (%s, %s)", (alpha, omega)).fetchall())
    assert rows == {alpha: "warm: You've emailed them before (2 emails)", omega: "cold: "}
