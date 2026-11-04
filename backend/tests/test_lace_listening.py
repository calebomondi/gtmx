"""Listening on a Lace's social accounts: what was said since the last
listen, sorted, passed to the Lace; a scheduled listen with nothing to say
or nothing to listen on stays quiet."""

import uuid
from datetime import UTC, datetime, timedelta

import psycopg
from langchain_core.messages import AIMessage

from agents.lace.apps import AppError
from agents.schemas.listening import HeardItem
from backend.app.database.connect import AsyncSessionLocal
from backend.app.runs import listening_jobs, manager
from backend.app.services import lace_listening
from backend.app.services.lace_apps import DbLaceApps
from backend.tests.test_lace_jobs import _runs, _wait_for_turns, lace  # noqa: F401 -- fixture
from backend.tests.test_laces_api import lace_runtime  # noqa: F401 -- fixture
from backend.tests.test_runs import _wait_for_status
from config import settings

NOW = datetime.now(UTC)


def _apps(monkeypatch, x=None, instagram=None, facebook=None):
    async def mentions(self):
        if isinstance(x, Exception):
            raise x
        return x

    async def comments(self, platform, posts):
        return {"instagram": instagram, "facebook": facebook}[platform]
    monkeypatch.setattr(DbLaceApps, "x_mentions", mentions)
    monkeypatch.setattr(DbLaceApps, "my_comments", comments)


def _sorted(monkeypatch) -> list:
    seen = []

    def sort(startup, facts, items):
        seen.extend(items)
        return [(item, HeardItem(ref="1", kind="lead" if "clinic" in item["text"] else "feedback",
                                 note=f"about {item['author']}")) for item in items]
    monkeypatch.setattr(listening_jobs, "sort_heard", sort)
    return seen


def test_a_listen_passes_on_leads_and_feedback_since_the_last(client, lace, lace_runtime, user, monkeypatch):  # noqa: F811
    _apps(monkeypatch, x=[{"handle": "jane", "text": "We run 4 clinics, does it fit?", "url": "https://x.com/i/1",
                          "date": NOW.isoformat()},
                         {"handle": "old", "text": "Ancient clinic tweet", "url": "https://x.com/i/0",
                          "date": (NOW - timedelta(days=30)).isoformat()}],
          instagram=[{"author": "tom", "text": "Pricing is confusing", "post_url": "https://instagram.com/p/1",
                      "date": NOW.isoformat()}],
          facebook=AppError("Link the Facebook Page"))
    heard = _sorted(monkeypatch)
    lace_runtime.append(AIMessage(content="Jane runs 4 clinics: worth a reply."))
    run = client.portal.call(manager.request_lace_job, "lace_listening", user.id, uuid.UUID(lace), {}).run
    run = client.portal.call(_wait_for_status, run.id, {"completed"})
    # The first listen looks back a week: the month-old mention is left out.
    assert [item["author"] for item in heard] == ["jane", "tom"] and run.progress == {"heard": 2, "kept": 2}
    update = client.portal.call(_wait_for_turns, lace, 1)[-1].input["updates"][0]
    assert update.startswith("Listened on X, Instagram: 2 new mentions and comments.")
    assert "Leads worth engaging:\n- [X] @jane: about jane (https://x.com/i/1)" in update
    assert "Feedback:\n- [Instagram] @tom: about tom (https://instagram.com/p/1)" in update
    assert "Couldn't read Facebook (Link the Facebook Page)." in update


def test_a_scheduled_listen_with_nothing_on_is_quiet(client, lace, lace_runtime, user, monkeypatch):  # noqa: F811
    _apps(monkeypatch)
    run = client.portal.call(manager.start_lace_job, "lace_listening", user.id, uuid.UUID(lace), {"scheduled": True})
    run = client.portal.call(_wait_for_status, run.id, {"completed"})
    assert run.progress == {"heard": 0, "kept": 0}
    with psycopg.connect(settings.database_url) as conn:
        assert conn.execute("SELECT count(*) FROM lace_events").fetchone()[0] == 0


def test_asked_with_nothing_on_says_how_to_connect(client, lace, lace_runtime, user, monkeypatch):  # noqa: F811
    _apps(monkeypatch)
    lace_runtime.append(AIMessage(content="Connect X first."))
    run = client.portal.call(manager.start_lace_job, "lace_listening", user.id, uuid.UUID(lace), {})
    client.portal.call(_wait_for_status, run.id, {"failed"})
    update = client.portal.call(_wait_for_turns, lace, 1)[-1].input["updates"][0]
    assert "No social account is on for this Lace" in update


def test_a_lace_listened_to_recently_is_not_due(client, lace, user):  # noqa: F811
    async def due():
        async with AsyncSessionLocal() as db:
            return [str(lace_id) for lace_id, _ in await lace_listening.laces_due(db)]
    assert client.portal.call(due) == [lace]
    with psycopg.connect(settings.database_url, autocommit=True) as conn:
        conn.execute("INSERT INTO runs (id, user_id, lace_id, kind, status) VALUES (%s, %s, %s, 'lace_listening',"
                     " 'completed')", (uuid.uuid4(), user.id, lace))
    assert client.portal.call(due) == []
