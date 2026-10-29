"""A Lace's target accounts: searched in the background on its ICP, saved
with their cases, reported back, and listed strongest first."""

import uuid

import psycopg
from langchain_core.messages import AIMessage

from agents.schemas.accounts import AccountFit, AccountRecord, TriggerEvent
from agents.schemas.icp import ICP
from backend.app.runs import lace_jobs
from backend.app.runs import manager
from backend.tests.helpers import make_user
from backend.tests.test_lace_jobs import _call, _runs, _wait_for_turns, lace  # noqa: F401 -- fixture
from backend.tests.test_laces_api import API, lace_runtime  # noqa: F401 -- fixture
from backend.tests.test_runs import _wait_for_status
from config import settings


def _found(name: str, strength: str | None) -> tuple[AccountRecord, AccountFit | None]:
    record = AccountRecord(name=name, website=f"https://www.{name.lower()}.test/", geo="Kenya", score=0.5,
                           summary=f"{name} runs clinics.",
                           trigger_event=TriggerEvent(event=f"{name} raised a round", signal_type="funding_round",
                                                      source="https://news.test"))
    fit = AccountFit(need="Payroll", capability="Payroll", payoff="On time", angle="Hi", strength=strength) if strength else None
    return record, fit


def _with_icp(lace_id):
    with psycopg.connect(settings.database_url, autocommit=True) as conn:
        conn.execute("UPDATE laces SET icp = '{\"buyer_type\": \"b2b\", \"industries\": [\"Clinics\"]}' WHERE id = %s",
                     (lace_id,))
        conn.execute("INSERT INTO lace_competitors (id, lace_id, name, website, domain_key, status)"
                     " VALUES (%s, %s, 'Rival', 'https://rival.test', 'rival.test', 'dismissed')", (uuid.uuid4(), lace_id))


def test_search_saves_accounts_and_the_lace_reports_back(client, lace, lace_runtime, monkeypatch):  # noqa: F811
    _with_icp(lace)
    seen = {}

    def fake(profile, facts, icp, exclude, country):
        seen.update(exclude=exclude, country=country, industries=icp.industries)
        return [_found("Weak", "weak"), _found("Strong", "strong"), _found("Unmade", None)]

    monkeypatch.setattr(lace_jobs, "find_accounts", fake)
    lace_runtime.extend([_call("find_accounts", {"country": "Kenya"}), AIMessage(content="On it."),
                         AIMessage(content="Strong raised a round and needs payroll.")])
    client.post(f"{API}/laces/{lace}/messages", json={"text": "find me customers in Kenya"})
    turns = client.portal.call(_wait_for_turns, lace, 2)

    assert seen == {"exclude": ["acme.test", "rival.test"], "country": "Kenya", "industries": ["Clinics"]}
    update = turns[-1].input["updates"][0]
    assert "in Kenya finished: 2 leads (2 new, 0 already on file)" in update and "Strong raised a round" in update
    # A weak fit is left out, named for the Lace only, never put forward.
    assert "1 weaker match left out: Weak. Don't put these forward." in update
    # Found accounts wait for the founder: none is a target until saved.
    assert client.get(f"{API}/laces/{lace}/accounts").json() == []
    accounts = client.get(f"{API}/laces/{lace}/accounts?status=suggested").json()
    assert [a["name"] for a in accounts] == ["Strong", "Unmade"]  # strongest case first
    top = accounts[0]
    assert top["trigger"]["event"] == "Strong raised a round" and top["case"]["strength"] == "strong"
    assert accounts[1]["case"] is None
    assert client.get(f"{API}/laces/{lace}/messages").json()[-1]["content"] == "Strong raised a round and needs payroll."
    saved = client.patch(f"{API}/laces/{lace}/accounts/{top['id']}", json={"status": "target"}).json()
    assert saved["status"] == "target"
    assert [a["name"] for a in client.get(f"{API}/laces/{lace}/accounts").json()] == ["Strong"]
    assert client.patch(f"{API}/laces/{lace}/accounts/{top['id']}", json={"status": "suggested"}).status_code == 422


