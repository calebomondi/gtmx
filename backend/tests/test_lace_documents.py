"""Documents a founder shares with their Lace: uploaded and kept as text,
attached to a message, read by the Lace, and shown back as attachments."""

import uuid
from functools import partial

from langchain_core.messages import AIMessage

from agents.lace.graph import build_lace_graph
from backend.app.runs import lace as lace_runs
from backend.tests.helpers import make_user
from backend.tests.test_lace_jobs import lace  # noqa: F401 -- fixture
from backend.tests.test_laces_api import API, lace_runtime  # noqa: F401 -- fixture
from backend.tests.test_runs import _wait_for_status
from config import settings


def _upload(client, lace_id, name="notes.md", data=b"# Pricing\nKES 1,500 per truck a month."):
    return client.post(f"{API}/laces/{lace_id}/documents", files={"file": (name, data, "text/markdown")})


def test_upload_list_and_delete(client, lace):  # noqa: F811
    uploaded = _upload(client, lace)
    assert uploaded.status_code == 201
    doc = uploaded.json()
    assert (doc["filename"], doc["size_bytes"], doc["truncated"]) == ("notes.md", 38, False)
    assert [d["id"] for d in client.get(f"{API}/laces/{lace}/documents").json()] == [doc["id"]]
    assert client.delete(f"{API}/laces/{lace}/documents/{doc['id']}").status_code == 204
    assert client.get(f"{API}/laces/{lace}/documents").json() == []


def test_what_cannot_be_kept_is_refused_with_a_reason(client, lace, monkeypatch):  # noqa: F811
    assert "Try PDF" in _upload(client, lace, "setup.exe", b"MZ").json()["detail"]
    assert "no text" in _upload(client, lace, "blank.txt", b"  ").json()["detail"]
    monkeypatch.setattr(settings, "lace_document_max_chars", 10)
    assert _upload(client, lace).json()["truncated"] is True
    monkeypatch.setattr(settings, "max_documents_per_lace", 1)
    assert _upload(client, lace).status_code == 409
    monkeypatch.setattr(settings, "lace_document_max_mb", 0)
    assert "over 0 MB" in _upload(client, lace).json()["detail"]


def test_another_users_documents_stay_theirs(client, lace):  # noqa: F811
    doc = _upload(client, lace).json()
    client.sign_in(make_user("Intruder"))
    assert client.get(f"{API}/laces/{lace}/documents").status_code == 404
    assert client.delete(f"{API}/laces/{lace}/documents/{doc['id']}").status_code == 404


def test_an_attached_document_reaches_the_lace_and_shows_in_the_chat(client, lace, monkeypatch):  # noqa: F811
    doc = _upload(client, lace).json()
    seen: list = []

    def model_step(messages, tools, sink):
        seen.append(messages)
        return AIMessage(content="Your pricing is KES 1,500 per truck.")
    monkeypatch.setattr(lace_runs, "build_lace_graph", partial(build_lace_graph, model_step=model_step))

    sent = client.post(f"{API}/laces/{lace}/messages", json={"text": "What do we charge?", "document_ids": [doc["id"]]})
    client.portal.call(_wait_for_status, uuid.UUID(sent.json()["run_id"]), {"completed"})

    system, *_, asked = seen[0]
    assert f"- notes.md (id {doc['id']})" in system.content
    assert asked.content.startswith("What do we charge?") and f"notes.md (document id {doc['id']})" in asked.content
    founder = [m for m in client.get(f"{API}/laces/{lace}/messages").json() if m["role"] == "founder"][-1]
    assert founder == {"role": "founder", "content": "What do we charge?",
                       "documents": [{"id": doc["id"], "filename": "notes.md"}]}


def test_a_message_needs_words_or_a_document_of_this_lace(client, lace):  # noqa: F811
    assert client.post(f"{API}/laces/{lace}/messages", json={"text": " "}).status_code == 422
    stranger = str(uuid.uuid4())
    assert client.post(f"{API}/laces/{lace}/messages", json={"document_ids": [stranger]}).status_code == 404
