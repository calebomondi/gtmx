"""Suggested replies written for a reply that ends on an offer."""

from agents.lace.follow_ups import TAIL_CHARS, ends_on_question, follow_ups
from agents.schemas.lace_ui import FollowUps

OFFER = ("Velinex runs scheduling for clinics.\n\nAnything else you'd like to explore? Maybe dig into Velinex's "
         "recent activity or look for target accounts we could pursue?")


def _answers(*options):
    seen = []

    def ask(messages, schema, **kwargs):
        seen.append(messages[-1].content)
        return FollowUps(options=list(options))
    return ask, seen


def test_only_a_closing_question_counts():
    assert ends_on_question(OFFER)
    assert not ends_on_question("Is it them?\n\nI saved Velinex for you.")
    assert not ends_on_question("")


def test_the_offers_become_tappable_replies():
    ask, seen = _answers("Dig into Velinex's activity", "Find target accounts")
    assert follow_ups(OFFER, ask) == ["Dig into Velinex's activity", "Find target accounts"]
    assert seen == [OFFER]


def test_the_model_reads_only_the_end_of_a_long_reply():
    ask, seen = _answers("Yes", "No")
    follow_ups("x" * 5000 + OFFER, ask)
    assert len(seen[0]) == TAIL_CHARS and seen[0].endswith(OFFER[-40:])


def test_too_few_or_too_long_options_are_dropped():
    assert follow_ups(OFFER, _answers()[0]) == []
    assert follow_ups(OFFER, _answers("Dig in")[0]) == []
    assert follow_ups(OFFER, _answers("Dig in", "x" * 61)[0]) == []
    assert follow_ups(OFFER, _answers("a", "b", "c", "d")[0]) == ["a", "b", "c"]
