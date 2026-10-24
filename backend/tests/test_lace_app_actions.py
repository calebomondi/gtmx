"""Actions a Lace proposes in its founder's apps: kept until the founder
approves (then run as them, recorded, put on the Feed and told to the Lace)
or declines; never run twice, never run without the app connected, and only
for the Lace's owner."""

import uuid
from datetime import UTC, datetime

import psycopg
import pytest

from agents.lace.app_actions import propose
from agents.schemas.lace import ProposedAction
from backend.app.database.connect import AsyncSessionLocal
from backend.app.services import lace_app_actions, lace_cards
from backend.app.services import connections as connection_service
from backend.app.services.connections import ConnectionInfo
from backend.app.services.lace_app_actions import ActionFailed, Outcome
from backend.app.services.lace_store import DbLaceStore
from backend.tests.helpers import make_user
from backend.tests.test_lace_jobs import lace  # noqa: F401 -- fixture
from backend.tests.test_laces_api import API, lace_runtime  # noqa: F401 -- fixture
from config import settings

POST = ProposedAction(app="linkedin", action="publish_post", title="Post on LinkedIn",
                      preview="We opened in Nakuru.", arguments={"text": "We opened in Nakuru."})


@pytest.fixture
def linkedin(monkeypatch):
    """A live LinkedIn connection, and a runner that records what it ran."""
    box = {"live": {"linkedin"}, "ran": [], "fail": None}

    async def list_for_user(db, user_id):
        now = datetime.now(UTC)
        return [ConnectionInfo(f"ca_{p}", p, "live", None, now, now) for p in box["live"]]
    monkeypatch.setattr(connection_service, "list_for_user", list_for_user)

    def publish(user_id, connection_id, arguments):
        box["ran"].append((connection_id, arguments))
        if box["fail"]:
            raise box["fail"]
        return Outcome("Posted on LinkedIn.", url="https://linkedin.com/feed/update/1", log_id="log_1")
    monkeypatch.setitem(lace_app_actions.RUNNERS, ("linkedin", "publish_post"), publish)
    return box


def _propose(client, lace_id, proposal=POST) -> dict:
    """What the Lace's tool returns: the proposal kept, with its card. Run on
    the app's own loop, as everything touching its database pool is."""
    result = client.portal.call(propose, DbLaceStore(AsyncSessionLocal, uuid.UUID(lace_id)), proposal)
    [card] = result.data["ui"]
    return card


def test_an_approved_action_runs_once_as_the_founder_and_is_reported(client, lace, lace_runtime, linkedin):  # noqa: F811
    card = _propose(client, lace)
    assert (card["type"], card["status"], card["title"]) == ("action", "proposed", "Post on LinkedIn")
    [waiting] = client.get(f"{API}/laces/{lace}/app-actions?status=proposed").json()
    assert waiting["id"] == card["id"] and waiting["preview"] == "We opened in Nakuru."

    done = client.post(f"{API}/laces/{lace}/app-actions/{card['id']}/approve").json()
    assert (done["status"], done["result"], done["url"]) == ("done", "Posted on LinkedIn.", "https://linkedin.com/feed/update/1")
    assert linkedin["ran"] == [("ca_linkedin", {"text": "We opened in Nakuru."})]
    assert client.post(f"{API}/laces/{lace}/app-actions/{card['id']}/approve").status_code == 409  # once
    with psycopg.connect(settings.database_url) as conn:
        assert conn.execute("SELECT kind, title, ref_type FROM lace_activity WHERE kind = 'app_action'").fetchone() == (
            "app_action", "Post on LinkedIn: done", "app_action")
        assert conn.execute("SELECT provider_log_id FROM lace_app_actions").fetchone()[0] == "log_1"


def test_declined_actions_never_run(client, lace, lace_runtime, linkedin):  # noqa: F811
    card = _propose(client, lace)
    assert client.post(f"{API}/laces/{lace}/app-actions/{card['id']}/decline").json()["status"] == "declined"
    assert client.post(f"{API}/laces/{lace}/app-actions/{card['id']}/approve").status_code == 409
    assert linkedin["ran"] == []
    with psycopg.connect(settings.database_url) as conn:
        assert "declined \"Post on LinkedIn\"" in conn.execute("SELECT text FROM lace_events").fetchone()[0]


def test_an_unconnected_app_keeps_it_waiting(client, lace, lace_runtime, linkedin):  # noqa: F811
    linkedin["live"] = set()
    card = _propose(client, lace)
    refused = client.post(f"{API}/laces/{lace}/app-actions/{card['id']}/approve")
    assert refused.status_code == 409 and "Connect your LinkedIn" in refused.json()["detail"]
    assert client.get(f"{API}/laces/{lace}/app-actions").json()[0]["status"] == "proposed"


@pytest.mark.parametrize("error, said", [
    (ActionFailed("LinkedIn refused the post: duplicate content."), "LinkedIn refused the post: duplicate content."),
    (ConnectionError("reset"), "Couldn't reach LinkedIn. Please try again."),
])
def test_a_failed_run_is_recorded_with_why(client, lace, lace_runtime, linkedin, error, said):  # noqa: F811
    linkedin["fail"] = error
    card = _propose(client, lace)
    failed = client.post(f"{API}/laces/{lace}/app-actions/{card['id']}/approve").json()
    assert (failed["status"], failed["result"]) == ("failed", said)


def test_only_the_owner_sees_or_decides(client, lace, lace_runtime, linkedin):  # noqa: F811
    card = _propose(client, lace)
    client.sign_in(make_user("Intruder"))
    assert client.get(f"{API}/laces/{lace}/app-actions").status_code == 404
    assert client.post(f"{API}/laces/{lace}/app-actions/{card['id']}/approve").status_code == 404
    assert linkedin["ran"] == []


def test_cards_show_where_the_action_stands_now(client, lace, lace_runtime, linkedin):  # noqa: F811
    card = _propose(client, lace)
    client.post(f"{API}/laces/{lace}/app-actions/{card['id']}/approve")

    async def read():
        async with AsyncSessionLocal() as db:
            return await lace_cards.with_status(db, uuid.UUID(lace), [{"role": "lace", "content": "", "ui": [dict(card)]}])
    [message] = client.portal.call(read)
    assert {k: message["ui"][0][k] for k in ("status", "result", "url")} == {
        "status": "done", "result": "Posted on LinkedIn.", "url": "https://linkedin.com/feed/update/1"}
