"""Dismissing a find with a reason teaches the Lace's profile what to steer
clear of; without one, or for a private find, nothing is learned."""

import json
import uuid

import psycopg

from backend.tests.test_lace_accounts import _with_icp
from backend.tests.test_lace_jobs import lace  # noqa: F401 -- fixture
from backend.tests.test_laces_api import API, lace_runtime  # noqa: F401 -- fixture
from config import settings


def _account(lace_id, name, owner_id=None) -> str:
    with psycopg.connect(settings.database_url, autocommit=True) as conn:
        return str(conn.execute(
            "INSERT INTO lace_accounts (id, lace_id, owner_id, key, name, account_type, record, status) VALUES"
            " (%s, %s, %s, %s, %s, 'company', '{}', 'suggested') RETURNING id",
            (uuid.uuid4(), lace_id, owner_id, name.lower(), name)).fetchone()[0])


def _exclusions(lace_id) -> list[str]:
    with psycopg.connect(settings.database_url) as conn:
        icp = conn.execute("SELECT icp FROM laces WHERE id = %s", (lace_id,)).fetchone()[0]
    return (icp if isinstance(icp, dict) else json.loads(icp or "{}")).get("exclusions", [])


def test_a_reason_becomes_an_exclusion(client, lace):  # noqa: F811
    _with_icp(lace)
    tea = _account(lace, "Kericho Gold")
    out = client.patch(f"{API}/laces/{lace}/accounts/{tea}",
                       json={"status": "dismissed", "reason": "not_our_buyer", "note": "tea estates don't build apps"})
    assert out.status_code == 200 and out.json()["status"] == "dismissed"
    assert _exclusions(lace) == ["Like Kericho Gold (not our buyer: tea estates don't build apps)"]
    # The same dismissal twice is learned once.
    client.patch(f"{API}/laces/{lace}/accounts/{tea}", json={"status": "dismissed", "reason": "not_our_buyer",
                                                            "note": "tea estates don't build apps"})
    assert len(_exclusions(lace)) == 1


def test_no_reason_or_a_private_find_teaches_nothing(client, lace):  # noqa: F811
    _with_icp(lace)
    plain = _account(lace, "Ryman")
    assert client.patch(f"{API}/laces/{lace}/accounts/{plain}", json={"status": "dismissed"}).status_code == 200
    mine = _account(lace, "Robert Dyas", owner_id=None)
    with psycopg.connect(settings.database_url, autocommit=True) as conn:
        conn.execute("UPDATE lace_accounts SET owner_id = (SELECT user_id FROM laces WHERE id = %s) WHERE id = %s",
                     (lace, mine))
    client.patch(f"{API}/laces/{lace}/accounts/{mine}", json={"status": "dismissed", "reason": "too_small"})
    assert _exclusions(lace) == []


def test_a_reason_goes_only_with_dismissing(client, lace):  # noqa: F811
    _with_icp(lace)
    acme = _account(lace, "Acme")
    assert client.patch(f"{API}/laces/{lace}/accounts/{acme}",
                        json={"status": "target", "reason": "too_small"}).status_code == 422
    assert client.patch(f"{API}/laces/{lace}/accounts/{acme}",
                        json={"status": "dismissed", "reason": "made_up"}).status_code == 422
