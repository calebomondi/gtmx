"""Every Lace reply gets replies the founder can tap next, written after the
answer from their question and their situation, unless the Lace already put
something to click under it. The chips are a courtesy: a failed or slow model
leaves the reply as it was."""

import asyncio
import time

import pytest

from agents.llm.main import LlmProvidersExhaustedError
from backend.app.runs import lace as lace_runs

ANSWER = "I found three rivals: Velinex, Hamtech and Roamly. Velinex is the closest."


@pytest.fixture
def suggests(monkeypatch):
    asked = []

    def write(reply, asked_by, situation):
        asked.append((reply, asked_by, situation))
        return ["Dig into Velinex", "Is Roamly really a rival?"]
    monkeypatch.setattr(lace_runs, "follow_ups", write)
    return asked


async def test_every_answer_gets_chips_written_from_the_question_and_the_situation(suggests):
    card = {"type": "card", "kind": "competitor", "id": "c1", "title": "Velinex"}
    blocks = await lace_runs._with_follow_ups(ANSWER, [card], "who competes with us?", "- Leads saved: none yet")
    assert blocks == [card, {"type": "suggestions", "options": ["Dig into Velinex", "Is Roamly really a rival?"]}]
    assert suggests == [(ANSWER, "who competes with us?", "- Leads saved: none yet")]


@pytest.mark.parametrize("shown", ["suggestions", "choices", "checklist", "form", "action"])
async def test_nothing_is_added_under_something_clickable(suggests, shown):
    blocks = [{"type": shown}]
    assert await lace_runs._with_follow_ups(ANSWER, blocks) == blocks
    assert suggests == []


async def test_an_empty_reply_is_left_alone(suggests):
    assert await lace_runs._with_follow_ups("  ", []) == []
    assert suggests == []


async def test_no_options_means_no_chips(monkeypatch):
    monkeypatch.setattr(lace_runs, "follow_ups", lambda reply, asked, situation: [])
    assert await lace_runs._with_follow_ups(ANSWER, []) == []


async def test_a_failed_or_slow_model_leaves_the_reply_as_it_was(monkeypatch):
    def fails(reply, asked, situation):
        raise LlmProvidersExhaustedError("lace:follow_ups", None)
    monkeypatch.setattr(lace_runs, "follow_ups", fails)
    assert await lace_runs._with_follow_ups(ANSWER, []) == []

    def slow(reply, asked, situation):
        time.sleep(0.3)
        return ["a", "b"]
    monkeypatch.setattr(lace_runs, "follow_ups", slow)
    monkeypatch.setattr(lace_runs, "FOLLOW_UPS_TIMEOUT_S", 0.05)
    assert await lace_runs._with_follow_ups(ANSWER, []) == []
    await asyncio.sleep(0.3)  # let the abandoned thread finish

