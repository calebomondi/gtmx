"""A Lace's outreach drafts: written in the background to the right person,
saved for the founder to edit or discard, never sent by the Lace."""

import json
import uuid
from datetime import UTC, datetime

import psycopg
from langchain_core.messages import AIMessage

from agents.schemas.accounts import AccountRecord, ContactRecord, TriggerEvent
from agents.schemas.outreach import OutreachDraft
from backend.app.runs import lace_jobs
from backend.app.runs import manager
from backend.app.services.lace_contacts import contact_key
from backend.tests.helpers import make_user
from backend.tests.test_lace_jobs import _wait_for_turns, lace  # noqa: F401 -- fixture
from backend.tests.test_laces_api import API, lace_runtime  # noqa: F401 -- fixture
from backend.tests.test_runs import _wait_for_status
from config import settings


def _account(lace_id, name, contacts, status="person", strength="strong", approved=True) -> uuid.UUID:
    """A saved target account with its people on file, cleared for outreach
    unless `approved` is False."""
    record = AccountRecord(name=name, website=f"https://{name.lower()}.test", key_contacts=contacts,
                           trigger_event=TriggerEvent(event="Raised", signal_type="funding_round", source="https://n.test"))
    with psycopg.connect(settings.database_url, autocommit=True) as conn:
        account_id = conn.execute(
            "INSERT INTO lace_accounts (id, lace_id, key, name, account_type, record, contact_status, fit_strength)"
            " VALUES (%s, %s, %s, %s, 'company', %s, %s, %s) RETURNING id",
            (uuid.uuid4(), lace_id, name.lower(), name, json.dumps(record.model_dump(mode="json")), status, strength),
        ).fetchone()[0]
        for c in contacts:
            conn.execute("INSERT INTO lace_contacts (id, lace_id, account_id, key, name, email, linkedin, x, instagram,"
                         " facebook, tiktok, source, approved_at)"
                         " VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 'discovery', %s)",
                         (uuid.uuid4(), lace_id, account_id, contact_key(c), c.name, c.email, c.linkedin, c.x,
                          c.instagram, c.facebook, c.tiktok, datetime.now(UTC) if approved else None))
    return account_id


def _stub_writer(monkeypatch, fail_for=()):
    written = []

    def draft(profile, facts, rivals, record, recipient, sender, note=None):
        if record.name in fail_for:
            raise RuntimeError("provider down")
        written.append((record.name, recipient.address, sender) + ((note,) if note else ()))
        return OutreachDraft(subject=f"About {record.name}", body=f"Hi {recipient.name or 'there'}, ... {sender}")

    async def sender(user_id):
        return "Caleb"

    monkeypatch.setattr(lace_jobs, "draft_first_touch", draft)
    monkeypatch.setattr(lace_jobs.outreach_service, "sender_for_user", sender)
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
    assert "Drafting failed for (try again later): Broken" in update
    drafts = {d["recipient_company"]: d for d in client.get(f"{API}/laces/{lace}/outreach").json()}
    # Each draft is named by id, so the Lace can show it as a card.
    assert f"Alpha [draft {drafts['Alpha']['id']}]: to Jane Doe by email" in update
    assert f"Beta [draft {drafts['Beta']['id']}]: to Tom by linkedin" in update
    assert set(drafts) == {"Alpha", "Beta"} and all(d["status"] == "draft" for d in drafts.values())
    assert drafts["Alpha"]["subject"] == "About Alpha" and drafts["Beta"]["channel"] == "linkedin"


