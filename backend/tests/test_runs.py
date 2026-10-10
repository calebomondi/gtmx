"""The run manager: runs are owned by the server, persist every frame, pause
on questions with no task alive, resume from an answer, and fail loudly."""

import asyncio
import uuid
from types import SimpleNamespace

import pytest
from langgraph.types import Command

from backend.app.database import models
from backend.app.database.connect import AsyncSessionLocal
from backend.app.runs import discovery, events, manager
from backend.app.schemas.agents import DiscoveryRequest
from backend.app.services.errors import ConflictError, NotFoundError
from backend.tests.helpers import make_user

QUESTION = {"type": "product_service_description_confirmation", "question": "Is this right?", "draft": "An issue tracker."}
PHASES = ["discover_offer", "create_specialists", "understand_offer", "understand_market", "understand_competition", "determine_icp"]
FINAL_VALUES = {
    "offer_name": "Linear", "website_url": "https://linear.app", "offer_description": "An issue tracker.",
    "target_market": ["US"], "features": ["Issues"], "confirmed": True,
    "follow_up": {"user_replies": ["yes"]},
}


class FakeAgent:
    """Interrupts once with QUESTION, then (on resume) completes every phase.
    `fail_on_resume` makes the resumed segment raise instead."""

    def __init__(self, fail_on_resume: bool = False):
        self.fail_on_resume = fail_on_resume
        self.inputs = []

    async def astream(self, agent_input, config, stream_mode):
        self.inputs.append(agent_input)
        if not isinstance(agent_input, Command):
            yield {"__interrupt__": (SimpleNamespace(value=QUESTION),)}
            return
        if self.fail_on_resume:
            raise RuntimeError("provider exploded with secret details")
        for node in PHASES:
            # understand_offer's output arrives only in its own update, as with
            # a real parallel super-step (aget_state lacks it until both finish).
            yield {node: {"offer_domain_fit_understanding": "From the update."} if node == "understand_offer" else {}}

    async def aget_state(self, config):
        return SimpleNamespace(values=FINAL_VALUES)


@pytest.fixture(autouse=True)
async def drain_run_tasks(clean_tables):
    """Let run tasks finish before table cleanup. A run marks itself completed
    a moment before writing its last event; cleanup's synchronous TRUNCATE
    would otherwise block the event loop that write needs."""
    yield
    if manager._tasks:
        await asyncio.gather(*manager._tasks.values(), return_exceptions=True)


@pytest.fixture
def agent(monkeypatch):
    fake = FakeAgent()
    monkeypatch.setattr(discovery, "get_agent", lambda: fake)
    return fake


REQUEST = DiscoveryRequest(product_name="Linear", product_url="https://linear.app")


async def _wait_for_status(run_id, statuses, timeout=5.0):
    async with asyncio.timeout(timeout):
        while True:
            async with AsyncSessionLocal() as db:
                run = await db.get(models.Run, run_id)
            if run.status in statuses:
                return run
            await asyncio.sleep(0.02)


async def _frames(run_id, after=0):
    out = []
    async with asyncio.timeout(5):
        async for frame in events.subscribe(run_id, after):
            out.append(frame)
            if frame["type"] in events.TERMINAL_FRAME_TYPES or frame["type"] == "interrupt":
                return out


async def test_run_pauses_with_no_task_then_resumes_and_completes(agent):
    owner = make_user("Owner")
    run = await manager.start_discovery(owner.id, REQUEST)

    paused = await _wait_for_status(run.id, {"awaiting_input"})
    assert run.id not in manager._tasks  # nothing waits on the human
    assert paused.progress["interrupt"]["question"] == "Is this right?"
    first = await _frames(run.id)
    assert [f["type"] for f in first] == ["interrupt"]

    await manager.answer(owner.id, run.id, "yes")
    done = await _wait_for_status(run.id, {"completed"})
    assert agent.inputs[-1] == Command(resume="yes")

    frames = await _frames(run.id, after=first[-1]["event_id"])
    types = [f["type"] for f in frames]
    assert types[0] == "answered" and types[-1] == "complete"
    assert "workspace_created" in types
    assert [f["node"] for f in frames if f["type"] == "phase" and f["status"] == "done"] == PHASES

    # Workspace and insights were persisted for the owner.
    async with AsyncSessionLocal() as db:
        workspace = await db.get(models.Workspace, done.workspace_id)
        profile = (await db.execute(
            models.ProductProfile.__table__.select().where(models.ProductProfile.workspace_id == workspace.id)
        )).first()
    assert workspace.user_id == owner.id and workspace.name == "Linear"
    offer_data = [f for f in frames if f["type"] == "phase_data" and f["node"] == "understand_offer"]
    assert offer_data and offer_data[0]["offer_domain_fit_understanding"] == "From the update."


