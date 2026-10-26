"""The app's feedback button: a user sends feedback with the page and Lace
they were on (only a Lace of theirs is kept), within a daily cap; admins
read it, newest first, and mark it read, audited."""

import uuid

import psycopg

from backend.app.services import feedback as feedback_service
from backend.tests.helpers import make_user
from backend.tests.test_lace_jobs import lace  # noqa: F401 -- fixture
from backend.tests.test_laces_api import API, lace_runtime  # noqa: F401 -- fixture
from config import settings


def _send(client, text, **extra):
    return client.post(f"{API}/feedback", json={"text": text, **extra})


def test_feedback_keeps_the_page_and_only_the_user_s_own_lace(client, user, lace):  # noqa: F811
    assert _send(client, "  The Feed is great.  ", path=f"/lace/{lace}/feed", lace_id=lace).status_code == 201
    assert _send(client, "Someone else's Lace", lace_id=str(uuid.uuid4())).status_code == 201
    assert _send(client, "").status_code == 422
    assert _send(client, "   ").status_code == 422
    assert _send(client, "x" * 2001).status_code == 422
    with psycopg.connect(settings.database_url) as conn:
        rows = conn.execute("SELECT text, path, lace_id, email, status FROM feedback ORDER BY created_at").fetchall()
    assert rows == [("The Feed is great.", f"/lace/{lace}/feed", uuid.UUID(lace), user.email, "new"),
                    ("Someone else's Lace", None, None, user.email, "new")]


def test_feedback_has_a_daily_cap(client, monkeypatch):
    monkeypatch.setattr(feedback_service, "MAX_PER_DAY", 2)
    assert [_send(client, f"Idea {i}").status_code for i in range(3)] == [201, 201, 429]


def test_admins_read_feedback_and_mark_it_read(client, lace):  # noqa: F811
    _send(client, "Drafts are too long.", lace_id=lace)
    _send(client, "Love the brief.")
    client.sign_in(make_user("Boss", is_admin=True))
    page = client.get(f"{API}/admin/feedback").json()
    assert [(f["text"], f["lace_name"]) for f in page["items"]] == [("Love the brief.", None),
                                                                    ("Drafts are too long.", "Ada")]
    drafts = page["items"][1]
    read = client.patch(f"{API}/admin/feedback/{drafts['id']}", json={"status": "read"}).json()
    assert read["status"] == "read" and read["read_at"]
    assert [f["text"] for f in client.get(f"{API}/admin/feedback", params={"status": "new"}).json()["items"]] == [
        "Love the brief."]
    assert client.get(f"{API}/admin/feedback", params={"q": "drafts"}).json()["total"] == 1
    with psycopg.connect(settings.database_url) as conn:
        assert conn.execute("SELECT action FROM admin_audit_log").fetchall() == [("feedback.status",)]
    assert client.patch(f"{API}/admin/feedback/{uuid.uuid4()}", json={"status": "read"}).status_code == 404


def test_feedback_is_admin_only_to_read(client):
    assert client.get(f"{API}/admin/feedback").status_code == 403