def test_nothing_is_drafted_to_people_not_yet_approved(client, lace, lace_runtime, user, monkeypatch):  # noqa: F811
    written = _stub_writer(monkeypatch)
    waiting = _account(lace, "Waiting", [ContactRecord(name="Jane Doe", email="jane@waiting.test"),
                                         ContactRecord(name="Tom", linkedin="https://linkedin.com/in/tom")],
                       approved=False)
    lace_runtime.append(AIMessage(content="Approve the people at Waiting first."))
    run = client.portal.call(manager.start_lace_job, "lace_drafts", user.id, uuid.UUID(lace), {})
    client.portal.call(_wait_for_status, run.id, {"completed"})
    turns = client.portal.call(_wait_for_turns, lace, 1)
    assert written == []
    assert "No message was drafted" in turns[-1].input["updates"][0]
    assert "wait for the founder to approve them" in turns[-1].input["updates"][0]

    # One click clears both; the next draft goes to the best of them.
    assert client.post(f"{API}/laces/{lace}/accounts/{waiting}/contacts/approve").json() == {"approved": 2}
    lace_runtime.append(AIMessage(content="Drafted to Jane."))
    run = client.portal.call(manager.start_lace_job, "lace_drafts", user.id, uuid.UUID(lace), {})
    client.portal.call(_wait_for_status, run.id, {"completed"})
    assert written == [("Waiting", "jane@waiting.test", "Caleb")]
    client.portal.call(_wait_for_turns, lace, 2)


def test_only_approved_people_are_written_to(client, lace, lace_runtime, user, monkeypatch):  # noqa: F811
    written = _stub_writer(monkeypatch)
    account = _account(lace, "Mixed", [ContactRecord(name="Jane Doe", email="jane@mixed.test"),
                                       ContactRecord(name="Tom", linkedin="https://linkedin.com/in/tom")],
                       approved=False)
    contacts = {c["name"]: c for c in client.get(f"{API}/laces/{lace}/contacts").json()}
    approved = client.patch(f"{API}/laces/{lace}/contacts/{contacts['Tom']['id']}", json={"approved": True}).json()
    assert approved["approved_at"] is not None and approved["account_name"] == "Mixed"
    lace_runtime.append(AIMessage(content="Drafted to Tom."))
    run = client.portal.call(manager.start_lace_job, "lace_drafts", user.id, uuid.UUID(lace), {"account_ids": [str(account)]})
    client.portal.call(_wait_for_status, run.id, {"completed"})
    assert written == [("Mixed", "https://linkedin.com/in/tom", "Caleb")]  # not Jane, who was not approved
    client.portal.call(_wait_for_turns, lace, 1)
    client.sign_in(make_user("Intruder"))
    assert client.patch(f"{API}/laces/{lace}/contacts/{contacts['Tom']['id']}", json={"approved": False}).status_code == 404
    assert client.post(f"{API}/laces/{lace}/accounts/{account}/contacts/approve").status_code == 404


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


def _message(lace_id, user_id, channel="email", status="draft", address="jane@alpha.test", subject="Hi"):
    with psycopg.connect(settings.database_url, autocommit=True) as conn:
        return conn.execute(
            "INSERT INTO lace_outreach (id, lace_id, user_id, channel, recipient_address, subject, body, status)"
            " VALUES (%s, %s, %s, %s, %s, %s, 'Hello Jane', %s) RETURNING id",
            (uuid.uuid4(), lace_id, user_id, channel, address, subject, status)).fetchone()[0]


def _gmail(monkeypatch, connected=True, error=None):
    from backend.app.services import connections as connection_service
    from backend.app.services.connections import ConnectionInfo
    calls = []

    async def connections(db, user_id):
        return [ConnectionInfo("ca_1", "gmail", "live", "me@acme.example", None, None)] if connected else []

    def execute(user_id, tool, arguments, connection_id):
        calls.append((tool, arguments))
        return {"data": None if error else {"id": "m_1", "threadId": "t_1"}, "error": error, "log_id": "log_1"}

    monkeypatch.setattr(connection_service, "list_for_user", connections)
    monkeypatch.setattr(connection_service, "execute_tool", execute)
    return calls


