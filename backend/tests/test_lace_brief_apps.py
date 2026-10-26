"""A brief also posted to the founder's Slack channel and saved under their
Notion page, as their settings say: recorded as app actions, never twice."""

import json
import uuid
from datetime import UTC, datetime

import psycopg

from backend.app.services import lace_brief_apps
from backend.tests.helpers import stub_accounts
from backend.tests.test_lace_apps import _lace
from backend.tests.test_social_actions import composio  # noqa: F401 -- fixture
from config import settings

BODY = "**3 replies** this week.\n- Samir asked about pricing"


def _setup(slack: str | None = None, notion: str | None = None, telegram: str | None = None) -> uuid.UUID:
    lace = _lace()
    with psycopg.connect(settings.database_url, autocommit=True) as conn:
        for platform, key, value in [("slack", "brief_channel", slack), ("notion", "brief_page", notion),
                                     ("telegram", "brief_chat", telegram)]:
            if value:
                conn.execute("INSERT INTO lace_apps (id, lace_id, platform, enabled, settings) VALUES (%s, %s, %s, true, %s)",
                             (uuid.uuid4(), lace, platform, json.dumps({key: value})))
        return conn.execute("INSERT INTO lace_briefs (id, lace_id, digest, body, created_at, posted_at)"
                            " VALUES (%s, %s, 'd', %s, %s, %s) RETURNING id",
                            (uuid.uuid4(), lace, BODY, datetime(2026, 10, 24, 7, tzinfo=UTC),
                             datetime.now(UTC))).fetchone()[0]


def _actions(brief) -> list[tuple]:
    with psycopg.connect(settings.database_url) as conn:
        return conn.execute("SELECT app, status, title FROM lace_app_actions WHERE arguments->>'brief_id' = %s"
                            " ORDER BY app DESC", (str(brief),)).fetchall()


async def test_a_brief_goes_where_the_settings_say_once(composio, monkeypatch):  # noqa: F811
    stub_accounts(monkeypatch, {"slack", "notion"})
    composio["answers"] = {"SLACK_SEND_MESSAGE": {"ok": True, "channel": "C1"},
                           "NOTION_CREATE_NOTION_PAGE": {"id": "pg1", "url": "https://notion.so/pg1"}}
    brief = _setup(slack="founders", notion="1a2b3c4d-5e6f-7a8b-9c0d-1e2f3a4b5c6d")
    await lace_brief_apps.deliver(brief)
    await lace_brief_apps.deliver(brief)  # a second call sends nothing more
    assert _actions(brief) == [("slack", "done", "Brief posted in #founders"),
                               ("notion", "done", "Brief saved in Notion: Ada's brief, Sat 24 Oct 2026")]
    tools = [tool for tool, _ in composio["calls"]]
    assert tools == ["SLACK_SEND_MESSAGE", "NOTION_CREATE_NOTION_PAGE", "NOTION_ADD_MULTIPLE_PAGE_CONTENT"]
    assert composio["calls"][0][1]["markdown_text"].startswith("*Ada's brief*\n\n**3 replies**")


async def test_nothing_goes_without_a_setting_or_a_connection(composio, monkeypatch):  # noqa: F811
    stub_accounts(monkeypatch, {"notion"})  # Slack set, but not connected
    brief = _setup(slack="founders")
    await lace_brief_apps.deliver(brief)
    assert composio["calls"] == [] and _actions(brief) == []


async def test_a_failed_post_is_recorded(composio, monkeypatch):  # noqa: F811
    stub_accounts(monkeypatch, {"slack"})
    composio["answers"] = {"SLACK_SEND_MESSAGE": {"error": "channel_not_found"}}
    brief = _setup(slack="nowhere")
    await lace_brief_apps.deliver(brief)
    assert _actions(brief) == [("slack", "failed", "Brief posted in #nowhere")]


def test_a_long_brief_is_cut_for_slack():
    class Lace:
        name = "Ada"
    text = lace_brief_apps._slack_text(Lace(), "x" * 5000)
    assert len(text) == lace_brief_apps.SLACK_CHARS and text.endswith("…the rest is in Thalace.")


async def test_a_brief_goes_to_a_telegram_chat_as_plain_text(composio, monkeypatch):  # noqa: F811
    stub_accounts(monkeypatch, {"telegram"})
    composio["answers"] = {"TELEGRAM_SEND_MESSAGE": {"ok": True, "result": {"message_id": 42}}}
    brief = _setup(telegram="@shanga_team")
    await lace_brief_apps.deliver(brief)
    assert _actions(brief) == [("telegram", "done", "Brief sent to @shanga_team on Telegram")]
    sent = composio["calls"][0][1]
    assert sent["chat_id"] == "@shanga_team" and sent["text"].startswith("Ada's brief\n\n**3 replies**")
    assert "parse_mode" not in sent
