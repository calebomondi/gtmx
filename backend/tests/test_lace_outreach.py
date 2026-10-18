"""A Lace's outreach drafts: written in the background to the right person,
saved for the founder to edit or discard, never sent by the Lace."""

import json
import uuid

import psycopg
from langchain_core.messages import AIMessage

from agents.schemas.accounts import AccountRecord, ContactRecord, TriggerEvent
from agents.schemas.outreach import OutreachDraft
from backend.app.runs import lace as lace_runs
from backend.app.runs import manager
from backend.tests.helpers import make_user
from backend.tests.test_lace_jobs import _wait_for_turns, lace  # noqa: F401 -- fixture
from backend.tests.test_laces_api import API, lace_runtime  # noqa: F401 -- fixture
from backend.tests.test_runs import _wait_for_status
from config import settings


def _account(lace_id, name, contacts, status="person", strength="strong") -> uuid.UUID:
    record = AccountRecord(name=name, website=f"https://{name.lower()}.test", key_contacts=contacts,
                           trigger_event=TriggerEvent(event="Raised", signal_type="funding_round", source="https://n.test"))
    with psycopg.connect(settings.database_url, autocommit=True) as conn:
        return conn.execute(
            "INSERT INTO lace_accounts (id, lace_id, key, name, account_type, record, contact_status, fit_strength)"
            " VALUES (%s, %s, %s, %s, 'company', %s, %s, %s) RETURNING id",
            (uuid.uuid4(), lace_id, name.lower(), name, json.dumps(record.model_dump(mode="json")), status, strength),
        ).fetchone()[0]


def _stub_writer(monkeypatch, fail_for=()):
    written = []

    def draft(profile, facts, rivals, record, recipient, sender):
        if record.name in fail_for:
            raise RuntimeError("provider down")
        written.append((record.name, recipient.address, sender))
        return OutreachDraft(subject=f"About {record.name}", body=f"Hi {recipient.name or 'there'}, ... {sender}")

    async def sender(user_id):
        return "Caleb"

    monkeypatch.setattr(lace_runs, "draft_first_touch", draft)
    monkeypatch.setattr(lace_runs.outreach_service, "sender_for_user", sender)
    return written


def test_drafts_go_to_the_best_person_and_wait_for_the_founder(client, lace, lace_runtime, user, monkeypatch):  # noqa: F811
    written = _stub_writer(monkeypatch, fail_for=("Broken",))
    _account(lace, "Alpha", [ContactRecord(name="Jane Doe", email="jane@alpha.test")])
    _account(lace, "Beta", [ContactRecord(name="Tom", linkedin="https://linkedin.com/in/tom")], strength="weak")
    _account(lace, "Broken", [ContactRecord(email="info@broken.test")], status="organisation")
    _account(lace, "Nobody", [], status="none")
    lace_runtime.append(AIMessage(content="Two drafts are ready for you."))

    run = client.portal.call(manager.start_lace_job, "lace_drafts", user.id, uuid.UUID(lace), {})
    run = client.portal.call(_wait_for_status, run.id, {"completed"})
    turns = client.portal.call(_wait_for_turns, lace, 1)

    assert sorted(written) == [("Alpha", "jane@alpha.test", "Caleb"), ("Beta", "https://linkedin.com/in/tom", "Caleb")]
    assert run.progress == {"drafted": 2, "unreachable": 0}
    update = turns[-1].input["updates"][0]
    assert "Alpha: to Jane Doe by email" in update and "Beta: to Tom by linkedin" in update
    assert "Drafting failed for (try again later): Broken" in update
    drafts = {d["recipient_company"]: d for d in client.get(f"{API}/laces/{lace}/outreach").json()}
    assert set(drafts) == {"Alpha", "Beta"} and all(d["status"] == "draft" for d in drafts.values())
    assert drafts["Alpha"]["subject"] == "About Alpha" and drafts["Beta"]["channel"] == "linkedin"


def test_accounts_already_written_to_are_not_redrafted(client, lace, lace_runtime, user, monkeypatch):  # noqa: F811
    written = _stub_writer(monkeypatch)
    alpha = _account(lace, "Alpha", [ContactRecord(name="Jane Doe", email="jane@alpha.test")])
    with psycopg.connect(settings.database_url, autocommit=True) as conn:
        conn.execute("INSERT INTO lace_outreach (id, lace_id, user_id, account_id, channel, body) VALUES"
                     " (%s, %s, %s, %s, 'email', 'earlier')", (uuid.uuid4(), lace, user.id, alpha))
    lace_runtime.append(AIMessage(content="Nothing new to draft."))
    run = client.portal.call(manager.start_lace_job, "lace_drafts", user.id, uuid.UUID(lace), {})
    client.portal.call(_wait_for_status, run.id, {"completed"})
    assert written == []
    # Named explicitly, it is drafted again.
    lace_runtime.append(AIMessage(content="Redrafted."))
    run = client.portal.call(manager.start_lace_job, "lace_drafts", user.id, uuid.UUID(lace), {"account_ids": [str(alpha)]})
    client.portal.call(_wait_for_status, run.id, {"completed"})
    assert [w[0] for w in written] == ["Alpha"]
    client.portal.call(_wait_for_turns, lace, 2)  # both jobs' reports


def test_founder_edits_and_discards_drafts_but_not_sent_messages(client, lace, lace_runtime, user):  # noqa: F811
    with psycopg.connect(settings.database_url, autocommit=True) as conn:
        draft, sent = (conn.execute(
            "INSERT INTO lace_outreach (id, lace_id, user_id, channel, body, status) VALUES (%s, %s, %s, 'email', 'x', %s)"
            " RETURNING id", (uuid.uuid4(), lace, user.id, status)).fetchone()[0] for status in ("draft", "sent"))
    edited = client.patch(f"{API}/laces/{lace}/outreach/{draft}", json={"subject": "New", "recipient_address": "a@b.test"})
    assert edited.status_code == 200 and edited.json()["subject"] == "New" and edited.json()["recipient_address"] == "a@b.test"
    assert client.patch(f"{API}/laces/{lace}/outreach/{sent}", json={"body": "changed"}).status_code == 409
    assert client.delete(f"{API}/laces/{lace}/outreach/{sent}").status_code == 409
    assert client.delete(f"{API}/laces/{lace}/outreach/{draft}").status_code == 204
    assert [m["status"] for m in client.get(f"{API}/laces/{lace}/outreach").json()] == ["sent"]
    client.sign_in(make_user("Intruder"))
    assert client.get(f"{API}/laces/{lace}/outreach").status_code == 404
    assert client.patch(f"{API}/laces/{lace}/outreach/{sent}", json={"body": "x"}).status_code == 404
