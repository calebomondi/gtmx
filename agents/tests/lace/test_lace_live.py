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
