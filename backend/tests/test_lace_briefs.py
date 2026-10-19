"""The brief: due in the founder's own timezone, written by the Lace from a
digest of what happened, posted once, skipped when there is nothing to say."""

import uuid
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import psycopg
import pytest
from langchain_core.messages import AIMessage

from agents.lace.brief import brief_request
from backend.app.database.connect import AsyncSessionLocal
from backend.app.runs import scheduler
from backend.app.services import lace_briefs
from backend.tests.helpers import make_user
from backend.tests.test_lace_jobs import _runs, _wait_for_turns, lace  # noqa: F401 -- fixture
from backend.tests.test_laces_api import API, lace_runtime  # noqa: F401 -- fixture
from backend.tests.test_runs import _wait_for_status
from config import settings


def _lace(frequency="daily", hour=8, tz="Africa/Nairobi", last=None, status="active"):
    return SimpleNamespace(brief_frequency=frequency, brief_hour=hour, timezone=tz, last_brief_at=last, status=status)


@pytest.mark.parametrize("lace_kw, now, due", [
    ({}, datetime(2026, 10, 19, 4, 59, tzinfo=UTC), False),        # 07:59 in Nairobi
    ({}, datetime(2026, 10, 19, 5, 0, tzinfo=UTC), True),          # 08:00 in Nairobi
    ({"last": datetime(2026, 10, 19, 5, 0, tzinfo=UTC)}, datetime(2026, 10, 19, 20, 0, tzinfo=UTC), False),
    ({"last": datetime(2026, 10, 18, 5, 0, tzinfo=UTC)}, datetime(2026, 10, 19, 5, 30, tzinfo=UTC), True),
    ({"frequency": "weekly", "last": datetime(2026, 10, 14, 5, 0, tzinfo=UTC)},
     datetime(2026, 10, 19, 6, 0, tzinfo=UTC), False),
    ({"frequency": "weekly", "last": datetime(2026, 10, 12, 5, 0, tzinfo=UTC)},
     datetime(2026, 10, 19, 6, 0, tzinfo=UTC), True),
    ({"frequency": "off"}, datetime(2026, 10, 19, 12, 0, tzinfo=UTC), False),
    ({"status": "onboarding"}, datetime(2026, 10, 19, 12, 0, tzinfo=UTC), False),
    ({"tz": "Not/AZone", "hour": 9}, datetime(2026, 10, 19, 9, 0, tzinfo=UTC), True),  # unknown zone: UTC
])
def test_is_due_in_the_founders_timezone(lace_kw, now, due):
    assert lace_briefs.is_due(_lace(**lace_kw), now) is due


def test_the_request_carries_the_digest():
    text = brief_request("New opportunities:\n- [sell] Tender", "weekly", "since Mon")
    assert "weekly brief" in text and "- [sell] Tender" in text and "since Mon" in text


def _seed(lace_id, user_id):
    soon = datetime.now(UTC).date() + timedelta(days=3)
    with psycopg.connect(settings.database_url, autocommit=True) as conn:
        conn.execute("INSERT INTO lace_outreach (id, lace_id, user_id, channel, recipient_company, body) VALUES"
                     " (%s, %s, %s, 'email', 'SunCulture', 'Hi')", (uuid.uuid4(), lace_id, user_id))
        conn.execute("INSERT INTO lace_opportunities (id, lace_id, kind, title, url, url_key, deadline) VALUES"
                     " (%s, %s, 'sell', 'Fleet tracking tender', 'https://t.test', 't.test', %s)",
                     (uuid.uuid4(), lace_id, soon))


async def test_digest_sections_and_nothing_to_tell(lace, user):  # noqa: F811
    lace_id = uuid.UUID(lace)
    since = datetime.now(UTC) - timedelta(days=1)
    async with AsyncSessionLocal() as db:
        assert await lace_briefs.digest(db, lace_id, since, datetime.now(UTC).date()) == ""
    _seed(lace_id, user.id)
    async with AsyncSessionLocal() as db:
        text = await lace_briefs.digest(db, lace_id, since, datetime.now(UTC).date())
    assert "Drafts waiting for the founder to review and send:\n- SunCulture by email" in text
    assert "New opportunities:\n- [sell] Fleet tracking tender" in text
    assert "Opportunities closing within a week:\n- Fleet tracking tender: closes" in text


def _due_now(lace_id):
    with psycopg.connect(settings.database_url, autocommit=True) as conn:
        conn.execute("UPDATE laces SET brief_hour = 0, timezone = 'UTC', last_brief_at = NULL WHERE id = %s", (lace_id,))


