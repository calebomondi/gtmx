"""Offline tests for the description-confirmation step of discover_offer.

Regression: a reply like "yes, that's correct" was not recognised as a
confirmation, went to the edit path, which re-asked the same question, and the
interview looped until the LLM quota ran out.
"""

import pytest

from agents.sub_agents.discover import discover_offer
from agents.sub_agents.discover.discover_offer import InlineCheck, _pure_confirmation, check_if_desc_inline


@pytest.mark.parametrize("reply", [
    "yes",
    "Yes.",
    "yes, that's correct",
    "Yes, that’s correct!",
    "yep looks good",
    "that's right",
    "That is correct.",
    "looks great",
    "ok and confirmed",
    "perfect",
    "lgtm",
    "  all good!  ",
])
def test_confirmation_phrasings_are_recognised(reply):
    assert _pure_confirmation(reply)


@pytest.mark.parametrize("reply", [
    "",
    None,
    "yes but change the pricing to $20",
    "no",
    "not quite, it's for agencies",
    "yes, and add that it integrates with Slack",
    "it's an issue tracker for software teams",
])
def test_edits_and_rejections_are_not_confirmations(reply):
    assert not _pure_confirmation(reply)


def _state(reply: str) -> dict:
    return {
        "offer_description": "Linear is an issue tracker for software teams.",
        "scraped_content": "Linear is an issue tracker for software teams.",
        "follow_up": {"follow_up_question": None, "user_replies": [reply]},
    }


def _stub_llm(monkeypatch, result: InlineCheck | None):
    monkeypatch.setattr(discover_offer, "invoke_structured_with_fallback", lambda **_: result)


def test_grounded_reply_with_no_change_confirms_instead_of_looping(monkeypatch):
    _stub_llm(monkeypatch, InlineCheck(inline=True, revised_description=None))
    cmd = check_if_desc_inline(_state("great, that's exactly what it does"))
    assert cmd.goto == "proceed_to_description"
    assert cmd.update["confirmed"] is True


def test_grounded_edit_reasks_with_the_revised_draft(monkeypatch):
    revised = "Linear is an issue tracker and roadmap tool for software teams."
    _stub_llm(monkeypatch, InlineCheck(inline=True, revised_description=revised))
    cmd = check_if_desc_inline(_state("also mention roadmaps"))
    assert cmd.goto == "ask_for_confirmation"
    assert cmd.update["offer_description"] == revised
    assert "confirmed" not in cmd.update


def test_ungrounded_edit_reasks_with_a_note(monkeypatch):
    _stub_llm(monkeypatch, InlineCheck(inline=False, note="We couldn't verify the AI feature."))
    cmd = check_if_desc_inline(_state("add that it has an AI copilot"))
    assert cmd.goto == "ask_for_confirmation"
    assert cmd.update["follow_up"]["follow_up_question"] == "We couldn't verify the AI feature."


def test_llm_failure_reasks_rather_than_confirming(monkeypatch):
    _stub_llm(monkeypatch, None)
    cmd = check_if_desc_inline(_state("hmm"))
    assert cmd.goto == "ask_for_confirmation"
    assert "confirmed" not in cmd.update
