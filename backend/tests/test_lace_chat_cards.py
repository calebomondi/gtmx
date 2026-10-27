"""Cards and questions in the chat: what the Lace shows lands under its reply
and stays there, cards say where their item stands now, questions are
answered with a click and stay answered, and a card's account can be searched
for contacts."""

import uuid

import psycopg
from langchain_core.messages import AIMessage

from backend.app.runs import lace_jobs
from backend.tests.helpers import make_user
from backend.tests.test_lace_contacts import _account
from backend.tests.test_lace_jobs import _call, _runs, _wait_for_turns, lace  # noqa: F401 -- fixture
from backend.tests.test_laces_api import API, lace_runtime  # noqa: F401 -- fixture
from config import settings


def _rival(lace_id) -> str:
    rival = uuid.uuid4()
    with psycopg.connect(settings.database_url, autocommit=True) as conn:
        conn.execute("INSERT INTO lace_competitors (id, lace_id, name, website, domain_key, summary) VALUES"
                     " (%s, %s, 'Rival', 'https://rival.test', 'rival.test', 'Payroll for vets.')", (rival, lace_id))
    return str(rival)


def _say(client, lace_id, text):
    client.post(f"{API}/laces/{lace_id}/messages", json={"text": text})


def test_shown_cards_stay_under_the_reply(client, lace, lace_runtime):  # noqa: F811
    rival = _rival(lace)
    lace_runtime.extend([_call("show", {"kind": "competitor", "ids": [rival]}),
                         AIMessage(content="Rival is the one to watch.")])
    _say(client, lace, "who should I watch?")
    client.portal.call(_wait_for_turns, lace, 1)

    reply = client.get(f"{API}/laces/{lace}/messages").json()[-1]
    assert reply["content"] == "Rival is the one to watch."
    assert reply["ui"] == [{"type": "card", "kind": "competitor", "id": rival, "title": "Rival",
                            "subtitle": "https://rival.test", "body": "Payroll for vets.", "url": "https://rival.test",
                            "status": "tracked"}]
    # Earlier messages carry no ui at all.
    assert "ui" not in client.get(f"{API}/laces/{lace}/messages").json()[0]


def test_a_choice_shows_even_without_words(client, lace, lace_runtime):  # noqa: F811
    lace_runtime.extend([_call("ask_choice", {"question": "Which market first?", "options": ["Kenya", "Nigeria"]}),
                         AIMessage(content="")])
    _say(client, lace, "let's find customers")
    client.portal.call(_wait_for_turns, lace, 1)
    reply = client.get(f"{API}/laces/{lace}/messages").json()[-1]
    [block] = reply["ui"]
    assert reply["content"] == "" and block["id"]
    assert {k: block[k] for k in ("type", "question", "options")} == {
        "type": "choices", "question": "Which market first?", "options": ["Kenya", "Nigeria"]}


def test_a_choice_is_not_repeated_in_the_text(client, lace, lace_runtime):  # noqa: F811
    lace_runtime.extend([_call("ask_choice", {"question": "Which market first?", "options": ["Kenya", "Nigeria"]}),
                         AIMessage(content="Both markets have buyers.\n\nWould you like me to:\n\n1. Start with Kenya?"
                                           "\n2. Start with Nigeria?\n\nWhich works best?")])
    _say(client, lace, "where should we start?")
    client.portal.call(_wait_for_turns, lace, 1)
    reply = client.get(f"{API}/laces/{lace}/messages").json()[-1]
    assert reply["content"] == "Both markets have buyers."
    assert reply["ui"][0]["type"] == "choices"


def test_a_card_says_where_its_item_stands_now(client, lace, lace_runtime):  # noqa: F811
    rival = _rival(lace)
    lace_runtime.extend([_call("show", {"kind": "competitor", "ids": [rival]}), AIMessage(content="Here.")])
    _say(client, lace, "who should I watch?")
    client.portal.call(_wait_for_turns, lace, 1)
    assert client.patch(f"{API}/laces/{lace}/competitors/{rival}", json={"status": "dismissed"}).status_code == 200
    [card] = client.get(f"{API}/laces/{lace}/messages").json()[-1]["ui"]
    assert card["status"] == "dismissed"
    with psycopg.connect(settings.database_url, autocommit=True) as conn:
        conn.execute("DELETE FROM lace_competitors WHERE id = %s", (rival,))
    [card] = client.get(f"{API}/laces/{lace}/messages").json()[-1]["ui"]
    assert card["status"] == "gone"


def _asked(client, lace, lace_runtime, tool, args) -> dict:  # noqa: F811
    lace_runtime.extend([_call(tool, args), AIMessage(content="Over to you.")])
    _say(client, lace, "go on")
    client.portal.call(_wait_for_turns, lace, 1)
    [block] = client.get(f"{API}/laces/{lace}/messages").json()[-1]["ui"]
    return block


def _answer(client, lace, answer):  # noqa: F811
    return client.post(f"{API}/laces/{lace}/messages", json={"answer": answer})