def test_the_lace_posts_its_brief_once(client, lace, lace_runtime, user):  # noqa: F811
    _seed(lace, user.id)
    _due_now(lace)
    lace_runtime.append(AIMessage(content="Good morning. A draft to SunCulture is waiting, and a tender closes soon."))
    assert client.portal.call(scheduler.sweep_briefs) == 1
    turns = client.portal.call(_wait_for_turns, lace, 1)
    assert "brief_id" in turns[-1].input
    messages = client.get(f"{API}/laces/{lace}/messages").json()
    assert messages[-1] == {"role": "lace", "content": "Good morning. A draft to SunCulture is waiting, and a tender closes soon."}
    assert not any("Digest" in m["content"] for m in messages)  # the request is not shown
    with psycopg.connect(settings.database_url) as conn:
        body, posted = conn.execute("SELECT body, posted_at IS NOT NULL FROM lace_briefs").fetchone()
    assert body.startswith("Good morning") and posted
    with psycopg.connect(settings.database_url) as conn:
        kind, summary, ref_type = conn.execute("SELECT kind, summary, ref_type FROM lace_activity").fetchone()
    assert (kind, ref_type) == ("brief", "brief") and summary.startswith("Good morning")
    assert client.portal.call(scheduler.sweep_briefs) == 0  # once a day


def test_nothing_to_tell_means_no_brief(client, lace, lace_runtime):  # noqa: F811
    _due_now(lace)
    assert client.portal.call(scheduler.sweep_briefs) == 0
    with psycopg.connect(settings.database_url) as conn:
        assert conn.execute("SELECT count(*) FROM lace_briefs").fetchone()[0] == 0
        assert conn.execute("SELECT last_brief_at IS NOT NULL FROM laces WHERE id = %s", (lace,)).fetchone()[0]


def test_a_busy_lace_gets_its_brief_at_the_next_sweep(client, lace, lace_runtime, user):  # noqa: F811
    _seed(lace, user.id)
    _due_now(lace)
    with psycopg.connect(settings.database_url, autocommit=True) as conn:
        busy = conn.execute("INSERT INTO runs (id, user_id, lace_id, kind, status) VALUES (%s, %s, %s, 'lace_turn',"
                            " 'running') RETURNING id", (uuid.uuid4(), user.id, lace)).fetchone()[0]
    assert client.portal.call(scheduler.sweep_briefs) == 0
    with psycopg.connect(settings.database_url, autocommit=True) as conn:
        assert conn.execute("SELECT count(*) FROM lace_briefs WHERE posted_at IS NULL").fetchone()[0] == 1
        conn.execute("UPDATE runs SET status = 'completed' WHERE id = %s", (busy,))
    lace_runtime.append(AIMessage(content="Your brief."))
    assert client.portal.call(scheduler.sweep_briefs) == 1
    [brief_turn] = [r for r in client.portal.call(_runs, lace, "lace_turn") if (r.input or {}).get("brief_id")]
    client.portal.call(_wait_for_status, brief_turn.id, {"completed"})


def test_brief_settings(client, lace, lace_runtime):  # noqa: F811
    assert client.get(f"{API}/laces/{lace}/brief").json()["brief_frequency"] == "daily"
    updated = client.patch(f"{API}/laces/{lace}/brief", json={"brief_frequency": "weekly", "brief_hour": 7,
                                                              "timezone": "Africa/Nairobi"}).json()
    assert (updated["brief_frequency"], updated["brief_hour"], updated["timezone"]) == ("weekly", 7, "Africa/Nairobi")
    assert client.patch(f"{API}/laces/{lace}/brief", json={"timezone": "Mars/Olympus"}).status_code == 422
    assert client.patch(f"{API}/laces/{lace}/brief", json={"brief_hour": 24}).status_code == 422
    client.sign_in(make_user("Intruder"))
    assert client.get(f"{API}/laces/{lace}/brief").status_code == 404


def test_a_new_lace_starts_in_the_founders_timezone(client, lace_runtime):  # noqa: F811
    lace_runtime.append(AIMessage(content="Hello."))
    created = client.post(f"{API}/laces", json={"name": "Ada", "website": "acme.test", "timezone": "Africa/Nairobi"})
    lace_id = created.json()["lace"]["id"]
    assert client.get(f"{API}/laces/{lace_id}/brief").json()["timezone"] == "Africa/Nairobi"
    client.portal.call(_wait_for_status, created.json()["run_id"], {"completed"})
    assert client.post(f"{API}/laces", json={"name": "Bo", "website": "b.test", "timezone": "Nowhere"}).status_code == 422
