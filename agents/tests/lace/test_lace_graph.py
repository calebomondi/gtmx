"""The Lace loop with a scripted model: routing, the brief, and its bounds."""

import json

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
from langgraph.checkpoint.memory import MemorySaver

from agents.lace.graph import build_lace_graph, history_window, tool_calls_this_turn
from agents.lace.prompts import render_brief
from lace_fakes import MemoryStore, ScriptedModel, call, make_fact


def _ask(text: str) -> dict:
    return {"messages": [HumanMessage(content=text)]}


async def test_answers_without_tools(store, settings):
    model = ScriptedModel(AIMessage(content="Hello, I'm Ada."))
    graph = build_lace_graph(store, settings=settings, model_step=model)
    out = await graph.ainvoke(_ask("hi"))
    assert out["messages"][-1].content == "Hello, I'm Ada."
    assert len(model.calls) == 1


async def test_brief_rides_in_the_system_prompt(settings):
    store = MemoryStore([make_fact("f1", "Acme sells payroll software to clinics.")])
    model = ScriptedModel(AIMessage(content="ok"))
    await build_lace_graph(store, settings=settings, model_step=model).ainvoke(_ask("what do we sell?"))
    system = model.calls[0][0][0]
    assert isinstance(system, SystemMessage)
    assert "You are Ada" in system.content and "payroll software to clinics" in system.content


async def test_tool_call_then_answer(store, settings):
    model = ScriptedModel(
        call("record_fact", {"topic": "pricing", "claim": "Plans start at $20.", "from_founder": True}),
        AIMessage(content="Noted."),
    )
    out = await build_lace_graph(store, settings=settings, model_step=model).ainvoke(_ask("we charge $20"))
    tool_msg = next(m for m in out["messages"] if isinstance(m, ToolMessage))
    assert json.loads(tool_msg.content)["ok"]
    assert [f.claim for f in await store.facts()] == ["Plans start at $20."]
    # The second step sees the new fact in its brief.
    assert "Plans start at $20." in model.calls[1][0][0].content


async def test_a_failing_tool_does_not_end_the_turn(store, settings):
    model = ScriptedModel(
        call("record_fact", {"topic": "offer", "claim": "x"}),  # no source: refused
        AIMessage(content="I need a source for that."),
    )
    out = await build_lace_graph(store, settings=settings, model_step=model).ainvoke(_ask("note x"))
    assert out["messages"][-1].content == "I need a source for that."


async def test_tool_budget_forces_an_answer(store, settings):
    settings = settings.model_copy(update={"lace_max_tool_calls_per_turn": 2})
    model = ScriptedModel(
        call("get_facts", {}, id="a"),
        call("get_facts", {}, id="b"),
        AIMessage(content="Here's what I have."),
    )
    out = await build_lace_graph(store, settings=settings, model_step=model).ainvoke(_ask("dig"))
    assert out["messages"][-1].content == "Here's what I have."
    final_prompt, final_tools = model.calls[-1]
    assert final_tools == []
    assert "used this turn's tool calls" in final_prompt[-1].content


async def test_budget_is_per_turn_on_a_persistent_thread(store, settings):
    settings = settings.model_copy(update={"lace_max_tool_calls_per_turn": 1})
    model = ScriptedModel(
        call("get_facts", {}, id="a"), AIMessage(content="one"),
        call("get_facts", {}, id="b"), AIMessage(content="two"),
    )
    graph = build_lace_graph(store, settings=settings, model_step=model, checkpointer=MemorySaver())
    thread = {"configurable": {"thread_id": "lace-1"}}
    await graph.ainvoke(_ask("first"), thread)
    out = await graph.ainvoke(_ask("second"), thread)
    assert out["messages"][-1].content == "two"
    # The second turn's tool call was allowed: the first turn's didn't count.
    assert model.calls[2][1] != []


def test_history_window_starts_on_a_founder_message():
    old = [HumanMessage(content="old " * 400), AIMessage(content="", tool_calls=[{"name": "x", "args": {}, "id": "1"}]),
           ToolMessage(content="r " * 400, tool_call_id="1"), AIMessage(content="done")]
    current = [HumanMessage(content="now"), AIMessage(content="", tool_calls=[{"name": "x", "args": {}, "id": "2"}]),
               ToolMessage(content="big " * 600, tool_call_id="2")]
    window = history_window(old + current, budget=500)
    assert window == current  # old turn dropped whole, never cut mid-turn
    assert history_window(old + current, budget=100_000) == old + current


def test_tool_calls_count_only_the_current_turn():
    msgs = [HumanMessage(content="a"), ToolMessage(content="", tool_call_id="1"),
            HumanMessage(content="b"), ToolMessage(content="", tool_call_id="2"), ToolMessage(content="", tool_call_id="3")]
    assert tool_calls_this_turn(msgs) == 2


def test_brief_puts_confident_facts_first_and_respects_its_cap():
    facts = [make_fact("1", "Maybe sells to vets.", confidence="low"),
             make_fact("2", "Sells payroll to clinics.", confidence="high")]
    assert render_brief(facts).splitlines()[0] == "- [offer] Sells payroll to clinics."
    many = [make_fact(str(i), f"Fact number {i} about the offer.") for i in range(400)]
    assert render_brief(many, cap=100).endswith("(more facts on file: use get_facts)")
    assert render_brief([]).startswith("Nothing yet")


def test_dangling_tool_calls_get_an_interrupted_result():
    from agents.lace.graph import close_dangling_tool_calls
    msgs = [HumanMessage(content="go"),
            AIMessage(content="", tool_calls=[{"name": "x", "args": {}, "id": "a"}, {"name": "y", "args": {}, "id": "b"}]),
            ToolMessage(content="done", tool_call_id="a"),
            HumanMessage(content="next")]
    closed = close_dangling_tool_calls(msgs)
    answers = {m.tool_call_id: m.content for m in closed if isinstance(m, ToolMessage)}
    assert answers["a"] == "done" and "interrupted" in answers["b"]
    assert len(closed) == len(msgs) + 1
    assert close_dangling_tool_calls(msgs[:1]) == msgs[:1]


async def test_a_turn_after_an_interrupted_one_still_works(store, settings):
    model = ScriptedModel(AIMessage(content="Picking up where we left off."))
    graph = build_lace_graph(store, settings=settings, model_step=model, checkpointer=MemorySaver())
    thread = {"configurable": {"thread_id": "t"}}
    # A turn cut off between the tool call and its result.
    await graph.aupdate_state(thread, {"messages": [
        HumanMessage(content="dig"), AIMessage(content="", tool_calls=[{"name": "get_facts", "args": {}, "id": "z"}])]},
        as_node="tools")
    await graph.ainvoke(_ask("hello?"), thread)
    sent = model.calls[0][0]
    assert any(isinstance(m, ToolMessage) and m.tool_call_id == "z" for m in sent)


def test_prompt_separates_sourced_claims_from_judgment():
    from agents.lace.prompts import system_prompt
    from agents.schemas.lace import LaceProfile
    prompt = system_prompt(LaceProfile(name="Ada", website="https://acme.test"), [])
    assert '"My read"' in prompt and '"Sources" list' in prompt and "never recorded with record_fact" in prompt
