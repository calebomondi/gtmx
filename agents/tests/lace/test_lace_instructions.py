"""Standing instructions: the Lace keeps them when the founder says how it
should work, sees them in every chat, and drops them when asked."""

import json

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from agents.lace.graph import build_lace_graph
from agents.lace.instruction_tools import build_instruction_tools
from agents.lace.prompts import render_instructions
from agents.schemas.lace import INSTRUCTION_CHARS, Instruction
from lace_fakes import MemoryStore, ScriptedModel


async def _call(store, name, **args) -> dict:
    tool = {t.name: t for t in build_instruction_tools(store)}[name]
    return json.loads(await tool.ainvoke(args))


async def test_an_instruction_is_kept_once():
    store = MemoryStore()
    out = await _call(store, "remember_instruction", instruction="  Only competitors   selling in Kenya ",
                      applies_to="competitors")
    assert out["ok"] and "settings, under Instructions" in out["summary"]
    assert [(i.text, i.applies_to) for i in store.kept] == [("Only competitors selling in Kenya", "competitors")]
    again = await _call(store, "remember_instruction", instruction="only competitors selling in kenya",
                        applies_to="competitors")
    assert again["summary"] == "That instruction is already kept." and len(store.kept) == 1


async def test_an_empty_long_or_one_too_many_instruction_is_refused():
    store = MemoryStore()
    assert not (await _call(store, "remember_instruction", instruction="  ", applies_to="leads"))["ok"]
    long = await _call(store, "remember_instruction", instruction="x" * (INSTRUCTION_CHARS + 1), applies_to="leads")
    assert not long["ok"] and str(INSTRUCTION_CHARS) in long["summary"]
    store.max_instructions = 0
    full = await _call(store, "remember_instruction", instruction="Shorter emails", applies_to="outreach")
    assert not full["ok"] and "up to 30" in full["summary"] and store.kept == []


async def test_forgetting_one():
    store = MemoryStore()
    await _call(store, "remember_instruction", instruction="No events outside Africa", applies_to="opportunities")
    assert not (await _call(store, "forget_instruction", instruction_id="nope"))["ok"]
    out = await _call(store, "forget_instruction", instruction_id="i1")
    assert out["summary"] == "Dropped the instruction: No events outside Africa" and store.kept == []


def test_a_job_sees_only_the_instructions_for_its_kind():
    kept = [Instruction(id="1", text="Only Kenya", applies_to="competitors"),
            Instruction(id="2", text="We are B2B only", applies_to="everything"),
            Instruction(id="3", text="Casual tone", applies_to="outreach")]
    assert render_instructions(kept, "competitors") == "- Only Kenya\n- We are B2B only"
    assert render_instructions(kept, "leads") == "- We are B2B only"
    assert render_instructions([], "leads") == ""
    assert render_instructions(kept).splitlines()[0] == "- [1] (competitors) Only Kenya"
    assert render_instructions([]) == "None yet."


async def test_the_lace_sees_them_in_every_chat(settings):
    store = MemoryStore()
    await store.add_instruction("Only competitors selling in Kenya", "competitors")
    model = ScriptedModel(AIMessage(content="Noted."))
    await build_lace_graph(store, settings=settings, model_step=model).ainvoke(
        {"messages": [HumanMessage(content="hi")]}, {"configurable": {"thread_id": "t"}})
    system = model.calls[0][0][0]
    assert isinstance(system, SystemMessage)
    assert "Standing instructions from the team" in system.content
    assert "- [i1] (competitors) Only competitors selling in Kenya" in system.content
