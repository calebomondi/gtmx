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
