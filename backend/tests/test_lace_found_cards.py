"""What a search found always reaches the founder as cards to save or
dismiss, and only the founder saves a suggestion."""

import uuid

import psycopg
from langchain_core.messages import AIMessage

from backend.app.runs import lace as lace_runs
from backend.app.runs import lace_jobs
from backend.tests.test_lace_jobs import RIVAL, _call, _runs, _wait_for_turns, lace  # noqa: F401 -- fixture
from backend.tests.test_laces_api import API, lace_runtime  # noqa: F401 -- fixture
from config import settings


def _hunt(client, lace_id, lace_runtime, monkeypatch, *report):  # noqa: F811
    monkeypatch.setattr(lace_jobs, "find_competitors", lambda profile, facts, focus: [RIVAL])
    lace_runtime.extend([_call("find_competitors"), AIMessage(content="On it."), *report])
    client.post(f"{API}/laces/{lace_id}/messages", json={"text": "who competes with us?"})
    client.portal.call(_wait_for_turns, lace_id, 2)
    return client.get(f"{API}/laces/{lace_id}/messages").json()[-1]


def _rival_id() -> str:
    with psycopg.connect(settings.database_url) as conn:
        return str(conn.execute("SELECT id FROM lace_competitors").fetchone()[0])


def test_new_finds_show_as_cards_when_the_reply_forgot_them(client, lace, lace_runtime, monkeypatch):  # noqa: F811
    reply = _hunt(client, lace, lace_runtime, monkeypatch, AIMessage(content="I found Rival."))
    # It passes on what a search found, so it says so; the Lace's answer to
    # the founder before it doesn't.
    assert reply["update"] is True
    assert "update" not in client.get(f"{API}/laces/{lace}/messages").json()[-2]
    [card] = reply["ui"]
    assert (card["type"], card["kind"], card["title"], card["status"]) == ("card", "competitor", "Rival", "suggested")
    [job] = client.portal.call(_runs, lace, "lace_competitors")
    with psycopg.connect(settings.database_url) as conn:
        assert conn.execute("SELECT run_id FROM lace_events").fetchall() == [(job.id,)]


def test_cards_the_reply_showed_are_not_added_twice(client, lace, lace_runtime, monkeypatch):  # noqa: F811
    _hunt(client, lace, lace_runtime, monkeypatch, AIMessage(content="I found Rival."))
    [job] = client.portal.call(_runs, lace, "lace_competitors")
    shown = {"type": "card", "kind": "competitor", "id": _rival_id(), "title": "Rival"}
    thread = lace_runs.LaceThread(uuid.UUID(lace))
    assert client.portal.call(lace_runs._with_found_cards, thread, [job.id], [shown]) == [shown]
    # Another chat's searches, or none, add nothing.
    assert client.portal.call(lace_runs._with_found_cards, thread, [], []) == []
    private = lace_runs.LaceThread(uuid.UUID(lace), uuid.uuid4())
    assert client.portal.call(lace_runs._with_found_cards, private, [job.id], []) == []


def test_the_lace_cannot_save_a_suggestion(client, lace, lace_runtime, monkeypatch):  # noqa: F811
    _hunt(client, lace, lace_runtime, monkeypatch, AIMessage(content="I found Rival."))
    lace_runtime.extend([_call("update_saved", {"kind": "competitor", "ids": [_rival_id()], "verdict": "save"}),
                         AIMessage(content="It's yours to save.")])
    client.post(f"{API}/laces/{lace}/messages", json={"text": "save rival"})
    client.portal.call(_wait_for_turns, lace, 3)
    with psycopg.connect(settings.database_url) as conn:
        assert conn.execute("SELECT status FROM lace_competitors").fetchall() == [("suggested",)]
    [card] = client.get(f"{API}/laces/{lace}/messages").json()[-1]["ui"]
    assert (card["kind"], card["title"], card["status"]) == ("competitor", "Rival", "suggested")


def test_the_lace_can_still_bring_back_a_removed_one(client, lace, lace_runtime, monkeypatch):  # noqa: F811
    _hunt(client, lace, lace_runtime, monkeypatch, AIMessage(content="I found Rival."))
    rival = _rival_id()
    assert client.patch(f"{API}/laces/{lace}/competitors/{rival}", json={"status": "dismissed"}).status_code == 200
    lace_runtime.extend([_call("update_saved", {"kind": "competitor", "ids": [rival], "verdict": "save"}),
                         AIMessage(content="Rival is back.")])
    client.post(f"{API}/laces/{lace}/messages", json={"text": "bring rival back"})
    client.portal.call(_wait_for_turns, lace, 3)
    with psycopg.connect(settings.database_url) as conn:
        assert conn.execute("SELECT status FROM lace_competitors").fetchall() == [("tracked",)]
