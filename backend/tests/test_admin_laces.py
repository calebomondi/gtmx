"""Admin views of Laces: every user's Laces with their counts and cost, a
Lace's detail with its runs, and runs filtered by Lace -- admin only."""

import uuid

import psycopg
import pytest

from backend.tests.helpers import make_user
from backend.tests.test_admin_entities import API, directory  # noqa: F401 -- fixture
from config import settings


def _lace(conn, user_id, name, website) -> uuid.UUID:
    lace_id = uuid.uuid4()
    conn.execute("INSERT INTO laces (id, user_id, name, website, startup_name, status) VALUES"
                 " (%s, %s, %s, %s, %s, 'active')", (lace_id, user_id, name, website, f"{name} Inc"))
    return lace_id


def _run(conn, user_id, lace_id, kind, model, tokens) -> uuid.UUID:
    run_id = conn.execute("INSERT INTO runs (id, user_id, lace_id, kind, status) VALUES (%s, %s, %s, %s, 'completed')"
                          " RETURNING id", (uuid.uuid4(), user_id, lace_id, kind)).fetchone()[0]
    conn.execute("INSERT INTO llm_calls (run_id, log_label, provider, model, input_tokens, output_tokens, seconds, ok)"
                 " VALUES (%s, 'lace:step', 'qwen', %s, %s, %s, 1, true)", (run_id, model, tokens, tokens))
    return run_id


@pytest.fixture
def laces(user, directory, monkeypatch):  # noqa: F811
    monkeypatch.setattr(settings, "llm_prices", {"priced-model": [1.0, 1.0]})
    with psycopg.connect(settings.database_url, autocommit=True) as conn:
        ada = _lace(conn, user.id, "Ada", "https://shangalabs.test")
        bo = _lace(conn, user.id, "Bo", "https://bo.test")
        conn.execute("INSERT INTO lace_facts (id, lace_id, topic, claim, source_url, confidence, origin) VALUES"
                     " (%s, %s, 'offer', 'Fleet tracking.', 'https://shangalabs.test', 'high', 'crawl')", (uuid.uuid4(), ada))
        for status in ("tracked", "suggested"):
            conn.execute("INSERT INTO lace_competitors (id, lace_id, name, website, domain_key, status) VALUES"
                         " (%s, %s, %s, 'https://r.test', %s, %s)", (uuid.uuid4(), ada, f"R {status}", f"{status}.test", status))
        account = conn.execute("INSERT INTO lace_accounts (id, lace_id, key, name, account_type, record) VALUES"
                               " (%s, %s, 'sun.test', 'SunCulture', 'company', '{}') RETURNING id",
                               (uuid.uuid4(), ada)).fetchone()[0]
        conn.execute("INSERT INTO lace_contacts (id, lace_id, account_id, key, name, source) VALUES"
                     " (%s, %s, %s, 'amina', 'Amina', 'discovery')", (uuid.uuid4(), ada, account))
        for status in ("sent", "draft"):
            conn.execute("INSERT INTO lace_outreach (id, lace_id, user_id, account_id, channel, status,"
                         " recipient_company, body) VALUES (%s, %s, %s, %s, 'email', %s, 'SunCulture', 'Hi')",
                         (uuid.uuid4(), ada, user.id, account, status))
        _run(conn, user.id, ada, "lace_turn", "priced-model", 500_000)
        _run(conn, user.id, ada, "lace_accounts", "priced-model", 1_000_000)
        _run(conn, user.id, bo, "lace_turn", "unpriced-model", 10)
    return {"ada": str(ada), "bo": str(bo)}


def test_laces_list_with_counts_and_cost(client, laces):
    page = client.get(f"{API}/laces").json()
    assert page["total"] == 3  # with owned_runs' "Owner Lace"
    rows = {r["name"]: r for r in page["items"]}
    ada = rows["Ada"]
    assert (ada["facts"], ada["competitors"], ada["accounts"], ada["contacts"], ada["sent"], ada["runs"]) == (1, 1, 1, 1, 1, 2)
    assert ada["cost_usd"] == 3.0 and ada["user_email"] == "owner@example.com"
    assert rows["Bo"]["cost_usd"] is None  # some of its usage has no price
    assert [r["name"] for r in client.get(f"{API}/laces", params={"q": "shanga"}).json()["items"]] == ["Ada"]


def test_lace_detail_and_its_runs(client, laces):
    detail = client.get(f"{API}/laces/{laces['ada']}").json()
    assert (detail["suggestions"], detail["drafts_waiting"], detail["brief_frequency"]) == (1, 1, "daily")
    assert sorted(r["kind"] for r in detail["recent_runs"]) == ["lace_accounts", "lace_turn"]
    assert all(r["lace_name"] == "Ada" for r in detail["recent_runs"])
    runs = client.get(f"{API}/runs", params={"lace_id": laces["bo"]}).json()
    assert runs["total"] == 1 and runs["items"][0]["lace_name"] == "Bo"
    assert client.get(f"{API}/laces/{uuid.uuid4()}").status_code == 404


@pytest.mark.parametrize("path", ["/laces", f"/laces/{uuid.uuid4()}"])
def test_lace_views_are_admin_only(client, path):
    assert client.get(f"{API}{path}").status_code == 403
    client.sign_in(make_user("Boss", is_admin=True))
    assert client.get(f"{API}/laces", params={"per_page": 1000}).status_code == 422
