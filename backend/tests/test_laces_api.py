"""The Lace API end to end, with the model and the website stubbed: create a
Lace, watch onboarding finish, chat with it, and keep other users out."""

import json
import uuid
from functools import partial

import psycopg
import pytest
from langchain_core.messages import AIMessage
from langgraph.checkpoint.memory import MemorySaver

from agents.lace.graph import build_lace_graph
from agents.schemas.lace import NewFact, OnboardingResult
from backend.app.runs import lace as lace_runs
from backend.app.runs import manager
from backend.tests.helpers import make_user
from backend.tests.test_runs import _wait_for_status
from config import settings

API = "/api/v1"


@pytest.fixture
def lace_runtime(monkeypatch):
    """A shared in-memory checkpointer, a fake onboarding, and a scripted
    model; `replies` is what the model says next."""
    saver = MemorySaver()
    replies: list[AIMessage] = []
    monkeypatch.setattr(lace_runs, "get_checkpointer", lambda: saver)

    async def fake_onboard(store, cfg, progress):
        progress(0.5, "Read 1 of 1 pages")
        await store.record_fact(NewFact(topic="offer", claim="Acme sells payroll to clinics.",
                                        source_url="https://acme.test/", confidence="high", origin="crawl"))
        await store.set_startup_name("Acme")
        return OnboardingResult(startup_name="Acme", pages_read=["https://acme.test/"], pages_failed=[],
                                facts_recorded=1, open_questions=["Who is the buyer?"])

    monkeypatch.setattr(lace_runs, "onboard", fake_onboard)
    monkeypatch.setattr(lace_runs, "opening_message", lambda system, result: "Hi, I'm Ada. Who is the buyer?")
    def model_step(messages, tools, sink):
        reply = replies.pop(0)
        for word in str(reply.content).split(" "):
            sink.token(word + " ")
        return reply

    monkeypatch.setattr(lace_runs, "build_lace_graph", partial(build_lace_graph, model_step=model_step))
    return replies


def _create(client, name="Ada", website="acme.test"):
    return client.post(f"{API}/laces", json={"name": name, "website": website})


def _events(client, run_id) -> list[dict]:
    with client.stream("GET", f"{API}/runs/{run_id}/events") as response:
        assert response.headers["content-type"].startswith("application/x-ndjson")
        return [json.loads(line) for line in response.iter_lines() if line]


def test_create_onboards_and_opens_the_conversation(client, lace_runtime):
    created = _create(client)
    assert created.status_code == 201
    body = created.json()
    assert body["lace"]["website"] == "https://acme.test" and body["lace"]["status"] == "onboarding"
    client.portal.call(_wait_for_status, uuid.UUID(body["run_id"]), {"completed"})

    lace_id = body["lace"]["id"]
    lace = client.get(f"{API}/laces/{lace_id}").json()
    assert lace["status"] == "active" and lace["startup_name"] == "Acme"
    assert [f["claim"] for f in client.get(f"{API}/laces/{lace_id}/facts").json()] == ["Acme sells payroll to clinics."]
    assert client.get(f"{API}/laces/{lace_id}/messages").json() == [
        {"role": "lace", "content": "Hi, I'm Ada. Who is the buyer?"}]
    frames = _events(client, body["run_id"])
    assert [f["type"] for f in frames][-2:] == ["message", "complete"]


def test_a_turn_streams_steps_and_the_reply(client, lace_runtime):
    body = _create(client).json()
    client.portal.call(_wait_for_status, uuid.UUID(body["run_id"]), {"completed"})
    lace_id = body["lace"]["id"]
    lace_runtime.extend([
        AIMessage(content="", tool_calls=[{"name": "record_fact", "id": "c1", "args": {
            "topic": "icp", "claim": "Buyers are clinic owners.", "from_founder": True}}]),
        AIMessage(content="Got it: clinic owners."),
    ])

    sent = client.post(f"{API}/laces/{lace_id}/messages", json={"text": "  clinic owners buy  "})
    assert sent.status_code == 202
    run_id = sent.json()["run_id"]
    client.portal.call(_wait_for_status, uuid.UUID(run_id), {"completed"})

    frames = _events(client, run_id)
    assert {"type": "step", "text": "Noting that down"}.items() <= next(f for f in frames if f["type"] == "step").items()
    result = next(f for f in frames if f["type"] == "tool_result")
    assert result["tool"] == "record_fact" and result["ok"]
    assert frames[-2]["content"] == "Got it: clinic owners."
    assert [{k: v for k, v in m.items() if k != "author"}
            for m in client.get(f"{API}/laces/{lace_id}/messages").json()[-2:]] == [
        {"role": "founder", "content": "clinic owners buy"},
        {"role": "lace", "content": "Got it: clinic owners."},
    ]
    topics = {f["topic"] for f in client.get(f"{API}/laces/{lace_id}/facts").json()}
    assert topics == {"offer", "icp"}
    assert [f["topic"] for f in client.get(f"{API}/laces/{lace_id}/facts?topic=icp").json()] == ["icp"]


