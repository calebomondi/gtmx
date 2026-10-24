"""Channel connections through Composio: per-user listing, Connect Links only
for available channels, and disconnect only for the owner."""

import uuid
from datetime import UTC, datetime
from types import SimpleNamespace

import pytest

from backend.app.services import connections as svc
from backend.tests.helpers import make_user
from config import settings

API = "/api/v1/connections"


def _account(id_, user_id, toolkit, status, name=None):
    now = datetime.now(UTC)
    return SimpleNamespace(
        id=id_, user_id=user_id, status=status, toolkit=SimpleNamespace(slug=toolkit),
        created_at=now, updated_at=now,
        model_dump=lambda: {"state": {"val": {"displayName": name}} if name else None},
    )


class FakeComposio:
    def __init__(self, accounts):
        self.accounts = {a.id: a for a in accounts}
        self.deleted, self.authorized, self.executed = [], [], []
        self.identities = {"GMAIL_GET_PROFILE": {"emailAddress": "jane.doe@acme.com"}}
        self.connected_accounts = self

    def list(self, toolkit_slugs, statuses, user_ids=None, limit=None, cursor=None, timeout=None):
        items = [a for a in self.accounts.values()
                 if (user_ids is None or a.user_id in user_ids) and a.status in statuses
                 and a.toolkit.slug in toolkit_slugs]
        if limit is None:
            return SimpleNamespace(items=items, next_cursor=None)
        start = int(cursor or 0)
        more = start + limit < len(items)
        return SimpleNamespace(items=items[start:start + limit], next_cursor=str(start + limit) if more else None)

    def get(self, id_):
        return self.accounts.get(id_)

    def delete(self, id_, revoke_on_delete):
        self.deleted.append((id_, revoke_on_delete))

    def create(self, user_id, manage_connections, auth_configs):
        fake = self

        class Session:
            def authorize(self, toolkit, callback_url):
                fake.authorized.append((user_id, toolkit, callback_url, auth_configs))
                return SimpleNamespace(redirect_url=f"https://connect.example/{toolkit}")

            def execute(self, tool, arguments, **kwargs):
                if "account" in kwargs:  # what the live project answers
                    raise RuntimeError("The 'account' parameter is not supported for this project.")
                fake.executed.append(tool)
                data = fake.identities.get(tool)
                return SimpleNamespace(data=data, error=None if data else "unsupported", log_id="log")
        return Session()


@pytest.fixture
def composio(monkeypatch, user):
    fake = FakeComposio([
        _account("ca_live", str(user.id), "gmail", "ACTIVE", "jane@acme.com"),
        _account("ca_old", str(user.id), "gmail", "INITIATED"),  # stale link beside a live one
        _account("ca_x", str(user.id), "twitter", "EXPIRED"),
        _account("ca_other", "someone-else", "linkedin", "ACTIVE"),
    ])
    monkeypatch.setattr(svc, "_client", lambda: fake)
    return fake


def test_lists_only_the_users_connections(client, composio):
    body = client.get(API).json()
    assert {c["platform"]: c["available"] for c in body["channels"]} == {
        "gmail": True, "googlecalendar": True, "linkedin": True, "instagram": True, "facebook": True,
        "tiktok": False, "x": False,
        # Every second-wave app's sign-in is managed by Composio.
        "outlook": True, "whatsapp": True, "zoho": True, "hubspot": True, "googlesheets": True, "notion": True,
        "slack": True, "asana": True, "calendly": True,
    }
    rows = {(c["id"], c["platform"], c["status"], c["display_name"]) for c in body["connections"]}
    # The live account is labelled from the provider's own profile.
    assert rows == {("ca_live", "gmail", "live", "jane.doe@acme.com"), ("ca_x", "x", "needs_attention", None)}


def test_identities_are_read_once_and_forgotten_on_disconnect(client, composio):
    client.get(API)
    client.get(API)
    assert composio.executed == ["GMAIL_GET_PROFILE"]  # remembered after the first read
    assert client.delete(f"{API}/ca_live").status_code == 204
    composio.accounts["ca_live2"] = _account("ca_live2", composio.accounts["ca_live"].user_id, "gmail", "ACTIVE")
    composio.identities["GMAIL_GET_PROFILE"] = {"emailAddress": "new@acme.com"}
    labels = {c["id"]: c["display_name"] for c in client.get(API).json()["connections"]}
    assert labels["ca_live2"] == "new@acme.com"


