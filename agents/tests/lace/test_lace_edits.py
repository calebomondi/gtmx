"""The Lace's tools for changing what is saved: they act only through the
store, report what changed and what matched nothing, and keep within limits."""

import json

from agents.lace.edit_tools import MAX_IDS, build_edit_tools
from agents.schemas.lace import DraftSummary


async def _run(store, tool_name: str, **args) -> dict:
    tool = {t.name: t for t in build_edit_tools(store)}[tool_name]
    return json.loads(await tool.ainvoke(args))


async def test_removing_reports_what_changed_and_what_matched_nothing(store):
    result = await _run(store, "update_saved", kind="opportunity", ids=["o1", "o1", "x9"], verdict="remove")
    assert result["ok"] and result["summary"] == "Removed: opportunity o1. No match for: x9."
    assert store.saved_changes == [("opportunity", ["o1", "x9"], "remove")]
    nothing = await _run(store, "update_saved", kind="account", ids=["x1"], verdict="save")
    assert not nothing["ok"] and "No match for: x1" in nothing["summary"]


async def test_changes_take_a_bounded_list_of_ids(store):
    assert not (await _run(store, "update_saved", kind="competitor", ids=[], verdict="remove"))["ok"]
    many = [f"c{i}" for i in range(MAX_IDS + 1)]
    assert not (await _run(store, "update_saved", kind="competitor", ids=many, verdict="remove"))["ok"]


async def test_adding_a_contact_needs_a_company_and_a_name(store):
    added = await _run(store, "add_contact", company="Thalace", name="Kaleb Mokua", email=" kaleb@thalace.test ")
    assert added["ok"] and added["data"]["email"] == "kaleb@thalace.test" and added["data"]["approved"]
    unreachable = await _run(store, "add_contact", company="Thalace", name="No Address")
    assert unreachable["ok"] and "nothing can be drafted" in unreachable["summary"]
    assert not (await _run(store, "add_contact", company=" ", name="Kaleb"))["ok"]


async def test_a_draft_is_rewritten_or_discarded_never_sent(store):
    store.drafted = [DraftSummary(id="d1", channel="email", recipient="Amina", company="SunCulture", subject="Hi",
                                  body="Long note")]
    assert not (await _run(store, "edit_draft", draft_id="d1"))["ok"]
    assert not (await _run(store, "edit_draft", draft_id="d1", body="  "))["ok"]
    rewritten = await _run(store, "edit_draft", draft_id="d1", body="Short note")
    assert rewritten["ok"] and store.drafted[0].body == "Short note"
    assert not (await _run(store, "edit_draft", draft_id="d9", body="x"))["ok"]
    discarded = await _run(store, "discard_drafts", ids=["d1"])
    assert discarded["summary"] == "Discarded drafts to: Amina." and store.drafted == []
    assert "send" not in " ".join(t.name for t in build_edit_tools(store))