def test_the_founders_click_sends_through_their_gmail(client, lace, lace_runtime, user, monkeypatch):  # noqa: F811
    calls = _gmail(monkeypatch)
    message = _message(lace, user.id)
    sent = client.post(f"{API}/laces/{lace}/outreach/{message}/send")
    assert sent.status_code == 200
    body = sent.json()
    assert body["status"] == "sent" and body["sent_at"]
    assert calls == [("GMAIL_SEND_EMAIL", {"recipient_email": "jane@alpha.test", "subject": "Hi", "body": "Hello Jane"})]
    with psycopg.connect(settings.database_url) as conn:
        assert conn.execute("SELECT thread_id, provider_log_id FROM lace_outreach WHERE id = %s",
                            (message,)).fetchone() == ("t_1", "log_1")
    # Sent once: a second click can't send it again.
    assert client.post(f"{API}/laces/{lace}/outreach/{message}/send").status_code == 409
    assert len(calls) == 1


def test_sending_needs_gmail_an_address_and_an_email(client, lace, lace_runtime, user, monkeypatch):  # noqa: F811
    _gmail(monkeypatch, connected=False)
    assert "Connect your Gmail" in client.post(f"{API}/laces/{lace}/outreach/{_message(lace, user.id)}/send").json()["detail"]
    _gmail(monkeypatch)
    no_address = _message(lace, user.id, address=None)
    assert client.post(f"{API}/laces/{lace}/outreach/{no_address}/send").status_code == 422
    linkedin = _message(lace, user.id, channel="linkedin", address="https://linkedin.com/in/jane")
    assert client.post(f"{API}/laces/{lace}/outreach/{linkedin}/send").status_code == 409


def test_a_rejected_send_is_recorded_and_can_be_retried(client, lace, lace_runtime, user, monkeypatch):  # noqa: F811
    _gmail(monkeypatch, error="invalid to")
    message = _message(lace, user.id)
    failed = client.post(f"{API}/laces/{lace}/outreach/{message}/send").json()
    assert failed["status"] == "failed" and "Gmail rejected" in failed["error"]
    _gmail(monkeypatch)
    assert client.post(f"{API}/laces/{lace}/outreach/{message}/send").json()["status"] == "sent"


def test_linkedin_messages_are_marked_sent_by_hand(client, lace, lace_runtime, user):  # noqa: F811
    linkedin = _message(lace, user.id, channel="linkedin", address="https://linkedin.com/in/jane")
    marked = client.post(f"{API}/laces/{lace}/outreach/{linkedin}/mark-sent").json()
    assert marked["status"] == "sent" and marked["sent_at"]
    assert client.post(f"{API}/laces/{lace}/outreach/{linkedin}/mark-sent").status_code == 409
    assert client.post(f"{API}/laces/{lace}/outreach/{_message(lace, user.id)}/mark-sent").status_code == 409


def test_the_daily_cap_counts_lace_and_workspace_sends(client, lace, lace_runtime, user, monkeypatch):  # noqa: F811
    _gmail(monkeypatch)
    monkeypatch.setattr(settings, "max_outreach_sends_per_day", 1)
    with psycopg.connect(settings.database_url, autocommit=True) as conn:
        conn.execute("UPDATE lace_outreach SET status = 'sent', sent_at = now() WHERE id = %s",
                     (_message(lace, user.id),))
    assert client.post(f"{API}/laces/{lace}/outreach/{_message(lace, user.id)}/send").status_code == 429


def test_another_users_message_cannot_be_sent(client, lace, lace_runtime, user, monkeypatch):  # noqa: F811
    calls = _gmail(monkeypatch)
    message = _message(lace, user.id)
    client.sign_in(make_user("Intruder"))
    assert client.post(f"{API}/laces/{lace}/outreach/{message}/send").status_code == 404
    assert calls == []


