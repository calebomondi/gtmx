"""Account rows carry the agent's one-line summary end to end: from the
agent's record, through the stored row, to the API."""

import psycopg

from agents.schemas.accounts import AccountRecord
from backend.app.account_runner import _account_values
from config import settings


def test_summary_is_stored_from_the_agent_record():
    record = AccountRecord(
        name="4G Capital", summary="Nairobi lender financing SME stock and working capital.",
        trigger_event={"event": "Raised debt", "signal_type": "funding_round", "source": "https://news.example/4g"},
    )
    assert _account_values(record)["summary"] == "Nairobi lender financing SME stock and working capital."


def test_accounts_api_returns_the_summary(client, owned):
    with psycopg.connect(settings.database_url, autocommit=True) as conn:
        conn.execute("UPDATE accounts SET summary = 'Makes widgets for clinics.' WHERE id = %s", (owned["account"],))
    accounts = client.get(f"{settings.api_v1_str}/workspaces/{owned['workspace']}/accounts").json()["accounts"]
    assert [a["summary"] for a in accounts] == ["Makes widgets for clinics."]


def test_socials_are_stored_and_returned(client, owned):
    record = AccountRecord(
        name="Acme", socials={"linkedin": "https://linkedin.com/company/acme"},
        trigger_event={"event": "Hiring", "signal_type": "hiring_post", "source": "https://jobs.example/acme"},
    )
    assert _account_values(record)["socials"] == {"linkedin": "https://linkedin.com/company/acme"}
    with psycopg.connect(settings.database_url, autocommit=True) as conn:
        conn.execute("UPDATE accounts SET socials = %s WHERE id = %s",
                     ('{"instagram": "https://instagram.com/acme"}', owned["account"]))
    [account] = client.get(f"{settings.api_v1_str}/workspaces/{owned['workspace']}/accounts").json()["accounts"]
    assert account["socials"] == {"instagram": "https://instagram.com/acme"}


async def test_account_runs_exclude_the_offer_and_its_competitors(user, seed_workspace, monkeypatch):
    import uuid as _uuid

    from psycopg.types.json import Jsonb

    from backend.app import account_runner

    workspace_id = seed_workspace(user.id, "WS")
    with psycopg.connect(settings.database_url, autocommit=True) as conn:
        conn.execute(
            "INSERT INTO product_profiles (id, workspace_id, product_url, target_geo, insights) VALUES (%s, %s, %s, %s, %s)",
            (_uuid.uuid4(), workspace_id, "https://www.shangalabs.com/", Jsonb([]), Jsonb({"icp": {"industries": ["IoT"]}})),
        )
        conn.execute(
            "INSERT INTO competitors (id, workspace_id, name, website, domain_key, source, strengths, weaknesses,"
            " opportunities, notable_customers, pain_signals, customer_sentiment, tracking_sources, evidence,"
            " unsourced_fields) VALUES (%s, %s, 'Geviton', 'https://geviton.co.ke', 'geviton.co.ke', 'agent',"
            " '[]', '[]', '[]', '[]', '[]', '[]', '[]', '{}', '[]')",
            (_uuid.uuid4(), workspace_id),
        )
    seen = {}

    class Graph:
        def invoke(self, state):
            seen.update(state)
            return {"accounts": None}
    monkeypatch.setattr(account_runner, "build_account_discovery_graph", lambda checkpointer: Graph())
    await account_runner.run_account_discovery_for_workspace(_uuid.UUID(workspace_id))
    assert sorted(seen["exclude_domains"]) == ["geviton.co.ke", "shangalabs.com"]
