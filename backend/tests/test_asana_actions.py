"""Asana through a stubbed Composio, as Asana's documented response shapes:
the founder's open tasks for the Lace, and the follow-up they approve."""

import pytest

from backend.app.database.connect import AsyncSessionLocal
from backend.app.services import asana_actions, lace_apps
from backend.app.services.lace_app_actions import ActionFailed
from backend.tests.helpers import stub_accounts
from backend.tests.test_lace_apps import _lace
from backend.tests.test_social_actions import _ctx, composio  # noqa: F401 -- fixture

WORKSPACES = {"data": [{"gid": "w1", "name": "Shanga"}]}


async def test_the_lace_reads_the_founders_open_tasks(composio, monkeypatch):  # noqa: F811
    stub_accounts(monkeypatch, {"asana"})
    composio["answers"] = {"ASANA_GET_MULTIPLE_WORKSPACES": WORKSPACES, "ASANA_GET_MULTIPLE_TASKS": {"data": [
        {"gid": "t1", "name": "Send deck", "due_on": "2026-10-20", "completed": False,
         "permalink_url": "https://app.asana.com/0/0/t1", "projects": [{"name": "Sales"}]},
        {"gid": "t2", "name": "Done thing", "completed": True},
    ]}}
    assert await lace_apps.DbLaceApps(AsyncSessionLocal, _lace()).asana_tasks() == [
        {"name": "Send deck", "due_on": "2026-10-20", "project": "Sales", "link": "https://app.asana.com/0/0/t1"}]
    assert composio["calls"][1][1]["workspace"] == "w1" and composio["calls"][1][1]["assignee"] == "me"


async def test_an_approved_follow_up_is_the_founders_task(composio):  # noqa: F811
    composio["answers"] = {"ASANA_GET_MULTIPLE_WORKSPACES": WORKSPACES,
                           "ASANA_CREATE_A_TASK": {"data": {"gid": "t9", "permalink_url": "https://app.asana.com/0/0/t9"}}}
    outcome = await asana_actions.create_task(_ctx("asana"), {"name": "Call Samir", "notes": "Annual terms",
                                                              "due_on": "2026-10-28"})
    assert composio["calls"][1] == ("ASANA_CREATE_A_TASK", {"data": {
        "name": "Call Samir", "notes": "Annual terms", "assignee": "me", "workspace": "w1", "due_on": "2026-10-28"},
        "opt_fields": ["permalink_url"]})
    assert (outcome.result, outcome.url) == ("Added “Call Samir” to your Asana tasks.", "https://app.asana.com/0/0/t9")


async def test_no_workspace_fails_with_why(composio):  # noqa: F811
    composio["answers"] = {"ASANA_GET_MULTIPLE_WORKSPACES": {"data": []}}
    with pytest.raises(ActionFailed, match="didn't list a workspace"):
        await asana_actions.create_task(_ctx("asana"), {"name": "x"})