def _busy_lace(client, user) -> tuple[str, uuid.UUID]:
    """A Lace in the middle of a turn: (its id, the turn's run id)."""
    body = _create(client).json()
    client.portal.call(_wait_for_status, uuid.UUID(body["run_id"]), {"completed"})
    busy = uuid.uuid4()
    with psycopg.connect(settings.database_url, autocommit=True) as conn:
        conn.execute("INSERT INTO runs (id, user_id, lace_id, kind, status) VALUES (%s, %s, %s, 'lace_turn', 'running')",
                     (busy, user.id, body["lace"]["id"]))
    return body["lace"]["id"], busy


def _finish(run_id: uuid.UUID) -> None:
    with psycopg.connect(settings.database_url, autocommit=True) as conn:
        conn.execute("UPDATE runs SET status = 'completed' WHERE id = %s", (run_id,))


def test_a_message_to_a_busy_lace_waits_its_turn(client, lace_runtime, user):
    lace_id, busy = _busy_lace(client, user)
    lace_runtime.append(AIMessage(content="Hello to you."))
    sent = client.post(f"{API}/laces/{lace_id}/messages", json={"text": "hello"})
    assert sent.status_code == 202 and sent.json()["queued"] is True
    waiting = client.get(f"{API}/laces/{lace_id}/messages").json()[-1]
    assert waiting["content"] == "hello" and waiting["queued"] is True and waiting["author"]["name"]

    _finish(busy)
    assert client.portal.call(manager.start_next_queued, uuid.UUID(lace_id)) is True
    client.portal.call(_wait_for_status, uuid.UUID(sent.json()["run_id"]), {"completed"})
    shown = client.get(f"{API}/laces/{lace_id}/messages").json()[-2:]
    assert [(m["content"], m.get("queued")) for m in shown] == [("hello", None), ("Hello to you.", None)]


def test_only_a_few_messages_can_wait(client, lace_runtime, user):
    lace_id, _ = _busy_lace(client, user)
    for n in range(manager.MAX_QUEUED_TURNS):
        assert client.post(f"{API}/laces/{lace_id}/messages", json={"text": f"m{n}"}).json()["queued"]
    refused = client.post(f"{API}/laces/{lace_id}/messages", json={"text": "one more"})
    assert refused.status_code == 409 and "already waiting" in refused.json()["detail"]


def test_waiting_messages_start_after_a_restart(client, lace_runtime, user):
    lace_id, busy = _busy_lace(client, user)
    lace_runtime.append(AIMessage(content="Back."))
    sent = client.post(f"{API}/laces/{lace_id}/messages", json={"text": "still there?"}).json()
    client.portal.call(manager.recover_after_restart)
    client.portal.call(_wait_for_status, uuid.UUID(sent["run_id"]), {"completed"})
    client.portal.call(_wait_for_status, busy, {"failed"})


def test_a_waiting_answer_to_a_closed_question_fails_and_the_next_runs(client, lace_runtime, user):
    lace_id, busy = _busy_lace(client, user)
    stale = uuid.uuid4()
    with psycopg.connect(settings.database_url, autocommit=True) as conn:
        conn.execute("INSERT INTO runs (id, user_id, lace_id, kind, status, input) "
                     "VALUES (%s, %s, %s, 'lace_turn', 'queued', %s)",
                     (stale, user.id, lace_id, json.dumps({"answer": {"block_id": "gone", "chosen": ["a"]},
                                                           "author": {"id": str(user.id), "name": "Ada"}})))
    lace_runtime.append(AIMessage(content="Noted."))
    sent = client.post(f"{API}/laces/{lace_id}/messages", json={"text": "next"}).json()
    _finish(busy)
    assert client.portal.call(manager.start_next_queued, uuid.UUID(lace_id)) is True
    client.portal.call(_wait_for_status, uuid.UUID(sent["run_id"]), {"completed"})
    client.portal.call(_wait_for_status, stale, {"failed"})


