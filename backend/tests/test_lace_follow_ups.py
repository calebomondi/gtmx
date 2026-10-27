"""A Lace reply that ends on an offer gets suggested replies, unless the
Lace already put something to click under it."""

import asyncio
import time

import pytest

from agents.llm.main import LlmProvidersExhaustedError
from backend.app.runs import lace as lace_runs

OFFER = "I found three rivals.\n\nWant me to dig into Velinex, or look for target accounts?"


@pytest.fixture
def suggests(monkeypatch):
    asked = []

    def follow_ups(reply):
        asked.append(reply)
        return ["Dig into Velinex", "Find target accounts"]
    monkeypatch.setattr(lace_runs, "follow_ups", follow_ups)
    return asked


async def test_an_offer_gets_suggested_replies(suggests):
    card = {"type": "card", "kind": "competitor", "id": "c1", "title": "Velinex"}
    blocks = await lace_runs._with_follow_ups(OFFER, [card])
    assert blocks == [card, {"type": "suggestions", "options": ["Dig into Velinex", "Find target accounts"]}]


@pytest.mark.parametrize("shown", ["suggestions", "choices", "checklist", "form", "action"])
async def test_nothing_is_added_under_something_clickable(suggests, shown):
    blocks = [{"type": shown}]
    assert await lace_runs._with_follow_ups(OFFER, blocks) == blocks
    assert suggests == []


async def test_a_reply_without_a_closing_question_is_left_alone(suggests):
    assert await lace_runs._with_follow_ups("I saved Velinex.", []) == []
    assert suggests == []


async def test_no_options_means_no_chips(monkeypatch):
    monkeypatch.setattr(lace_runs, "follow_ups", lambda reply: [])
    assert await lace_runs._with_follow_ups(OFFER, []) == []


async def test_a_failed_or_slow_model_leaves_the_reply_as_it_was(monkeypatch):
    def fails(reply):
        raise LlmProvidersExhaustedError("lace:follow_ups", None)
    monkeypatch.setattr(lace_runs, "follow_ups", fails)
    assert await lace_runs._with_follow_ups(OFFER, []) == []

    def slow(reply):
        time.sleep(0.3)
        return ["a", "b"]
    monkeypatch.setattr(lace_runs, "follow_ups", slow)
    monkeypatch.setattr(lace_runs, "FOLLOW_UPS_TIMEOUT_S", 0.05)
    assert await lace_runs._with_follow_ups(OFFER, []) == []
    await asyncio.sleep(0.3)  # let the abandoned thread finish
