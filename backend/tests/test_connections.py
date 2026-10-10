"""Channel connections through Composio: per-user listing, Connect Links only
for available channels, and disconnect only for the owner."""

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
        self.deleted, self.authorized = [], []
        self.connected_accounts = self

    def list(self, user_ids, toolkit_slugs, statuses):
        return SimpleNamespace(items=[a for a in self.accounts.values() if a.user_id in user_ids])

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
        "gmail": True, "linkedin": True, "instagram": True, "tiktok": False, "x": False,
    }
    rows = {(c["id"], c["platform"], c["status"], c["display_name"]) for c in body["connections"]}
    assert rows == {("ca_live", "gmail", "live", "jane@acme.com"), ("ca_x", "x", "needs_attention", None)}


def test_connect_link_for_available_channels_only(client, user, composio, monkeypatch):
    assert client.post(f"{API}/linkedin").json() == {"redirect_url": "https://connect.example/linkedin"}
    assert composio.authorized[0][:2] == (str(user.id), "linkedin")
    assert composio.authorized[0][2].endswith("/accounts?connected=linkedin")
    assert client.post(f"{API}/tiktok").status_code == 409  # needs our own OAuth app
    assert client.post(f"{API}/facebook").status_code == 404

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
