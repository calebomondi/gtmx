"""Outreach may only state numbers its sources state, and never claim results
or customers in general terms. Cases are the live chain's real failures."""

import pytest

from agents.pipelines.outreach import grounding

SOURCES = (
    "HeatherDB: ~10× lower compute cost than GPU stacks. Runs on a Raspberry Pi 5. "
    "Moniepoint completed a US$200M Series C. Kuda serves over 8 million customers."
)


def test_invented_numbers_are_caught_and_sourced_ones_pass():
    draft = ("With your $200M Series C and 8 million customers, HeatherDB cuts AI costs by up to 60% "
             "and is 10x cheaper, at 200 million API calls per minute.")
    assert grounding.unsupported_numbers(draft, SOURCES) == ["60%", "200 million"]


def test_the_same_amount_written_differently_is_sourced():
    sources = "Permit fees add ~15k KES per unit. Acme raised $3.5M. Margins rose 20%."
    assert grounding.unsupported_numbers("about 15,000 KES per unit, after your $3.5 million raise", sources) == []
    assert grounding.unsupported_numbers("3.5 million users and 20x growth", sources) == ["3.5 million", "20x"]


def test_meeting_logistics_are_not_claims():
    assert grounding.unsupported_numbers("A 15-minute call on Tue 14 Oct at 10:00, or 30 minutes Thursday?", SOURCES) == []


def test_generic_proof_is_flagged():
    found = grounding.problems("Open to a review of how we've helped similar high-volume payment processors?", SOURCES)
    assert any("claims results or customers" in p for p in found)
    assert grounding.problems("Our clients see faster rollouts.", SOURCES)


def test_a_clean_draft_has_no_problems():
    draft = "Hi Kuda team,\n\nWith over 8 million customers, fraud models get retrained often. HeatherDB adapts without retraining, on ~10× cheaper hardware. Worth 15 minutes?\n\nWanjiku"
    assert grounding.problems(draft, SOURCES) == []


def test_the_r_ending_a_word_is_not_the_rand():
    """'for 200 million' was read as 'R 200 million'."""
    sources = "Moniepoint processes 200 million transactions."
    assert grounding.unsupported_numbers("infrastructure for 200 million API calls", sources) == []
    assert grounding.unsupported_numbers("a pilot from R 500 a month", sources) == ["R 500"]


@pytest.mark.parametrize("text", [
    "Open to a chat on how other African scale-ups are cutting AI costs?",
    "Open to a chat on how we're helping similar fintechs cut costs?",
    "Many leading Nigerian banks already run it.",
])
def test_broader_generic_proof_is_caught(text):
    assert any("claims results or customers" in p for p in grounding.problems(text, SOURCES))


def test_curly_apostrophes_do_not_hide_generic_proof():
    assert grounding.problems("Open to a chat on how we’re helping fintechs cut costs?", SOURCES)


DUE_DRAFT = (
    "Hi Sinako,\n\n"
    "Due operates across 15+ African markets. Rapid expansion often fragments context.\n\n"
    "Notion is used by 62% of Fortune 100 companies.\n\n"
    "Would you be open to a brief chat about how other fintechs are using Notion to manage cross-border work?\n\n"
    "Wanjiku"
)


def test_ungrounded_sentences_are_cut_and_an_ungrounded_ask_becomes_the_planned_one():
    sources = "Due operates in 15+ African markets."
    body = grounding.strip_ungrounded(DUE_DRAFT, sources, "Open to a 15-minute call on how Due keeps context across markets?")
    assert "62%" not in body and "other fintechs" not in body
    assert "Due operates across 15+ African markets." in body and body.startswith("Hi Sinako,")
    assert body.count("?") == 1 and "15-minute call on how Due keeps context" in body and body.endswith("Wanjiku")


def test_a_grounded_draft_is_left_alone():
    sources = "Due operates in 15+ African markets. Notion is used by 62% of Fortune 100 companies."
    clean = DUE_DRAFT.replace("how other fintechs are using Notion to manage", "how Due manages")
    assert grounding.strip_ungrounded(clean, sources, "Call?") == clean