def _x(monkeypatch, connected=True, user_id="123", send_error=None):
    from backend.app.services import connections as connection_service
    from backend.app.services.connections import ConnectionInfo
    calls = []

    async def connections(db, user_id_):
        return [ConnectionInfo("ca_x", "x", "live", "@me", None, None)] if connected else []

    def execute(user_id_, tool, arguments, connection_id):
        calls.append((tool, arguments))
        if tool == "TWITTER_USER_LOOKUP_BY_USERNAME":
            return {"data": {"data": {"id": user_id}} if user_id else {}, "error": None if user_id else "not found",
                    "log_id": "l1"}
        return {"data": None if send_error else {"data": {"dm_event_id": "e_1"}}, "error": send_error, "log_id": "l2"}

    monkeypatch.setattr(connection_service, "list_for_user", connections)
    monkeypatch.setattr(connection_service, "execute_tool", execute)
    return calls


def test_an_x_dm_is_sent_through_x_on_the_founders_click(client, lace, lace_runtime, user, monkeypatch):  # noqa: F811
    calls = _x(monkeypatch)
    message = _message(lace, user.id, channel="x", address="https://x.com/EnziMotors", subject=None)
    sent = client.post(f"{API}/laces/{lace}/outreach/{message}/send").json()
    assert sent["status"] == "sent" and sent["sent_at"]
    assert calls == [("TWITTER_USER_LOOKUP_BY_USERNAME", {"username": "EnziMotors"}),
                     ("TWITTER_SEND_A_NEW_MESSAGE_TO_A_USER", {"participant_id": "123", "text": "Hello Jane"})]
    with psycopg.connect(settings.database_url) as conn:
        assert conn.execute("SELECT provider_message_id, provider_log_id FROM lace_outreach WHERE id = %s",
                            (message,)).fetchone() == ("e_1", "l2")
    assert client.post(f"{API}/laces/{lace}/outreach/{message}/send").status_code == 409  # sent once


def test_x_refusals_are_clear(client, lace, lace_runtime, user, monkeypatch):  # noqa: F811
    _x(monkeypatch, connected=False)
    no_x = _message(lace, user.id, channel="x", address="https://x.com/EnziMotors")
    assert "Connect your X account" in client.post(f"{API}/laces/{lace}/outreach/{no_x}/send").json()["detail"]
    _x(monkeypatch)
    bad = _message(lace, user.id, channel="x", address="https://x.com/i/status/1")
    assert client.post(f"{API}/laces/{lace}/outreach/{bad}/send").status_code == 422
    _x(monkeypatch, user_id=None)
    unknown = client.post(f"{API}/laces/{lace}/outreach/{no_x}/send").json()
    assert unknown["status"] == "failed" and "Couldn't find @EnziMotors" in unknown["error"]
    _x(monkeypatch, send_error="dm not allowed")
    refused = client.post(f"{API}/laces/{lace}/outreach/{no_x}/send").json()
    assert refused["status"] == "failed" and "may not accept DMs" in refused["error"]


def test_other_social_channels_are_handed_to_the_founder(client, lace, lace_runtime, user):  # noqa: F811
    for channel, words in (("instagram", "Instagram doesn't let apps start"), ("facebook", "only lets a Page reply"),
                           ("tiktok", "TikTok has no messaging")):
        message = _message(lace, user.id, channel=channel, address=f"https://{channel}.com/enzi")
        refused = client.post(f"{API}/laces/{lace}/outreach/{message}/send")
        assert refused.status_code == 409 and words in refused.json()["detail"]
        assert client.post(f"{API}/laces/{lace}/outreach/{message}/mark-sent").json()["status"] == "sent"


def test_x_sends_count_toward_the_daily_cap(client, lace, lace_runtime, user, monkeypatch):  # noqa: F811
    _gmail(monkeypatch)
    monkeypatch.setattr(settings, "max_outreach_sends_per_day", 1)
    with psycopg.connect(settings.database_url, autocommit=True) as conn:
        conn.execute("UPDATE lace_outreach SET status = 'sent', sent_at = now() WHERE id = %s",
                     (_message(lace, user.id, channel="x", address="https://x.com/a"),))
    assert client.post(f"{API}/laces/{lace}/outreach/{_message(lace, user.id)}/send").status_code == 429


