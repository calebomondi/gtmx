"""The replies suggested under an answer: written from the founder's question,
the answer and their situation, specific and of different kinds, tidied and
bounded, and none when the answer wants the founder to type."""

from langchain_core.messages import SystemMessage

from agents.lace.follow_ups import ASKED_CHARS, CHOICE_CHARS, REPLY_CHARS, follow_ups
from agents.schemas.lace_ui import FollowUps

ANSWER = "I found three rivals: Velinex, Hamtech and Roamly. Velinex is the closest."


def _answers(*options):
    seen = []

    def ask(messages, schema, **kwargs):
        seen.append(messages)
        return FollowUps(options=list(options))
    return ask, seen


def test_the_model_reads_the_question_the_answer_and_the_situation():
    ask, seen = _answers("Dig into Velinex", "Find fintech leads in Lagos")
    assert follow_ups(ANSWER, "who competes?", "- Drafts waiting: 2", ask=ask) == [
        "Dig into Velinex", "Find fintech leads in Lagos"]
    [(system, human)] = seen
    assert isinstance(system, SystemMessage)
    assert all(kind in system.content for kind in ("next:", "dig:", "challenge:", "nudge:"))
    assert "who competes?" in human.content and ANSWER in human.content and "Drafts waiting: 2" in human.content


def test_without_a_question_or_situation_it_reads_the_answer_alone():
    ask, seen = _answers("a b", "c d")
    follow_ups(ANSWER, ask=ask)
    assert seen[0][1].content == f"The assistant answered:\n{ANSWER}"


def test_long_inputs_are_cut_to_what_matters():
    ask, seen = _answers("a b", "c d")
    follow_ups("#" * 5000 + ANSWER, "~" * 2000, ask=ask)
    human = seen[0][1].content
    assert ANSWER in human and human.count("#") == REPLY_CHARS - len(ANSWER)
    assert human.count("~") == ASKED_CHARS


def test_chips_are_tidied_deduplicated_and_bounded():
    ask, _ = _answers('"Dig into Velinex."', "Dig into Velinex", "x" * (CHOICE_CHARS + 1), "Track Roamly", "Ask",
                      "One too many")
    assert follow_ups(ANSWER, ask=ask) == ["Dig into Velinex", "Track Roamly", "Ask"]


def test_fewer_than_two_means_none():
    assert follow_ups(ANSWER, ask=_answers()[0]) == []
    assert follow_ups(ANSWER, ask=_answers("Only one")[0]) == []
