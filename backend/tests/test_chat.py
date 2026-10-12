"""Workspace chat: replies are produced by a `chat` run, grounded in the
workspace's data, one at a time, owner-only, and failures stay in the chat."""

import asyncio
import uuid

from backend.app.runs import background, manager
from backend.tests.helpers import make_user
from backend.tests.test_runs import _wait_for_status

API = "/api/v1"


async def _drain():
    if manager._tasks:
        await asyncio.gather(*manager._tasks.values(), return_exceptions=True)


def test_reply_is_grounded_and_stored(client, owned, monkeypatch):
    seen = {}

    def fake_answer(question, history, context):
        seen.update(question=question, context=context, history=history)
        return background.workspace_chat.ChatAnswer(domain="competition", content=f"Answer to: {question}")
    monkeypatch.setattr(background.workspace_chat, "answer", fake_answer)

    path = f"{API}/workspaces/{owned['workspace']}/chat"
    sent = client.post(path, json={"message": "Who are my top rivals?"})
    assert sent.status_code == 202
    client.portal.call(_wait_for_status, uuid.UUID(sent.json()["reply_run"]["id"]), {"completed"})
    client.portal.call(_drain)

    thread = client.get(path).json()
    assert [(m["role"], m["content"], m["specialist_domain"]) for m in thread["messages"]] == [
        ("user", "Who are my top rivals?", None), ("assistant", "Answer to: Who are my top rivals?", "competition"),
    ]
    assert thread["reply_run"] is None
    assert "rival.example" in seen["context"].research["competition"]  # tracked competitors reach that specialist
    assert seen["history"] == []

    second = client.post(path, json={"message": "And their weaknesses?"}).json()
    client.portal.call(_wait_for_status, uuid.UUID(second["reply_run"]["id"]), {"completed"})
    client.portal.call(_drain)
    assert [r for r, _ in seen["history"]] == ["user", "assistant"]


def test_one_reply_at_a_time_and_ownership(client, owned, monkeypatch):
    gate = {"open": False}

    def slow_answer(*_):
        import time
        while not gate["open"]:
            time.sleep(0.02)
        return background.workspace_chat.ChatAnswer(domain="gtm", content="done")
    monkeypatch.setattr(background.workspace_chat, "answer", slow_answer)
    path = f"{API}/workspaces/{owned['workspace']}/chat"
    run_id = client.post(path, json={"message": "first"}).json()["reply_run"]["id"]
    assert client.post(path, json={"message": "second"}).status_code == 409
    gate["open"] = True
    client.portal.call(_wait_for_status, uuid.UUID(run_id), {"completed"})
    client.portal.call(_drain)

    client.sign_in(make_user("Intruder"))
    assert client.get(path).status_code == 404
    assert client.post(path, json={"message": "hi"}).status_code == 404


def test_failed_reply_is_shown_in_chat_not_feed(client, owned, monkeypatch):
    def boom(*_):
        raise RuntimeError("model exploded with internals")
    monkeypatch.setattr(background.workspace_chat, "answer", boom)
    path = f"{API}/workspaces/{owned['workspace']}/chat"
    run_id = client.post(path, json={"message": "hello"}).json()["reply_run"]["id"]
    client.portal.call(_wait_for_status, uuid.UUID(run_id), {"failed"})
    client.portal.call(_drain)

    thread = client.get(path).json()
    assert thread["reply_run"]["status"] == "failed" and "internals" not in thread["reply_run"]["error"]
    assert client.get(f"{API}/signals").json() == []
