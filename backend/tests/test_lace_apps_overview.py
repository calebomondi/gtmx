"""What a Lace is told about its apps: only those offered, each with whose
account it is and whether it may use it; a failure leaves the list out."""

import uuid

import pytest

from agents.lace.apps import AppError
from backend.app.database.connect import AsyncSessionLocal
from backend.app.services import lace_app_settings
from backend.app.services.lace_apps import DbLaceApps
from backend.tests.test_lace_jobs import lace  # noqa: F401 -- fixture
from backend.tests.test_laces_api import lace_runtime  # noqa: F401 -- fixture


def _app(platform, label, *, status, connected, enabled, account=None, available=True):
    return {"platform": platform, "label": label, "group": "docs", "available": available, "connected": connected,
            "status": status, "account": account, "account_name": None, "connection_id": None, "enabled": enabled,
            "settings": {}}


def test_the_overview_says_what_the_lace_can_use(client, lace, monkeypatch):  # noqa: F811
    async def listed(db, lace_row):
        return [_app("notion", "Notion", status="live", connected=True, enabled=True, account="own"),
                _app("slack", "Slack", status="needs_attention", connected=False, enabled=True, account="shared"),
                _app("asana", "Asana", status=None, connected=False, enabled=False),
                _app("whatsapp", "WhatsApp Business", status=None, connected=False, enabled=True, available=False)]
    monkeypatch.setattr(lace_app_settings, "list_for_lace", listed)
    apps = client.portal.call(DbLaceApps(AsyncSessionLocal, uuid.UUID(lace)).overview)
    assert [(a.platform, a.connected, a.needs_attention, a.enabled, a.account) for a in apps] == [
        ("notion", True, False, True, "own"), ("slack", True, True, True, "shared"), ("asana", False, False, False, None)]


def test_an_unreachable_composio_is_an_app_error(client, lace):  # noqa: F811
    # Tests can't reach Composio (see conftest), as when it is down.
    with pytest.raises(AppError, match="apps unavailable"):
        client.portal.call(DbLaceApps(AsyncSessionLocal, uuid.UUID(lace)).overview)


def test_an_app_read_by_handle_is_listed_even_when_it_cant_be_connected(client, lace, monkeypatch):  # noqa: F811
    async def listed(db, lace_row):
        x = _app("x", "X", status=None, connected=False, enabled=True, available=False)
        return [{**x, "settings": {"handle": "mokuakaleb"}},
                _app("tiktok", "TikTok", status=None, connected=False, enabled=True, available=False)]
    monkeypatch.setattr(lace_app_settings, "list_for_lace", listed)
    [x] = client.portal.call(DbLaceApps(AsyncSessionLocal, uuid.UUID(lace)).overview)
    assert (x.platform, x.connected, x.handle) == ("x", False, "mokuakaleb")
