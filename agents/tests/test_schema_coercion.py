"""LenientModel: every container field an LLM double-serialises is repaired,
through Optional and nesting; scalars and non-JSON strings are left alone."""

from typing import Optional

from agents.schemas.coercion import LenientModel


class Inner(LenientModel):
    tags: list[str] = []


class Outer(LenientModel):
    name: str = ""
    items: list[Inner] = []
    maybe: Optional[list[str]] = None
    meta: dict = {}


def test_nested_string_containers_are_parsed():
    out = Outer.model_validate({
        "name": "[not a list field]",
        "items": '[{"tags": "[\\"a\\", \\"b\\"]"}]',
        "maybe": '```json\n["x"]\n```',
        "meta": 'note: {"k": 1} trailing',
    })
    assert out.name == "[not a list field]"  # scalar fields are never touched
    assert out.items[0].tags == ["a", "b"]
    assert out.maybe == ["x"]
    assert out.meta == {"k": 1}


def test_real_containers_pass_through():
    out = Outer.model_validate({"items": [{"tags": ["a"]}], "maybe": None})
    assert out.items[0].tags == ["a"] and out.maybe is None


class Finding(LenientModel):
    text: str
    evidence: str


class Profile(LenientModel):
    strengths: list[str] = []
    sentiment: list[Finding] = []


def test_a_list_written_as_prose_becomes_a_list():
    out = Profile.model_validate({"strengths": "- Strong brand\n2. Local team\n\n", "sentiment": "No reviews found."})
    assert out.strengths == ["Strong brand", "Local team"]
    # Prose has no evidence to make a finding of.
    assert out.sentiment == []


def test_text_items_that_came_as_objects_become_their_text():
    out = Profile.model_validate({"strengths": [{"text": "Strong brand"}, {"point": "Local team"}, "Fast"]})
    assert out.strengths == ["Strong brand", "Local team", "Fast"]