@pytest.mark.parametrize("platform, data, label", [
    ("linkedin", {"localizedFirstName": "Wanjiru", "localizedLastName": "Kamau"}, "Wanjiru Kamau"),
    ("instagram", {"username": "mama_mboga"}, "@mama_mboga"),
    ("x", {"data": {"username": "gtmx"}}, "@gtmx"),
    ("facebook", {"name": "Acme Kenya"}, "Acme Kenya"),
    ("googlecalendar", {"id": "jane@acme.com", "summary": "Jane"}, "jane@acme.com"),
    ("linkedin", {}, None),
])
def test_identity_labels_per_platform(platform, data, label):
    assert svc._IDENTITY[platform][2](data) == label


def test_connect_link_for_available_channels_only(client, user, composio, monkeypatch):
    assert client.post(f"{API}/linkedin").json() == {"redirect_url": "https://connect.example/linkedin"}
    assert composio.authorized[0][:2] == (str(user.id), "linkedin")
    assert composio.authorized[0][2].endswith("/accounts?connected=linkedin")
    assert client.post(f"{API}/tiktok").status_code == 409  # needs our own OAuth app
    assert client.post(f"{API}/myspace").status_code == 404

    monkeypatch.setattr(settings, "composio_auth_configs", {"twitter": "ac_123"})
    assert client.post(f"{API}/x").status_code == 200
    assert composio.authorized[-1][1] == "twitter" and composio.authorized[-1][3] == {"twitter": "ac_123"}


def test_disconnect_only_own_connections(client, composio):
    assert client.delete(f"{API}/ca_other").status_code == 404
    assert client.delete(f"{API}/ca_missing").status_code == 404
    assert client.delete(f"{API}/ca_live").status_code == 204
    assert composio.deleted == [("ca_live", True)]
    client.sign_in(make_user("Intruder"))
    assert client.delete(f"{API}/ca_x").status_code == 404


async def test_live_by_user_pages_through_every_user(composio, user, monkeypatch):
    monkeypatch.setattr(svc, "_LIST_PAGE_SIZE", 1)
    other = uuid.uuid4()
    composio.accounts["ca_li"] = _account("ca_li", str(user.id), "linkedin", "ACTIVE")
    composio.accounts["ca_ig"] = _account("ca_ig", str(other), "instagram", "ACTIVE")
    live = await svc.live_by_user()
    # "someone-else" isn't a user id of ours; expired/initiated aren't live.
    assert live == {user.id: {"gmail", "linkedin"}, other: {"instagram"}}


def test_connect_returns_to_the_origin_the_user_started_from(client, composio, monkeypatch):
    monkeypatch.setattr(settings, "frontend_base_url", "http://localhost:5173")
    monkeypatch.setattr(settings, "allowed_origins", ["https://app.example.com"])
    for origin, expected in [
        ("http://127.0.0.1:5173", "http://127.0.0.1:5173"),  # loopback alias keeps the session
        ("https://app.example.com", "https://app.example.com"),
        ("https://evil.example", "http://localhost:5173"),  # never an arbitrary origin
        ("http://127.0.0.1:9999", "http://localhost:5173"),
    ]:
        client.post(f"{API}/linkedin", headers={"Origin": origin})
        assert composio.authorized[-1][2] == f"{expected}/accounts?connected=linkedin"


def test_connect_returns_to_an_app_page_only(client, composio, monkeypatch):
    monkeypatch.setattr(settings, "frontend_base_url", "http://localhost:5173")
    client.post(f"{API}/linkedin", params={"return_to": "/lace/abc/messaging"})
    assert composio.authorized[-1][2] == "http://localhost:5173/lace/abc/messaging?connected=linkedin"
    for bad in ["//evil.example/x", "https://evil.example", "/lace/../admin", "lace/x", "/x?y=1"]:
        assert client.post(f"{API}/linkedin", params={"return_to": bad}).status_code == 422, bad


def test_one_connection_per_app(client, composio):
    """Tools can't choose between two connections of the same app, so a second is refused."""
    refused = client.post(f"{API}/gmail")
    assert refused.status_code == 409 and "already have a Gmail account" in refused.json()["detail"]
    assert client.post(f"{API}/linkedin").status_code == 200  # another app is fine