def test_a_checklist_is_answered_once_and_stays_answered(client, lace, lace_runtime):  # noqa: F811
    block = _asked(client, lace, lace_runtime, "ask_checklist", {
        "question": "Remove these opportunities?", "submit": "Remove ticked",
        "items": [{"id": "o1", "label": "Logistics expo"}, {"id": "o2", "label": "County tender"}]})
    assert block["type"] == "checklist" and [i["checked"] for i in block["items"]] == [True, True]

    assert _answer(client, lace, {"block_id": block["id"], "chosen": ["o9"]}).status_code == 422
    lace_runtime.append(AIMessage(content="Removed the expo."))
    assert _answer(client, lace, {"block_id": block["id"], "chosen": ["o1"]}).status_code == 202
    client.portal.call(_wait_for_turns, lace, 2)

    *_, asked, answered, reply = client.get(f"{API}/laces/{lace}/messages").json()
    assert asked["ui"][0]["id"] == block["id"]
    answered.pop("author")  # who sent it: covered in test_lace_members
    assert answered == {"role": "founder", "content": "Remove ticked: Logistics expo",
                        "answer": {"block_id": block["id"], "chosen": ["o1"], "values": {}}}
    assert reply["content"] == "Removed the expo."
    again = _answer(client, lace, {"block_id": block["id"], "chosen": ["o2"]})
    assert again.status_code == 409


def test_a_form_needs_its_required_fields(client, lace, lace_runtime):  # noqa: F811
    block = _asked(client, lace, lace_runtime, "ask_form", {
        "question": "Who should I add?", "submit": "Add them",
        "fields": [{"name": "name", "label": "Name"}, {"name": "email", "label": "Email", "kind": "email"},
                   {"name": "note", "label": "Note", "required": False}]})
    missing = _answer(client, lace, {"block_id": block["id"], "values": {"name": "Kaleb"}})
    assert missing.status_code == 422 and "Email" in missing.json()["detail"]
    lace_runtime.append(AIMessage(content="Added."))
    sent = _answer(client, lace, {"block_id": block["id"], "values": {"name": "Kaleb", "email": "k@thalace.test"}})
    assert sent.status_code == 202
    client.portal.call(_wait_for_turns, lace, 2)
    answered = client.get(f"{API}/laces/{lace}/messages").json()[-2]
    assert answered["content"] == "Name: Kaleb · Email: k@thalace.test"


def test_an_answer_comes_on_its_own(client, lace):  # noqa: F811
    bad = client.post(f"{API}/laces/{lace}/messages", json={"text": "hi", "answer": {"block_id": "x"}})
    assert bad.status_code == 422
    assert _answer(client, lace, {"block_id": "nope", "chosen": ["Kenya"]}).status_code == 409


def test_a_failed_show_adds_nothing(client, lace, lace_runtime):  # noqa: F811
    lace_runtime.extend([_call("show", {"kind": "account", "ids": ["made-up"]}), AIMessage(content="None yet.")])
    _say(client, lace, "show my accounts")
    client.portal.call(_wait_for_turns, lace, 1)
    assert "ui" not in client.get(f"{API}/laces/{lace}/messages").json()[-1]


def test_find_contacts_from_a_card(client, lace, lace_runtime, user, monkeypatch):  # noqa: F811
    monkeypatch.setattr(lace_jobs, "complete_contacts", lambda record, titles, cfg: record)
    account = str(_account(lace, "SunCulture"))
    with psycopg.connect(settings.database_url, autocommit=True) as conn:
        conn.execute("INSERT INTO runs (id, user_id, lace_id, kind, status) VALUES (%s, %s, %s, 'lace_contacts',"
                     " 'running')", (uuid.uuid4(), user.id, lace))
    url = f"{API}/laces/{lace}/accounts/{account}/find-contacts"
    busy = client.post(url)
    assert busy.status_code == 409 and "already running" in busy.json()["detail"]
    with psycopg.connect(settings.database_url, autocommit=True) as conn:
        conn.execute("UPDATE runs SET status = 'completed' WHERE lace_id = %s", (lace,))
    lace_runtime.append(AIMessage(content="Nobody found yet."))
    started = client.post(url)
    assert started.status_code == 202
    [job] = [r for r in client.portal.call(_runs, lace, "lace_contacts") if str(r.id) == started.json()["run_id"]]
    assert job.input == {"account_ids": [account], "actor_id": str(user.id)}
    client.portal.call(_wait_for_turns, lace, 1)
    assert client.post(f"{API}/laces/{lace}/accounts/{uuid.uuid4()}/find-contacts").status_code == 404
    client.sign_in(make_user("Intruder"))
    assert client.post(url).status_code == 404


def test_suggested_replies_stay_under_the_reply(client, lace, lace_runtime):  # noqa: F811
    lace_runtime.extend([_call("suggest_replies", {"options": ["Check their LinkedIn", "Find their OTA guide"]}),
                         AIMessage(content="Want me to dig deeper into one of them?")])
    _say(client, lace, "who are Hamtech?")
    client.portal.call(_wait_for_turns, lace, 1)
    reply = client.get(f"{API}/laces/{lace}/messages").json()[-1]
    assert reply["ui"] == [{"type": "suggestions", "options": ["Check their LinkedIn", "Find their OTA guide"]}]
