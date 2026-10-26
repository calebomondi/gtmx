"""The Lace against real Qwen and Exa: it researches with tools and records
what it found. Opt-in: `uv run pytest -m live agents/tests/lace`."""

import json

import pytest
from langchain_core.messages import HumanMessage, ToolMessage

from agents.lace.graph import build_lace_graph
from lace_fakes import MemoryStore

pytestmark = pytest.mark.live


async def test_researches_and_records_facts():
    store = MemoryStore()
    graph = build_lace_graph(store)
    out = await graph.ainvoke({"messages": [HumanMessage(content=(
        "Read https://linear.app and find out what Linear sells and who it is "
        "for, then record two facts about it with their sources."
    ))]})
    called = [json.loads(m.content) for m in out["messages"] if isinstance(m, ToolMessage)]
    assert called, "the Lace answered without using a tool"
    facts = await store.facts()
    assert len(facts) >= 2 and all(f.source_url for f in facts)
    assert out["messages"][-1].content.strip()


async def test_onboarding_learns_a_real_site():
    from agents.lace.onboarding import onboard
    from config import get_settings

    store = MemoryStore()
    store.startup_name = None
    store.website = "https://linear.app"
    result = await onboard(store, get_settings())
    assert result.pages_read and result.facts_recorded >= 5
    assert result.startup_name and "linear" in result.startup_name.lower()
    facts = await store.facts()
    print("\nPAGES", result.pages_read, "\nQUESTIONS", result.open_questions)
    for f in facts:
        print(f"FACT [{f.topic}/{f.confidence}] {f.claim}  <- {f.source_url}")
    assert {f.topic for f in facts} >= {"offer"}
    assert all(f.source_url in result.pages_read for f in facts)


async def test_reply_streams_from_the_real_model():
    from agents.lace.graph import build_lace_graph
    from langchain_core.messages import AIMessage

    graph = build_lace_graph(MemoryStore())
    tokens: list[str] = []
    resets = 0
    final, messages = None, []
    async for mode, chunk in graph.astream(
        {"messages": [HumanMessage(content="Search the web for what Linear (linear.app) is, then describe it in 3 sentences.")]},
        stream_mode=["custom", "values"],
    ):
        if mode == "custom" and "token" in chunk:
            tokens.append(chunk["token"])
        elif mode == "custom" and chunk.get("reset"):
            resets += 1
        elif mode == "values":
            messages = chunk["messages"]
            final = messages[-1]
    assert isinstance(final, AIMessage) and not final.tool_calls
    assert any(isinstance(m, ToolMessage) for m in messages), "it answered without searching"
    assert len(tokens) > 5, "the reply arrived in one piece"
    assert final.content.strip() in "".join(tokens)


async def test_defines_an_icp_from_what_it_learned():
    from agents.lace.graph import build_lace_graph
    from agents.lace.onboarding import onboard
    from config import get_settings

    store = MemoryStore()
    store.startup_name, store.website = None, "https://linear.app"
    await onboard(store, get_settings())
    graph = build_lace_graph(store)
    out = await graph.ainvoke({"messages": [HumanMessage(content="Who should we be selling to? Work out our ideal customer profile.")]})
    icp = store.saved_icp
    print("\nICP", icp.model_dump(exclude_defaults=True) if icp else None, "\nREPLY", out["messages"][-1].content)
    assert icp is not None and icp.buyer_type and (icp.industries or icp.buyer_personas) and icp.beachhead
