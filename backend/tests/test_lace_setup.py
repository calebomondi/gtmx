"""Creating a Lace as the founder sees it: onboarding's progress frames, then
reviewing what it learned (confirm, retract, correct)."""

import uuid

from backend.tests.helpers import make_user
from backend.tests.test_lace_jobs import lace  # noqa: F401 -- fixture
from backend.tests.test_laces_api import API, _create, _events, lace_runtime  # noqa: F401 -- fixture
from backend.tests.test_runs import _wait_for_status


def test_onboarding_reports_progress_in_order(client, lace_runtime):  # noqa: F811
    body = _create(client).json()
    client.portal.call(_wait_for_status, uuid.UUID(body["run_id"]), {"completed"})
    progress = [f for f in _events(client, body["run_id"]) if f["type"] == "progress"]
    assert [(f["fraction"], f["text"]) for f in progress] == [(0.5, "Read 1 of 1 pages"), (0.95, "Writing to you")]
    assert all(f["event_id"] for f in progress)  # stored: a reconnecting page catches up


def _facts(client, lace_id):
    return client.get(f"{API}/laces/{lace_id}/facts").json()


def test_confirm_and_retract(client, lace):  # noqa: F811
    [fact] = _facts(client, lace)
    confirmed = client.patch(f"{API}/laces/{lace}/facts/{fact['id']}", json={"verdict": "confirmed"}).json()
    assert confirmed["confirmed_at"] is not None
    assert client.patch(f"{API}/laces/{lace}/facts/{fact['id']}", json={"verdict": "retracted"}).status_code == 200
    assert _facts(client, lace) == []  # out of what the Lace knows
    assert client.patch(f"{API}/laces/{lace}/facts/{fact['id']}", json={"verdict": "confirmed"}).status_code == 404


def test_correction_supersedes_the_fact(client, lace):  # noqa: F811
    [fact] = _facts(client, lace)
    url = f"{API}/laces/{lace}/facts/{fact['id']}/correction"
    assert client.post(url, json={"claim": "   "}).status_code == 422
    corrected = client.post(url, json={"claim": "Acme sells payroll to vet clinics."})
    assert corrected.status_code == 201
    new = corrected.json()
    assert (new["origin"], new["topic"], new["source_url"]) == ("user", fact["topic"], None)
    assert [f["claim"] for f in _facts(client, lace)] == ["Acme sells payroll to vet clinics."]
    assert client.post(url, json={"claim": "Again"}).status_code == 404  # already superseded


def test_other_users_facts_are_not_found(client, lace):  # noqa: F811
    [fact] = _facts(client, lace)
    client.sign_in(make_user("Intruder"))
    assert client.patch(f"{API}/laces/{lace}/facts/{fact['id']}", json={"verdict": "retracted"}).status_code == 404
    assert client.post(f"{API}/laces/{lace}/facts/{fact['id']}/correction", json={"claim": "x"}).status_code == 404
