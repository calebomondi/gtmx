"""Cards and choices in the chat: what the Lace shows lands under its reply
and stays there, and a card's account can be searched for contacts."""

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
                            "subtitle": "https://rival.test", "body": "Payroll for vets.", "url": "https://rival.test"}]
    # Earlier messages carry no ui at all.
    assert "ui" not in client.get(f"{API}/laces/{lace}/messages").json()[0]


def test_a_choice_shows_even_without_words(client, lace, lace_runtime):  # noqa: F811
    lace_runtime.extend([_call("ask_choice", {"question": "Which market first?", "options": ["Kenya", "Nigeria"]}),
                         AIMessage(content="")])
    _say(client, lace, "let's find customers")
    client.portal.call(_wait_for_turns, lace, 1)
    reply = client.get(f"{API}/laces/{lace}/messages").json()[-1]
    assert reply == {"role": "lace", "content": "", "ui": [
        {"type": "choices", "question": "Which market first?", "options": ["Kenya", "Nigeria"]}]}


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
    assert job.input == {"account_ids": [account]}
    client.portal.call(_wait_for_turns, lace, 1)
    assert client.post(f"{API}/laces/{lace}/accounts/{uuid.uuid4()}/find-contacts").status_code == 404
    client.sign_in(make_user("Intruder"))
    assert client.post(url).status_code == 404
