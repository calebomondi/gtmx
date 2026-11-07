"""A Lace's standing instructions: kept from the chat or added in settings,
editable and removable by the team, and followed by the jobs they apply to."""

import uuid

from langchain_core.messages import AIMessage

from backend.app.runs import lace_jobs, manager
from backend.tests.helpers import make_user
from backend.tests.test_lace_jobs import RIVAL, _call, _wait_for_turns, lace  # noqa: F401 -- fixture
from backend.tests.test_laces_api import API, lace_runtime  # noqa: F401 -- fixture
from backend.tests.test_runs import _wait_for_status
from config import settings


def test_the_team_adds_edits_and_removes_them(client, lace, user):  # noqa: F811
    url = f"{API}/laces/{lace}/instructions"
    made = client.post(url, json={"text": "  Only competitors   in Kenya ", "applies_to": "competitors"})
    assert made.status_code == 201
    kept = made.json()
    assert (kept["text"], kept["applies_to"], kept["created_by"]) == ("Only competitors in Kenya", "competitors",
                                                                      str(user.id))
    client.post(url, json={"text": "We only sell to businesses"})
    assert [(i["text"], i["applies_to"]) for i in client.get(url).json()] == [
        ("Only competitors in Kenya", "competitors"), ("We only sell to businesses", "everything")]

    edited = client.patch(f"{url}/{kept['id']}", json={"text": "Only competitors in East Africa"}).json()
    assert edited["text"] == "Only competitors in East Africa" and edited["updated_at"]
    assert client.delete(f"{url}/{kept['id']}").status_code == 204
    assert [i["text"] for i in client.get(url).json()] == ["We only sell to businesses"]
    assert client.delete(f"{url}/{kept['id']}").status_code == 404


def test_a_bad_or_one_too_many_instruction_is_refused(client, lace, monkeypatch):  # noqa: F811
    url = f"{API}/laces/{lace}/instructions"
    assert client.post(url, json={"text": ""}).status_code == 422
    assert client.post(url, json={"text": "x" * 301}).status_code == 422
    assert client.post(url, json={"text": "Fine", "applies_to": "pricing"}).status_code == 422
    assert client.post(url, json={"text": "   "}).status_code == 422  # only spaces
    monkeypatch.setattr(settings, "max_instructions_per_lace", 1)
    assert client.post(url, json={"text": "One"}).status_code == 201
    full = client.post(url, json={"text": "Two"})
    assert full.status_code == 409 and "up to 1 standing instructions" in full.json()["detail"]


def test_another_users_instructions_stay_theirs(client, lace):  # noqa: F811
    kept = client.post(f"{API}/laces/{lace}/instructions", json={"text": "Shorter emails"}).json()
    client.sign_in(make_user("Intruder"))
    assert client.get(f"{API}/laces/{lace}/instructions").status_code == 404
    assert client.patch(f"{API}/laces/{lace}/instructions/{kept['id']}", json={"text": "x"}).status_code == 404
    assert client.delete(f"{API}/laces/{lace}/instructions/{kept['id']}").status_code == 404


def test_the_lace_keeps_one_the_founder_gives_in_the_chat(client, lace, lace_runtime, user):  # noqa: F811
    lace_runtime.extend([_call("remember_instruction", {"instruction": "Skip events outside Africa",
                                                        "applies_to": "opportunities"}),
                         AIMessage(content="Got it: I'll skip events outside Africa from now on.")])
    client.post(f"{API}/laces/{lace}/messages", json={"text": "don't show me events outside Africa"})
    client.portal.call(_wait_for_turns, lace, 1)
    [kept] = client.get(f"{API}/laces/{lace}/instructions").json()
    assert (kept["text"], kept["applies_to"], kept["created_by"]) == ("Skip events outside Africa", "opportunities",
                                                                      str(user.id))


def test_a_competitor_search_follows_them(client, lace, lace_runtime, user, monkeypatch):  # noqa: F811
    url = f"{API}/laces/{lace}/instructions"
    client.post(url, json={"text": "Only competitors selling in Kenya", "applies_to": "competitors"})
    client.post(url, json={"text": "Keep emails short", "applies_to": "outreach"})
    seen = {}

    def hunt(profile, facts, focus, limit=None):
        seen["focus"] = focus
        return [RIVAL]
    monkeypatch.setattr(lace_jobs, "find_competitors", hunt)
    lace_runtime.append(AIMessage(content="I found Rival."))
    run = client.portal.call(manager.start_lace_job, "lace_competitors", user.id, uuid.UUID(lace),
                             {"focus": "AI-first tools"})
    client.portal.call(_wait_for_status, run.id, {"completed"})
    assert seen["focus"] == ("AI-first tools\n\nThe team's standing instructions (always follow them):\n"
                             "- Only competitors selling in Kenya")


def test_an_opportunity_search_follows_only_its_own(client, lace, lace_runtime, user, monkeypatch):  # noqa: F811
    from backend.tests.test_lace_opportunities import _stub
    url = f"{API}/laces/{lace}/instructions"
    client.post(url, json={"text": "No events outside Africa", "applies_to": "opportunities"})
    client.post(url, json={"text": "We only sell to businesses"})
    client.post(url, json={"text": "Only competitors in Kenya", "applies_to": "competitors"})
    seen = _stub(monkeypatch, [])
    lace_runtime.append(AIMessage(content="Nothing current fits."))
    run = client.portal.call(manager.start_lace_job, "lace_opportunities", user.id, uuid.UUID(lace), {})
    client.portal.call(_wait_for_status, run.id, {"completed"})
    client.portal.call(_wait_for_turns, lace, 1)
    assert seen["instructions"] == "- No events outside Africa\n- We only sell to businesses"


def test_what_was_asked_comes_before_the_standing_instructions():
    assert lace_jobs.with_instructions(None, "") is None
    assert lace_jobs.with_instructions("  local players ", "") == "local players"
    assert lace_jobs.with_instructions(None, "- Shorter emails") == (
        "The team's standing instructions (always follow them):\n- Shorter emails")