async def test_replay_returns_only_frames_after_cursor(agent):
    owner = make_user("Owner")
    run = await manager.start_discovery(owner.id, REQUEST)
    await _wait_for_status(run.id, {"awaiting_input"})
    await manager.answer(owner.id, run.id, "yes")
    await _wait_for_status(run.id, {"completed"})
    everything = await _frames(run.id)  # stops at the interrupt
    rest = await _frames(run.id, after=everything[-1]["event_id"])
    ids = [f["event_id"] for f in everything + rest]
    assert ids == sorted(set(ids))  # monotonic, no duplicates


async def test_answer_rules(agent):
    owner, intruder = make_user("Owner"), make_user("Intruder")
    run = await manager.start_discovery(owner.id, REQUEST)
    await _wait_for_status(run.id, {"awaiting_input"})
    with pytest.raises(NotFoundError):
        await manager.answer(intruder.id, run.id, "yes")
    # Two concurrent answers: exactly one resumes the run.
    results = await asyncio.gather(
        manager.answer(owner.id, run.id, "yes"), manager.answer(owner.id, run.id, "yes"),
        return_exceptions=True,
    )
    assert sum(isinstance(r, ConflictError) for r in results) == 1
    await _wait_for_status(run.id, {"completed"})


async def test_failure_is_recorded_without_leaking_internals(monkeypatch):
    fake = FakeAgent(fail_on_resume=True)
    monkeypatch.setattr(discovery, "get_agent", lambda: fake)
    owner = make_user("Owner")
    run = await manager.start_discovery(owner.id, REQUEST)
    await _wait_for_status(run.id, {"awaiting_input"})
    await manager.answer(owner.id, run.id, "yes")
    failed = await _wait_for_status(run.id, {"failed"})
    assert "secret" not in failed.error
    frames = await _frames(run.id)
    assert frames[-1]["type"] == "interrupt"  # subscribe stops at first pause
    assert (await _frames(run.id, after=frames[-1]["event_id"]))[-1]["type"] == "error"


async def test_cancel_and_restart_recovery(agent):
    owner = make_user("Owner")
    run = await manager.start_discovery(owner.id, REQUEST)
    await _wait_for_status(run.id, {"awaiting_input"})
    cancelled = await manager.cancel(owner.id, run.id)
    assert cancelled.status == "cancelled"

    # A run left `running` by a dead process is failed on the next boot.
    async with AsyncSessionLocal() as db:
        stranded = models.Run(user_id=owner.id, kind="discovery", status="running")
        db.add(stranded)
        await db.commit()
    await manager.recover_after_restart()
    async with AsyncSessionLocal() as db:
        assert (await db.get(models.Run, stranded.id)).status == "failed"


def test_socket_starts_run_and_reattaches_after_disconnect(client, user, agent, monkeypatch):
    from backend.app.api.v1.endpoints import discovery as endpoint

    async def ws_user(_ws):
        return user
    monkeypatch.setattr(endpoint, "websocket_user", ws_user)

    with client.websocket_connect("/api/v1/discover") as ws:
        ws.send_json(REQUEST.model_dump())
        run_id = ws.receive_json()["run_id"]
        question = ws.receive_json()
        assert question["type"] == "interrupt" and question["run_id"] == run_id
    # Disconnected mid-question. The run is still there, waiting.

    with client.websocket_connect("/api/v1/discover") as ws:
        ws.send_json({"resume": run_id, "after": question["event_id"]})
        assert ws.receive_json()["type"] == "run"
        ws.send_json({"answer": "yes"})
        seen = []
        while not seen or seen[-1] not in events.TERMINAL_FRAME_TYPES:
            seen.append(ws.receive_json()["type"])
    assert seen[-1] == "complete"

    intruder = make_user("Intruder")

    async def other_user(_ws):
        return intruder
    monkeypatch.setattr(endpoint, "websocket_user", other_user)
    with client.websocket_connect("/api/v1/discover") as ws:  # someone else's run
        ws.send_json({"resume": run_id})
        assert ws.receive_json() == {"type": "error", "message": "Run not found"}


def test_phase_payload_serializes_pydantic_models():
    """Regression: real runs carry pydantic models (specialists, market data)
    in state; the fake agent above does not."""
    from pydantic import BaseModel

    class Model(BaseModel):
        name: str

    payload = discovery.phase_payload("create_specialists", {"specialists": [Model(name="a"), Model(name="b")]})
    assert payload == {"specialists": [{"name": "a"}, {"name": "b"}]}
    market = discovery.phase_payload("understand_market", {"market_data": Model(name="m")})
    assert market["market_data"] == {"name": "m"}