def test_blank_message_is_refused(client, lace_runtime):
    body = _create(client).json()
    client.portal.call(_wait_for_status, uuid.UUID(body["run_id"]), {"completed"})
    assert client.post(f"{API}/laces/{body['lace']['id']}/messages", json={"text": "   "}).status_code == 422


def test_other_users_lace_is_not_found(client, lace_runtime):
    body = _create(client).json()
    client.portal.call(_wait_for_status, uuid.UUID(body["run_id"]), {"completed"})
    lace_id = body["lace"]["id"]
    client.sign_in(make_user("Intruder"))
    for path in ("", "/facts", "/messages"):
        assert client.get(f"{API}/laces/{lace_id}{path}").status_code == 404
    assert client.post(f"{API}/laces/{lace_id}/messages", json={"text": "hi"}).status_code == 404
    assert client.get(f"{API}/runs/{body['run_id']}/events").status_code == 404
    assert client.get(f"{API}/laces").json() == []


def test_bad_website_is_refused_without_creating_a_lace(client, lace_runtime):
    assert _create(client, website="not a site").status_code == 422
    assert client.get(f"{API}/laces").json() == []


def test_lace_count_is_capped(client, lace_runtime, monkeypatch):
    monkeypatch.setattr(settings, "max_laces_per_user", 1)
    first = _create(client).json()
    client.portal.call(_wait_for_status, uuid.UUID(first["run_id"]), {"completed"})
    capped = _create(client, name="Second", website="second.test")
    assert capped.status_code == 409 and "already has a Lace" not in capped.json()["detail"]


async def test_live_subscribers_see_the_reply_stream_in(lace_runtime, user):
    import asyncio

    from backend.app.runs import events
    with psycopg.connect(settings.database_url, autocommit=True) as conn:
        lace_id = conn.execute("INSERT INTO laces (id, user_id, name, website) VALUES (%s, %s, 'Ada', 'https://acme.test')"
                               " RETURNING id", (uuid.uuid4(), user.id)).fetchone()[0]
        run_id = conn.execute("INSERT INTO runs (id, user_id, lace_id, kind, status) VALUES (%s, %s, %s, 'lace_turn',"
                              " 'running') RETURNING id", (uuid.uuid4(), user.id, lace_id)).fetchone()[0]
    lace_runtime.extend([
        AIMessage(content="Let me check.", tool_calls=[{"name": "get_facts", "id": "c1", "args": {}}]),
        AIMessage(content="Your buyers are clinic owners who run three or more sites."),
    ])
    frames: list[dict] = []

    async def collect():
        async for frame in events.subscribe(run_id):
            frames.append(frame)
            if frame["type"] == "complete":
                return

    collector = asyncio.create_task(collect())
    await asyncio.sleep(0.05)  # subscribed before the turn starts
    await lace_runs.turn_segment(run_id, lace_runs.LaceThread(lace_id), "who buys?")
    await asyncio.wait_for(collector, 5)

    types = [f["type"] for f in frames]
    # The pre-tool-call text leaves the reply box and stays in the trail,
    # ahead of the step it led to.
    assert types.index("token_reset") < types.index("step")
    steps = [f["text"] for f in frames if f["type"] == "step"]
    assert steps[:2] == ["Let me check.", "Checking what I know"]
    after_step = frames[types.index("step"):]
    streamed = "".join(f["text"] for f in after_step if f["type"] == "token")
    assert streamed.strip() == "Your buyers are clinic owners who run three or more sites."
    assert all(f["event_id"] is None for f in frames if f["type"].startswith("token"))
    # Reconnecting replays only stored frames: no tokens.
    stored = [f async for f in _stored(run_id)]
    assert not any(f["type"].startswith("token") for f in stored)


async def _stored(run_id):
    from backend.app.runs import events
    async for frame in events.subscribe(run_id):
        yield frame
        if frame["type"] == "complete":
            return