def test_a_draft_to_one_person_uses_their_channel_and_the_founders_note(client, lace, lace_runtime, user, monkeypatch):  # noqa: F811
    written = _stub_writer(monkeypatch)
    _account(lace, "Twiga", [ContactRecord(name="Amina", email="amina@twiga.test", linkedin="https://linkedin.com/in/amina"),
                             ContactRecord(name="Peter", email="peter@twiga.test")], approved=False)
    with psycopg.connect(settings.database_url) as conn:
        amina = str(conn.execute("SELECT id FROM lace_contacts WHERE name = 'Amina'").fetchone()[0])
    lace_runtime.append(AIMessage(content="I drafted a LinkedIn note to Amina."))

    started = client.post(f"{API}/laces/{lace}/contacts/{amina}/draft",
                          json={"channel": "linkedin", "note": "Mention our Twiga pilot"})
    assert started.status_code == 202
    client.portal.call(_wait_for_status, uuid.UUID(started.json()["run_id"]), {"completed"})
    assert written == [("Twiga", "https://linkedin.com/in/amina", "Caleb", "Mention our Twiga pilot")]
    with psycopg.connect(settings.database_url) as conn:
        assert conn.execute("SELECT channel, recipient_name FROM lace_outreach").fetchall() == [("linkedin", "Amina")]
        # Asking for the draft cleared her; Peter still waits.
        assert conn.execute("SELECT name FROM lace_contacts WHERE approved_at IS NOT NULL").fetchall() == [("Amina",)]


def test_a_draft_needs_a_way_to_reach_them_and_a_contact_of_this_lace(client, lace, lace_runtime, user):  # noqa: F811
    _account(lace, "Twiga", [ContactRecord(name="Peter", email="peter@twiga.test")])
    with psycopg.connect(settings.database_url) as conn:
        peter = str(conn.execute("SELECT id FROM lace_contacts WHERE name = 'Peter'").fetchone()[0])
    missing = client.post(f"{API}/laces/{lace}/contacts/{peter}/draft", json={"channel": "linkedin"})
    assert missing.status_code == 422 and "LinkedIn" in missing.json()["detail"]
    client.sign_in(make_user("Intruder"))
    assert client.post(f"{API}/laces/{lace}/contacts/{peter}/draft", json={"channel": "email"}).status_code == 404


def test_a_draft_can_go_to_a_persons_own_social_account(client, lace, lace_runtime, user, monkeypatch):  # noqa: F811
    written = _stub_writer(monkeypatch)
    _account(lace, "Twiga", [ContactRecord(name="Amina", email="amina@twiga.test", instagram="@amina.k",
                                           x="https://x.com/amina")])
    with psycopg.connect(settings.database_url) as conn:
        amina = str(conn.execute("SELECT id FROM lace_contacts WHERE name = 'Amina'").fetchone()[0])
    assert client.post(f"{API}/laces/{lace}/contacts/{amina}/draft", json={"channel": "tiktok"}).json()["detail"] \
        == "There's no TikTok account for this person."
    lace_runtime.append(AIMessage(content="I drafted an Instagram note to Amina."))
    started = client.post(f"{API}/laces/{lace}/contacts/{amina}/draft", json={"channel": "instagram"})
    client.portal.call(_wait_for_status, uuid.UUID(started.json()["run_id"]), {"completed"})
    assert written[0][1] == "https://www.instagram.com/amina.k"
    with psycopg.connect(settings.database_url) as conn:
        assert conn.execute("SELECT channel, recipient_address FROM lace_outreach").fetchall() == [
            ("instagram", "https://www.instagram.com/amina.k")]
