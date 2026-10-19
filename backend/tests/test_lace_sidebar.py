"""The Lace list as the sidebar shows it: most recently active first, each
with its mood (working, or waiting on the founder), and pinning."""

import uuid

import psycopg

from backend.tests.helpers import make_user
from backend.tests.test_lace_jobs import lace  # noqa: F401 -- fixture
from backend.tests.test_laces_api import API, lace_runtime  # noqa: F401 -- fixture
from backend.tests.test_runs import _wait_for_status
from config import settings


def _sql(query, *params):
    with psycopg.connect(settings.database_url, autocommit=True) as conn:
        conn.execute(query, params)


def _listed(client) -> dict:
    return {row["id"]: row for row in client.get(f"{API}/laces").json()}


def test_mood_follows_what_is_going_on(client, lace, user):  # noqa: F811
    assert _listed(client)[lace]["mood"] is None  # onboarded, nothing waiting

    run_id = uuid.uuid4()
    _sql("INSERT INTO runs (id, user_id, lace_id, kind, status) VALUES (%s, %s, %s, 'lace_competitors', 'running')",
         run_id, user.id, lace)
    assert _listed(client)[lace]["mood"] == "thinking"
    _sql("UPDATE runs SET status = 'completed' WHERE id = %s", run_id)

    draft = uuid.uuid4()
    _sql("INSERT INTO lace_outreach (id, lace_id, user_id, channel, recipient_company, body) VALUES"
         " (%s, %s, %s, 'email', 'SunCulture', 'Hi')", draft, lace, user.id)
    assert _listed(client)[lace]["mood"] == "alert"  # a draft waits to be sent
    _sql("UPDATE lace_outreach SET status = 'sent' WHERE id = %s", draft)
    assert _listed(client)[lace]["mood"] is None

    _sql("INSERT INTO lace_outreach (id, lace_id, user_id, channel, direction, status, recipient_company, body)"
         " VALUES (%s, %s, %s, 'email', 'inbound', 'received', 'SunCulture', 'Tell me more')",
         uuid.uuid4(), lace, user.id)
    assert _listed(client)[lace]["mood"] == "alert"  # a reply not yet read


def test_most_recently_active_first(client, lace, lace_runtime, user):  # noqa: F811
    second = client.post(f"{API}/laces", json={"name": "Bo", "website": "bo.test"}).json()
    client.portal.call(_wait_for_status, uuid.UUID(second["run_id"]), {"completed"})
    assert [row["name"] for row in client.get(f"{API}/laces").json()] == ["Bo", "Ada"]
    _sql("INSERT INTO runs (id, user_id, lace_id, kind, status, created_at) VALUES"
         " (%s, %s, %s, 'lace_turn', 'completed', now() + interval '1 minute')", uuid.uuid4(), user.id, lace)
    rows = client.get(f"{API}/laces").json()
    assert [row["name"] for row in rows] == ["Ada", "Bo"] and rows[0]["last_active_at"] > rows[1]["last_active_at"]


def test_pin_and_unpin(client, lace):  # noqa: F811
    assert _listed(client)[lace]["pinned"] is False
    assert client.patch(f"{API}/laces/{lace}", json={"pinned": True}).json()["pinned"] is True
    assert _listed(client)[lace]["pinned"] is True
    assert client.patch(f"{API}/laces/{lace}", json={}).json()["pinned"] is True  # nothing to change
    assert client.patch(f"{API}/laces/{lace}", json={"pinned": False}).json()["pinned"] is False
    client.sign_in(make_user("Intruder"))
    assert client.patch(f"{API}/laces/{lace}", json={"pinned": True}).status_code == 404
