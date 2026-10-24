"""The Lace's Asana tools: open tasks counted in code, and a follow-up task as
a proposal the founder approves."""

import json
from datetime import date

import pytest

from agents.lace.asana_tools import summarise_tasks
from agents.lace.tools import build_tools

TODAY = date(2026, 10, 24)
TASKS = [{"name": "Send deck", "due_on": "2026-10-20"}, {"name": "Call Joe", "due_on": "2026-10-24"},
         {"name": "Plan Q1", "due_on": "2026-12-01"}, {"name": "Read notes", "due_on": None}]


class Apps:
    def __init__(self, tasks=None):
        self.tasks = tasks

    async def asana_tasks(self):
        return self.tasks


def _tools(store, settings, apps):
    return {t.name: t for t in build_tools(store, settings, apps=apps)}


async def _run(tool, **args) -> dict:
    return json.loads(await tool.ainvoke(args))


def test_open_tasks_are_counted_in_code():
    assert summarise_tasks(TASKS, TODAY) == {"open": 4, "overdue": 1, "due_soon": 1, "no_date": 1}


async def test_listing_puts_the_oldest_due_first(store, settings):
    out = await _run(_tools(store, settings, Apps(TASKS))["list_tasks"])
    assert out["ok"] and out["data"]["counts"]["open"] == 4
    assert [t["name"] for t in out["data"]["tasks"]] == ["Send deck", "Call Joe", "Plan Q1", "Read notes"]


async def test_without_asana_it_says_so(store, settings):
    out = await _run(_tools(store, settings, Apps(None))["list_tasks"])
    assert not out["ok"] and "isn't connected" in out["error"]


async def test_a_follow_up_is_a_proposal(store, settings):
    out = await _run(_tools(store, settings, Apps())["create_follow_up_task"], name="Call Samir about pricing",
                     notes="He asked for annual terms.", due_on="2026-10-28")
    assert out["data"]["ui"][0]["preview"] == "Call Samir about pricing\nDue 2026-10-28\nHe asked for annual terms."
    assert store.proposed[0].arguments == {"name": "Call Samir about pricing", "notes": "He asked for annual terms.",
                                           "due_on": "2026-10-28"}


@pytest.mark.parametrize("args, said", [({"name": " "}, "a name"), ({"name": "x", "due_on": "next week"}, "YYYY-MM-DD")])
async def test_a_bad_task_is_refused(store, settings, args, said):
    out = await _run(_tools(store, settings, Apps())["create_follow_up_task"], **args)
    assert not out["ok"] and said in out["error"] and store.proposed == []
