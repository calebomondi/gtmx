"""Working on one draft with the Lace: the founder's message carries the
draft as it reads now, the Lace rewrites it with edit_draft, and the
exchange is tagged with the draft so its own panel can show it."""

import uuid

import psycopg
from langchain_core.messages import AIMessage, HumanMessage

from backend.app.runs import lace as lace_runs
from backend.tests.helpers import make_user
from backend.tests.test_lace_jobs import _call, _runs, _wait_for_turns, lace  # noqa: F401 -- fixture
from backend.tests.test_laces_api import API, lace_runtime  # noqa: F401 -- fixture
from config import settings


def _draft(lace_id, status="draft") -> str:
    with psycopg.connect(settings.database_url, autocommit=True) as conn:
        user_id = conn.execute("SELECT user_id FROM laces WHERE id = %s", (lace_id,)).fetchone()[0]
        return str(conn.execute(
            "INSERT INTO lace_outreach (id, lace_id, user_id, channel, recipient_name, recipient_company,"
            " recipient_address, subject, body, status) VALUES (%s, %s, %s, 'email', 'Kaleb', 'Thalace',"
            " 'kaleb@thalace.test', 'Your pilot', 'Hi Kaleb, long first draft.', %s) RETURNING id",
            (uuid.uuid4(), lace_id, user_id, status)).fetchone()[0])


def test_a_message_about_a_draft_carries_it_and_its_exchange_is_tagged(client, lace, lace_runtime):  # noqa: F811
    draft = _draft(lace)
    lace_runtime.extend([_call("edit_draft", {"draft_id": draft, "body": "Hi Kaleb, short one."}),
                         AIMessage(content="Cut it to one line and kept the ask.")])
    assert client.post(f"{API}/laces/{lace}/messages", json={"text": "make it shorter", "draft_id": draft}).status_code == 202
    [turn] = client.portal.call(_wait_for_turns, lace, 1)
    assert turn.input["draft_id"] == draft

    # The Lace read the draft as it stood, and how to change it.
    sent = [m for m in client.portal.call(lace_runs._thread, lace_runs.LaceThread(uuid.UUID(lace))) if isinstance(m, HumanMessage)][-1]
    assert "Hi Kaleb, long first draft." in sent.content and f"edit_draft (draft_id {draft})" in sent.content
    with psycopg.connect(settings.database_url) as conn:
        assert conn.execute("SELECT body FROM lace_outreach WHERE id = %s", (draft,)).fetchone()[0] == "Hi Kaleb, short one."

    founder, reply = client.get(f"{API}/laces/{lace}/messages").json()[-2:]
    founder.pop("author")  # who sent it: covered in test_lace_members
    assert founder == {"role": "founder", "content": "make it shorter", "draft_id": draft}
    assert reply == {"role": "lace", "content": "Cut it to one line and kept the ask.", "draft_id": draft}

    # The next ordinary message is not about the draft.
    lace_runtime.append(AIMessage(content="Sure."))
    client.post(f"{API}/laces/{lace}/messages", json={"text": "thanks"})
    client.portal.call(_wait_for_turns, lace, 2)
    assert all("draft_id" not in m for m in client.get(f"{API}/laces/{lace}/messages").json()[-2:])


def test_only_this_laces_unsent_drafts_can_be_worked_on(client, lace, lace_runtime):  # noqa: F811
    sent = _draft(lace, status="sent")
    refused = client.post(f"{API}/laces/{lace}/messages", json={"text": "shorter", "draft_id": sent})
    assert refused.status_code == 409 and "already been sent" in refused.json()["detail"]
    assert client.post(f"{API}/laces/{lace}/messages", json={"text": "x", "draft_id": str(uuid.uuid4())}).status_code == 404
    draft = _draft(lace)
    client.sign_in(make_user("Intruder"))
    assert client.post(f"{API}/laces/{lace}/messages", json={"text": "x", "draft_id": draft}).status_code == 404
    assert client.portal.call(_runs, lace, "lace_turn") == []
