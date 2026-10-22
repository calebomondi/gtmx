"""The Lace's checklist and form questions, and how the founder's answer to
each reads to the Lace and to the founder."""

import json

import pytest

from agents.lace.answers import AnswerError, describe
from agents.lace.ask_tools import build_ask_tools
from agents.schemas.lace_ui import BlockAnswer, ChecklistBlock, ChecklistItem, ChoicesBlock, FormBlock, FormField


async def _ask(name: str, **args) -> dict:
    tool = {t.name: t for t in build_ask_tools()}[name]
    return json.loads(await tool.ainvoke(args))


async def test_a_checklist_needs_distinct_labelled_items():
    ok = await _ask("ask_checklist", question="Remove these?", submit="Remove ticked",
                    items=[{"id": "o1", "label": "Expo"}, {"id": "o2", "label": "Tender", "checked": False}])
    [block] = ok["data"]["ui"]
    assert ok["ok"] and block["type"] == "checklist" and block["submit"] == "Remove ticked"
    assert not (await _ask("ask_checklist", question="Pick", items=[]))["ok"]
    assert not (await _ask("ask_checklist", question="Pick", items=[{"id": "a", "label": "A"},
                                                                    {"id": "a", "label": "B"}]))["ok"]
    assert not (await _ask("ask_checklist", question="Pick", items=[{"id": "a", "label": "A"}], submit="x" * 31))["ok"]


async def test_a_form_needs_distinct_named_fields():
    ok = await _ask("ask_form", question="Who?", fields=[{"name": "email", "label": "Email", "kind": "email",
                                                          "value": "k@thalace.test"}])
    assert ok["ok"] and ok["data"]["ui"][0]["fields"][0]["value"] == "k@thalace.test"
    assert not (await _ask("ask_form", question="Who?", fields=[{"name": "a", "label": "A"},
                                                                {"name": "a", "label": "B"}]))["ok"]
    assert not (await _ask("ask_form", question="", fields=[{"name": "a", "label": "A"}]))["ok"]


def test_a_checklist_answer_names_ids_for_the_lace_and_labels_for_the_founder():
    block = ChecklistBlock(id="b1", question="Remove these?", submit="Remove",
                           items=[ChecklistItem(id="o1", label="Expo"), ChecklistItem(id="o2", label="Tender")])
    for_lace, for_founder = describe(block, BlockAnswer(block_id="b1", chosen=["o2"]))
    assert "Ticked: Tender (id o2)" in for_lace and "Left unticked: Expo (id o1)" in for_lace
    assert for_founder == "Remove: Tender"
    assert describe(block, BlockAnswer(block_id="b1"))[1] == "None of these"
    with pytest.raises(AnswerError):
        describe(block, BlockAnswer(block_id="b1", chosen=["o3"]))


def test_a_choice_answer_is_one_of_its_options():
    block = ChoicesBlock(id="b1", question="Which?", options=["Kenya", "Nigeria"])
    assert describe(block, BlockAnswer(block_id="b1", chosen=["Kenya"])) == ("Kenya", "Kenya")
    with pytest.raises(AnswerError):
        describe(block, BlockAnswer(block_id="b1", chosen=["Ghana"]))


def test_a_form_answer_skips_blank_optional_fields():
    block = FormBlock(id="b1", question="Who?", submit="Add", fields=[
        FormField(name="name", label="Name"), FormField(name="note", label="Note", required=False)])
    for_lace, for_founder = describe(block, BlockAnswer(block_id="b1", values={"name": " Kaleb ", "note": ""}))
    assert for_lace.endswith("name (Name): Kaleb") and for_founder == "Name: Kaleb"
    with pytest.raises(AnswerError, match="Name"):
        describe(block, BlockAnswer(block_id="b1", values={"note": "hi"}))
    with pytest.raises(AnswerError):
        describe(block, BlockAnswer(block_id="b1", values={"name": "K", "other": "x"}))


async def test_suggested_replies_are_two_or_three_short_ones():
    ok = await _ask("suggest_replies", options=[" Check their LinkedIn ", "Find their OTA guide", ""])
    assert ok["ok"] and ok["data"]["ui"] == [{"type": "suggestions",
                                              "options": ["Check their LinkedIn", "Find their OTA guide"]}]
    assert not (await _ask("suggest_replies", options=["Only one"]))["ok"]
    assert not (await _ask("suggest_replies", options=["a", "b", "c", "d"]))["ok"]
    assert not (await _ask("suggest_replies", options=["x" * 61, "ok"]))["ok"]
