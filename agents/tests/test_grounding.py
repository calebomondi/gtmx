"""Outreach may only state numbers its sources state, and never claim results
or customers in general terms. Cases are the live chain's real failures."""

from agents.pipelines.outreach import grounding

SOURCES = (
    "HeatherDB: ~10× lower compute cost than GPU stacks. Runs on a Raspberry Pi 5. "
    "Moniepoint completed a US$200M Series C. Kuda serves over 8 million customers."
)


def test_invented_numbers_are_caught_and_sourced_ones_pass():
    draft = ("With your $200M Series C and 8 million customers, HeatherDB cuts AI costs by up to 60% "
             "and is 10x cheaper, at 200 million API calls per minute.")
    assert grounding.unsupported_numbers(draft, SOURCES) == ["60%", "200 million"]


def test_meeting_logistics_are_not_claims():
    assert grounding.unsupported_numbers("A 15-minute call on Tue 14 Oct at 10:00, or 30 minutes Thursday?", SOURCES) == []


def test_generic_proof_is_flagged():
    found = grounding.problems("Open to a review of how we've helped similar high-volume payment processors?", SOURCES)
    assert any("claims results or customers" in p for p in found)
    assert grounding.problems("Our clients see faster rollouts.", SOURCES)


def test_a_clean_draft_has_no_problems():
    draft = "Hi Kuda team,\n\nWith over 8 million customers, fraud models get retrained often. HeatherDB adapts without retraining, on ~10× cheaper hardware. Worth 15 minutes?\n\nWanjiku"
    assert grounding.problems(draft, SOURCES) == []
