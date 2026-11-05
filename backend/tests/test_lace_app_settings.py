"""Which apps a Lace may use: every connected one, the founder's shared
account where the Lace has none of its own, until switched off; switching off
stops the Lace using an app, however connected; settings are kept per Lace."""

import uuid

import pytest

from agents.lace.app_actions import propose
from agents.schemas.lace import ProposedAction
from backend.app.database.connect import AsyncSessionLocal
from backend.app.services import connections as connection_service
from backend.app.services.lace_store import DbLaceStore
from backend.tests.helpers import make_user, stub_accounts
from backend.tests.test_lace_jobs import lace  # noqa: F401 -- fixture
from backend.tests.test_laces_api import API, _create, lace_runtime  # noqa: F401 -- fixture


@pytest.fixture
def connected(monkeypatch):
    stub_accounts(monkeypatch, {"gmail", "hubspot", "linkedin"})


def _apps(client, lace_id) -> dict:
    return {a["platform"]: a for a in client.get(f"{API}/laces/{lace_id}/apps").json()}


def test_every_app_is_listed_with_its_connection_and_switch(client, lace, lace_runtime, connected):  # noqa: F811
    apps = _apps(client, lace)
    assert set(apps) == {a.platform for a in connection_service.APPS}
    assert (apps["hubspot"]["connected"], apps["hubspot"]["group"], apps["slack"]["connected"]) == (True, "crm", False)
    # One Lace: everything is on for it.
    assert apps["gmail"]["enabled"] and apps["hubspot"]["enabled"]


def test_with_two_laces_each_uses_the_shared_accounts(client, lace, lace_runtime, connected):  # noqa: F811
    second = _create(client, name="Second", website="second.test").json()["lace"]["id"]
    for lace_id in (lace, second):
        apps = _apps(client, lace_id)
        assert apps["hubspot"]["account"] == "shared" and apps["hubspot"]["enabled"]
        assert apps["gmail"]["enabled"] and apps["linkedin"]["enabled"]
    # Switched off in one Lace, it stays on in the other.
    off = client.put(f"{API}/laces/{lace}/apps/hubspot", json={"enabled": False}).json()
    assert not off["enabled"] and off["settings"] == {}
    assert _apps(client, second)["hubspot"]["enabled"]


def test_settings_are_kept_per_lace(client, lace, lace_runtime, connected):  # noqa: F811
    saved = client.put(f"{API}/laces/{lace}/apps/slack", json={"settings": {"brief_channel": "#Founders"}}).json()
    assert saved["settings"] == {"brief_channel": "founders"} and saved["enabled"]
    assert client.put(f"{API}/laces/{lace}/apps/slack", json={"enabled": False}).json()["settings"] == {
        "brief_channel": "founders"}
    assert client.put(f"{API}/laces/{lace}/apps/myspace", json={"enabled": True}).status_code == 404
    client.sign_in(make_user("Intruder"))
    assert client.get(f"{API}/laces/{lace}/apps").status_code == 404
    assert client.put(f"{API}/laces/{lace}/apps/slack", json={"enabled": True}).status_code == 404


def test_an_app_switched_off_is_not_used(client, lace, lace_runtime, connected):  # noqa: F811
    client.put(f"{API}/laces/{lace}/apps/linkedin", json={"enabled": False})
    proposal = ProposedAction(app="linkedin", action="publish_post", title="Post on LinkedIn", preview="Hi",
                              arguments={"text": "Hi"})
    card = client.portal.call(propose, DbLaceStore(AsyncSessionLocal, uuid.UUID(lace)), proposal).data["ui"][0]
    refused = client.post(f"{API}/laces/{lace}/app-actions/{card['id']}/approve")
    assert refused.status_code == 409 and "switched off for this Lace" in refused.json()["detail"]


def test_settings_are_checked_per_app(client, lace, lace_runtime, connected):  # noqa: F811
    page = "https://www.notion.so/acme/Briefs-1a2b3c4d5e6f7a8b9c0d1e2f3a4b5c6d"
    saved = client.put(f"{API}/laces/{lace}/apps/notion", json={"settings": {"brief_page": page}}).json()
    assert saved["settings"] == {"brief_page": "1a2b3c4d-5e6f-7a8b-9c0d-1e2f3a4b5c6d"}
    for platform, settings in [("notion", {"brief_page": "my briefs page"}), ("slack", {"brief_channel": "#a b"}),
                               ("slack", {"colour": "red"}), ("gmail", {"brief_channel": "sales"})]:
        assert client.put(f"{API}/laces/{lace}/apps/{platform}", json={"settings": settings}).status_code == 422, settings
    # An empty value clears the setting.
    assert client.put(f"{API}/laces/{lace}/apps/notion", json={"settings": {"brief_page": ""}}).json()["settings"] == {}


def test_the_telegram_brief_chat_is_checked(client, lace, lace_runtime, connected):  # noqa: F811
    saved = client.put(f"{API}/laces/{lace}/apps/telegram", json={"settings": {"brief_chat": "https://t.me/shanga_team"}})
    assert saved.json()["settings"] == {"brief_chat": "@shanga_team"}
    refused = client.put(f"{API}/laces/{lace}/apps/telegram", json={"settings": {"brief_chat": "my group"}})
    assert refused.status_code == 422 and "t.me link" in refused.json()["detail"]


def test_a_page_account_not_linked_to_the_lace_is_flagged(client, lace, lace_runtime, user, monkeypatch):  # noqa: F811
    import psycopg
    from config import settings
    stub_accounts(monkeypatch, {"facebook", "instagram", "gmail"})
    apps = _apps(client, lace)
    assert (apps["facebook"]["needs_link"], apps["instagram"]["needs_link"]) == (True, True)
    assert not apps["gmail"]["needs_link"] and not apps["telegram"]["needs_link"]  # not connected: nothing to link
    with psycopg.connect(settings.database_url, autocommit=True) as conn:
        conn.execute("INSERT INTO lace_channels (id, lace_id, user_id, platform, account_id, account_name)"
                     " VALUES (%s, %s, %s, 'facebook', 'pg_1', 'Thalace')", (uuid.uuid4(), lace, user.id))
    assert not _apps(client, lace)["facebook"]["needs_link"]
