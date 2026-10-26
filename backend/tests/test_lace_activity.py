"""A Lace's Feed: activity written with the results it reports, read newest
first, marked read, and keeping the sidebar mascot alert until it is seen."""

import uuid
from datetime import UTC, datetime, timedelta

import psycopg
from langchain_core.messages import AIMessage

from agents.lace.store import JobBlocked
from backend.app.runs import lace_jobs, manager
from backend.app.services.lace_activity import names, plural
from backend.tests.helpers import make_user
from backend.tests.test_lace_jobs import RIVAL, _wait_for_turns, lace  # noqa: F401 -- fixture
from backend.tests.test_laces_api import API, lace_runtime  # noqa: F401 -- fixture
from backend.tests.test_runs import _wait_for_status
from config import settings


def test_names_and_plurals():
    assert names(["A"]) == "A" and names(["A", "B"]) == "A and B"
    assert names(["A", "B", "C", "D", "E"]) == "A, B, C and 2 more"
    assert plural(1, "new opportunity", "new opportunities") == "1 new opportunity"
    assert plural(3, "message") == "3 messages"


def _job(client, user, lace_id, kind="lace_competitors"):
    run = client.portal.call(manager.start_lace_job, kind, user.id, uuid.UUID(lace_id), {})
    return client.portal.call(_wait_for_status, run.id, {"completed", "failed"})


def _feed(client, lace_id, **params):
    return client.get(f"{API}/laces/{lace_id}/activity", params=params).json()


def test_a_hunt_shows_in_the_feed(client, lace, lace_runtime, user, monkeypatch):  # noqa: F811
    monkeypatch.setattr(lace_jobs, "find_competitors", lambda profile, facts, focus: [RIVAL])
    lace_runtime.append(AIMessage(content="I found Rival."))
    assert _job(client, user, lace).status == "completed"
    client.portal.call(_wait_for_turns, lace, 1)
    [item] = _feed(client, lace)
    assert (item["kind"], item["title"], item["summary"], item["read_at"]) == (
        "competitors_found", "Found 1 new competitor", "Rival", None)


def test_a_failed_search_shows_why(client, lace, lace_runtime, user, monkeypatch):  # noqa: F811
    def blocked(profile, facts, focus):
        raise JobBlocked("Not enough is known about what the startup sells.")
    monkeypatch.setattr(lace_jobs, "find_competitors", blocked)
    lace_runtime.append(AIMessage(content="I couldn't search yet."))
    assert _job(client, user, lace).status == "failed"
    client.portal.call(_wait_for_turns, lace, 1)
    [item] = _feed(client, lace)
    assert (item["kind"], item["title"]) == ("job_failed", "The competitor search failed")
    assert item["summary"] == "Not enough is known about what the startup sells."


def _add(lace_id, title, minutes_ago, kind="drafts_ready"):
    with psycopg.connect(settings.database_url, autocommit=True) as conn:
        conn.execute("INSERT INTO lace_activity (id, lace_id, kind, title, created_at) VALUES (%s, %s, %s, %s, %s)",
                     (uuid.uuid4(), lace_id, kind, title, datetime.now(UTC) - timedelta(minutes=minutes_ago)))


def test_newest_first_paging_and_read(client, lace):  # noqa: F811
    for i, title in enumerate(["newest", "middle", "oldest"]):
        _add(lace, title, minutes_ago=i)
    first = _feed(client, lace, limit=2)
    assert [a["title"] for a in first] == ["newest", "middle"]
    assert [a["title"] for a in _feed(client, lace, before=first[-1]["created_at"])] == ["oldest"]

    mood = lambda: {r["id"]: r for r in client.get(f"{API}/laces").json()}[lace]["mood"]  # noqa: E731
    assert mood() == "alert"  # unseen activity
    assert client.post(f"{API}/laces/{lace}/activity/read").json() == {"marked": 3}
    assert all(a["read_at"] for a in _feed(client, lace)) and mood() is None
    assert client.post(f"{API}/laces/{lace}/activity/read").json() == {"marked": 0}


def test_other_users_feed_is_not_found(client, lace):  # noqa: F811
    _add(lace, "private", 0)
    client.sign_in(make_user("Intruder"))
    assert client.get(f"{API}/laces/{lace}/activity").status_code == 404
    assert client.post(f"{API}/laces/{lace}/activity/read").status_code == 404


def test_the_home_feed_spans_the_founders_laces(client, lace, lace_runtime):  # noqa: F811
    other = client.post(f"{API}/laces", json={"name": "Bo", "website": "bo.test"}).json()
    client.portal.call(_wait_for_status, uuid.UUID(other["run_id"]), {"completed"})
    _add(lace, "from Ada", 2)
    _add(other["lace"]["id"], "from Bo", 1)
    feed = client.get(f"{API}/laces/activity").json()
    assert [(a["title"], a["lace_name"]) for a in feed] == [("from Bo", "Bo"), ("from Ada", "Ada")]
    assert client.get(f"{API}/laces/activity", params={"before": feed[0]["created_at"]}).json()[0]["title"] == "from Ada"
    with psycopg.connect(settings.database_url, autocommit=True) as conn:
        conn.execute("UPDATE laces SET status = 'archived' WHERE id = %s", (other["lace"]["id"],))
    assert [a["title"] for a in client.get(f"{API}/laces/activity").json()] == ["from Ada"]
    client.sign_in(make_user("Intruder"))
    assert client.get(f"{API}/laces/activity").json() == []


def test_the_funnel_counts_accounts_at_each_step(client, lace, user):  # noqa: F811
    accounts = [uuid.uuid4() for _ in range(3)]
    with psycopg.connect(settings.database_url, autocommit=True) as conn:
        for i, account in enumerate(accounts):
            conn.execute("INSERT INTO lace_accounts (id, lace_id, key, name, account_type, record) VALUES"
                         " (%s, %s, %s, %s, 'company', '{}')", (account, lace, f"a{i}.test", f"Acct {i}"))
        rows = [(accounts[0], "outbound", "sent", None), (accounts[0], "outbound", "sent", None),
                (accounts[1], "outbound", "sent", None), (accounts[2], "outbound", "draft", None),
                (accounts[0], "inbound", "received", "meeting_request"), (accounts[1], "inbound", "received", "not_now")]
        for account, direction, status, intent in rows:
            conn.execute("INSERT INTO lace_outreach (id, lace_id, user_id, account_id, channel, direction, status,"
                         " intent, recipient_company, body) VALUES (%s, %s, %s, %s, 'email', %s, %s, %s, 'X', 'b')",
                         (uuid.uuid4(), lace, user.id, account, direction, status, intent))
    assert client.get(f"{API}/laces/{lace}/funnel").json() == {"accounts": 3, "contacted": 2, "replied": 2,
                                                               "interested": 1}
    client.sign_in(make_user("Intruder"))
    assert client.get(f"{API}/laces/{lace}/funnel").status_code == 404
