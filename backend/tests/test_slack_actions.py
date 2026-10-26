"""Slack through a stubbed Composio, as Slack's documented response shapes:
searching messages for the Lace, and a post the founder approves."""

from backend.app.database.connect import AsyncSessionLocal
from backend.app.services import lace_apps, slack_actions
from backend.tests.helpers import stub_accounts
from backend.tests.test_lace_apps import _lace
from backend.tests.test_social_actions import _ctx, composio  # noqa: F401 -- fixture


async def test_the_lace_searches_slack(composio, monkeypatch):  # noqa: F811
    stub_accounts(monkeypatch, {"slack"})
    composio["answers"] = {"SLACK_SEARCH_MESSAGES": {"ok": True, "messages": {"matches": [
        {"text": "Acme wants a demo", "username": "wanjiru", "channel": {"name": "sales"}, "ts": "1761300000.0001",
         "permalink": "https://acme.slack.com/archives/C1/p1"},
        {"text": "", "username": "bot"},  # nothing to read
    ]}}}
    found = await lace_apps.DbLaceApps(AsyncSessionLocal, _lace()).slack_search("Acme")
    assert found == [{"text": "Acme wants a demo", "author": "wanjiru", "channel": "sales",
                      "date": "2025-10-24T10:00+00:00", "link": "https://acme.slack.com/archives/C1/p1"}]
    assert composio["calls"][0][1] == {"query": "Acme", "count": 20, "sort": "timestamp", "sort_dir": "desc"}


async def test_an_approved_post_goes_to_its_channel(composio):  # noqa: F811
    composio["answers"] = {"SLACK_SEND_MESSAGE": {"ok": True, "channel": "C42", "ts": "1.2"}}
    outcome = await slack_actions.post_message(_ctx("slack"), {"channel": "sales", "text": "*Two* replies today."})
    assert composio["calls"] == [("SLACK_SEND_MESSAGE", {"channel": "sales", "markdown_text": "*Two* replies today.",
                                                         "as_user": True})]
    assert (outcome.result, outcome.url) == ("Posted in #sales.", "https://slack.com/app_redirect?channel=C42")
