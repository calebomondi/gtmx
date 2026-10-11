"""Search Anything: finds each kind by name, only ever the caller's own."""

import uuid

import psycopg

from backend.tests.helpers import make_user
from config import settings

URL = f"{settings.api_v1_str}/search"


def _hits(client, q):
    response = client.get(URL, params={"q": q})
    assert response.status_code == 200
    return [(h["kind"], h["title"]) for h in response.json()["hits"]]


def _seed_signal(user_id, workspace_id, title, *, dismissed=False):
    with psycopg.connect(settings.database_url, autocommit=True) as conn:
        conn.execute(
            "INSERT INTO signals (id, user_id, workspace_id, category, title, entity, summary, reason, dismissed)"
            " VALUES (%s, %s, %s, 'competitor', %s, '', '', '', %s)",
            (uuid.uuid4(), user_id, workspace_id, title, dismissed),
        )


def test_finds_every_kind_by_name(client, user, owned):
    _seed_signal(user.id, owned["workspace"], "Acme raised a Series B")
    _seed_signal(user.id, owned["workspace"], "Acme dismissed news", dismissed=True)
    assert set(_hits(client, "owner")) == {("workspace", "Owner Workspace"), ("project", "Owner Project")}
    assert set(_hits(client, "ACME")) == {("account", "Acme"), ("signal", "Acme raised a Series B")}
    assert [kind for kind, _ in _hits(client, "rival")] == ["competitor"]


def test_hit_carries_its_workspace(client, owned):
    [hit] = [h for h in client.get(URL, params={"q": "acme"}).json()["hits"] if h["kind"] == "account"]
    assert hit["workspace_id"] == owned["workspace"]
    assert hit["subtitle"] == "Owner Workspace"


def test_never_returns_another_users_data(client, owned):
    client.sign_in(make_user("Stranger"))
    assert _hits(client, "owner") == []
    assert _hits(client, "acme") == []


def test_names_starting_with_the_query_rank_first(client, user, seed_workspace):
    seed_workspace(user.id, "Big Acme")
    seed_workspace(user.id, "Acme Labs")
    assert [title for _, title in _hits(client, "acme")] == ["Acme Labs", "Big Acme"]


def test_short_and_wildcard_queries_match_nothing(client, owned):
    assert _hits(client, "a") == []
    assert _hits(client, "%%") == []
    assert _hits(client, "__") == []
    assert client.get(URL, params={"q": "x" * 101}).status_code == 422
