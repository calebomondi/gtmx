"""Sorting what was said on social media: each item numbered, the noise
dropped, and nothing the model invents kept."""

from agents.lace.listening import sort_heard
from agents.schemas.listening import Heard, HeardItem
from lace_fakes import make_fact

ITEMS = [{"platform": "x", "author": "jane", "text": "Does this work for clinics in Kampala?", "url": "u1"},
         {"platform": "instagram", "author": "bot99", "text": "Follow me for crypto", "url": "u2"},
         {"platform": "facebook", "author": "Tom", "text": "The pricing page is confusing", "url": "u3"}]


def test_noise_and_unknown_numbers_are_dropped():
    seen = {}

    def classify(messages):
        seen["system"], seen["listing"] = messages[0].content, messages[1].content
        return Heard(items=[HeardItem(ref="1", kind="lead", note="A clinic in Kampala asking"),
                            HeardItem(ref="2", kind="noise"), HeardItem(ref="3", kind="feedback", note="Pricing unclear"),
                            HeardItem(ref="3", kind="praise"), HeardItem(ref="9", kind="lead"),
                            HeardItem(ref="two", kind="lead")])

    found = sort_heard("Acme", [make_fact("1", "Acme sells payroll to clinics.")], ITEMS, classify=classify)
    assert [(item["url"], verdict.kind) for item, verdict in found] == [("u1", "lead"), ("u3", "feedback")]
    assert "1. [x] @jane: Does this work for clinics in Kampala?" in seen["listing"]
    assert "Acme sells payroll to clinics." in seen["system"]


def test_nothing_said_means_no_call():
    def classify(messages):
        raise AssertionError("nothing to sort")
    assert sort_heard("Acme", [], [], classify=classify) == []