def test_no_icp_means_the_search_works_one_out_first(client, lace, lace_runtime, user, monkeypatch):  # noqa: F811
    seen = {}
    monkeypatch.setattr(lace_jobs.lace_icp, "define_icp",
                        lambda profile, facts, rivals, guidance: ICP(buyer_type="b2b", industries=["Clinics"]))

    def fake(profile, facts, icp, exclude, country):
        seen["industries"] = icp.industries
        return [_found("Alpha", "strong")]
    monkeypatch.setattr(lace_jobs, "find_accounts", fake)
    lace_runtime.append(AIMessage(content="I found Alpha."))  # the wake follows at once
    run = client.portal.call(manager.start_lace_job, "lace_accounts", user.id, uuid.UUID(lace), {})
    client.portal.call(_wait_for_status, run.id, {"completed"})
    assert seen["industries"] == ["Clinics"]
    with psycopg.connect(settings.database_url) as conn:
        assert conn.execute("SELECT icp->'industries' FROM laces WHERE id = %s", (lace,)).fetchone()[0] == ["Clinics"]


def test_the_icp_job_saves_it_and_tells_the_lace(client, lace, lace_runtime, user, monkeypatch):  # noqa: F811
    monkeypatch.setattr(lace_jobs.lace_icp, "define_icp",
                        lambda profile, facts, rivals, guidance: ICP(buyer_type="b2b", industries=[guidance]))
    lace_runtime.append(AIMessage(content="I worked out who to sell to: clinics."))
    run = client.portal.call(manager.start_lace_job, "lace_icp", user.id, uuid.UUID(lace), {"guidance": "Clinics"})
    client.portal.call(_wait_for_status, run.id, {"completed"})
    turns = client.portal.call(_wait_for_turns, lace, 1)
    assert "ideal customer profile is saved" in turns[-1].input["updates"][0]
    assert "Industries: Clinics" in turns[-1].input["updates"][0]


def test_a_dismissed_account_stays_dismissed(client, lace, lace_runtime, user, monkeypatch):  # noqa: F811
    _with_icp(lace)
    monkeypatch.setattr(lace_jobs, "find_accounts", lambda *a: [_found("Alpha", "strong")])
    lace_runtime.extend([AIMessage(content="Found Alpha."), AIMessage(content="Found Alpha again.")])

    run = client.portal.call(manager.start_lace_job, "lace_accounts", user.id, uuid.UUID(lace), {})
    client.portal.call(_wait_for_status, run.id, {"completed"})
    client.portal.call(_wait_for_turns, lace, 1)
    [alpha] = client.get(f"{API}/laces/{lace}/accounts?status=suggested").json()
    assert client.patch(f"{API}/laces/{lace}/accounts/{alpha['id']}", json={"status": "dismissed"}).status_code == 200

    run = client.portal.call(manager.start_lace_job, "lace_accounts", user.id, uuid.UUID(lace), {})
    client.portal.call(_wait_for_status, run.id, {"completed"})
    client.portal.call(_wait_for_turns, lace, 2)
    assert client.get(f"{API}/laces/{lace}/accounts").json() == []
    assert client.portal.call(_runs, lace, "lace_accounts")[-1].progress["refreshed"] == 1
    assert [a["name"] for a in client.get(f"{API}/laces/{lace}/accounts?status=dismissed").json()] == ["Alpha"]


def test_accounts_are_private(client, lace, lace_runtime):  # noqa: F811
    with psycopg.connect(settings.database_url, autocommit=True) as conn:
        account = conn.execute("INSERT INTO lace_accounts (id, lace_id, key, name, account_type, record)"
                               " VALUES (%s, %s, 'alpha.test', 'Alpha', 'company', '{}') RETURNING id",
                               (uuid.uuid4(), lace)).fetchone()[0]
    client.sign_in(make_user("Intruder"))
    assert client.get(f"{API}/laces/{lace}/accounts").status_code == 404
    assert client.patch(f"{API}/laces/{lace}/accounts/{account}", json={"status": "dismissed"}).status_code == 404


def test_when_nothing_fits_the_lace_is_told_to_say_so(client, lace, lace_runtime, monkeypatch):  # noqa: F811
    _with_icp(lace)
    monkeypatch.setattr(lace_jobs, "find_accounts", lambda *a: [_found("Tea Estate", "weak"), _found("Retailer", "weak")])
    lace_runtime.extend([_call("find_accounts"), AIMessage(content="On it."), AIMessage(content="Nothing fits yet.")])
    client.post(f"{API}/laces/{lace}/messages", json={"text": "find me customers"})
    turns = client.portal.call(_wait_for_turns, lace, 2)
    update = turns[-1].input["updates"][0]
    assert "checked 2 companies, but none fits what we sell" in update and "Tell the founder plainly" in update
    assert "Tea Estate" not in update
    assert client.get(f"{API}/laces/{lace}/accounts?status=suggested").json() == []