def test_competitors_list_and_dismiss(client, lace_runtime):
    body = _create(client).json()
    client.portal.call(_wait_for_status, uuid.UUID(body["run_id"]), {"completed"})
    lace_id = body["lace"]["id"]
    with psycopg.connect(settings.database_url, autocommit=True) as conn:
        rival = conn.execute("INSERT INTO lace_competitors (id, lace_id, name, website, domain_key, summary)"
                             " VALUES (%s, %s, 'Rival', 'https://rival.test', 'rival.test', 'Payroll for vets.') RETURNING id",
                             (uuid.uuid4(), lace_id)).fetchone()[0]
    [row] = client.get(f"{API}/laces/{lace_id}/competitors").json()
    assert row["name"] == "Rival" and row["status"] == "tracked" and row["origin"] == "found"

    dismissed = client.patch(f"{API}/laces/{lace_id}/competitors/{rival}", json={"status": "dismissed"})
    assert dismissed.status_code == 200 and dismissed.json()["status"] == "dismissed"
    assert client.get(f"{API}/laces/{lace_id}/competitors").json() == []
    assert [r["name"] for r in client.get(f"{API}/laces/{lace_id}/competitors?status=dismissed").json()] == ["Rival"]

    client.sign_in(make_user("Intruder"))
    assert client.get(f"{API}/laces/{lace_id}/competitors").status_code == 404
    assert client.patch(f"{API}/laces/{lace_id}/competitors/{rival}", json={"status": "tracked"}).status_code == 404


def test_another_laces_competitor_is_not_found(client, lace_runtime):
    mine = _create(client).json()
    client.portal.call(_wait_for_status, uuid.UUID(mine["run_id"]), {"completed"})
    other = _create(client, name="Bob", website="bob.test").json()
    client.portal.call(_wait_for_status, uuid.UUID(other["run_id"]), {"completed"})
    with psycopg.connect(settings.database_url, autocommit=True) as conn:
        theirs = conn.execute("INSERT INTO lace_competitors (id, lace_id, name, website, domain_key)"
                              " VALUES (%s, %s, 'Rival', 'https://rival.test', 'rival.test') RETURNING id",
                              (uuid.uuid4(), other["lace"]["id"])).fetchone()[0]
    assert client.patch(f"{API}/laces/{mine['lace']['id']}/competitors/{theirs}",
                        json={"status": "dismissed"}).status_code == 404


async def _live_frames(lace_runtime, user, monkeypatch, model_step) -> list[dict]:
    import asyncio

    from backend.app.runs import events
    with psycopg.connect(settings.database_url, autocommit=True) as conn:
        lace_id = conn.execute("INSERT INTO laces (id, user_id, name, website) VALUES (%s, %s, 'Ada', 'https://acme.test')"
                               " RETURNING id", (uuid.uuid4(), user.id)).fetchone()[0]
        run_id = conn.execute("INSERT INTO runs (id, user_id, lace_id, kind, status) VALUES (%s, %s, %s, 'lace_turn',"
                              " 'running') RETURNING id", (uuid.uuid4(), user.id, lace_id)).fetchone()[0]
    monkeypatch.setattr(lace_runs, "build_lace_graph", partial(build_lace_graph, model_step=model_step))
    frames: list[dict] = []

    async def collect():
        async for frame in events.subscribe(run_id):
            frames.append(frame)
            if frame["type"] == "complete":
                return

    collector = asyncio.create_task(collect())
    await asyncio.sleep(0.05)
    await lace_runs.turn_segment(run_id, lace_runs.LaceThread(lace_id), "who buys?")
    await asyncio.wait_for(collector, 5)
    return frames


async def test_a_retried_answer_says_so_instead_of_vanishing(lace_runtime, user, monkeypatch):
    def model_step(messages, tools, sink):
        sink.token("Your buyers are ")
        sink.reset()  # the call failed; the ladder starts the answer over
        sink.token("Clinic owners.")
        return AIMessage(content="Clinic owners.")
    frames = await _live_frames(lace_runtime, user, monkeypatch, model_step)
    types = [f["type"] for f in frames]
    assert [f["text"] for f in frames if f["type"] == "step"] == [lace_runs.RETRY_STEP]
    assert types.index("token_reset") < types.index("step")


def test_narration_is_one_short_line():
    assert lace_runs.narration("  Let me\n\ncheck   the pricing page. ") == "Let me check the pricing page."
    long = lace_runs.narration("word " * 100)
    assert len(long) == lace_runs.NARRATION_CHARS and long.endswith("…")
    assert lace_runs.narration("") == ""
