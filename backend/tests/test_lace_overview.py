"""Home's tabs: what every live Lace of the founder's has saved, each item
with its Lace, and what waits for review; nothing from archived Laces or
from anyone else's."""

import uuid

import psycopg

from backend.tests.test_lace_jobs import lace  # noqa: F401 -- fixture
from backend.tests.test_laces_api import API, lace_runtime  # noqa: F401 -- fixture
from config import settings


def _lace(conn, user_id, name, status="active") -> uuid.UUID:
    return conn.execute("INSERT INTO laces (id, user_id, name, website, status) VALUES (%s, %s, %s, %s, %s)"
                        " RETURNING id", (uuid.uuid4(), user_id, name, f"https://{name.lower()}.test", status)).fetchone()[0]


def _competitor(conn, lace_id, name, status="tracked"):
    conn.execute("INSERT INTO lace_competitors (id, lace_id, name, website, domain_key, status) VALUES"
                 " (%s, %s, %s, %s, %s, %s)", (uuid.uuid4(), lace_id, name, f"https://{name}.test", f"{name}.test", status))


def _account(conn, lace_id, name, status="target"):
    conn.execute("INSERT INTO lace_accounts (id, lace_id, key, name, account_type, record, status) VALUES"
                 " (%s, %s, %s, %s, 'company', %s, %s)",
                 (uuid.uuid4(), lace_id, name.lower(), name, f'{{"name": "{name}"}}', status))


def test_saved_across_the_founders_live_laces(client, lace, user):  # noqa: F811
    with psycopg.connect(settings.database_url, autocommit=True) as conn:
        other = _lace(conn, user.id, "Bo")
        shelved = _lace(conn, user.id, "Shelved", status="archived")
        stranger = _lace(conn, uuid.uuid4(), "Theirs")
        _competitor(conn, lace, "rival")
        _competitor(conn, lace, "maybe", status="suggested")
        _competitor(conn, shelved, "hidden")
        _competitor(conn, stranger, "private")
        _account(conn, other, "Twiga")
        _account(conn, other, "Lori", status="suggested")

    saved = client.get(f"{API}/laces/saved").json()
    assert [(c["name"], c["lace_name"]) for c in saved["competitors"]] == [("rival", "Ada")]
    assert [(a["name"], a["lace_id"]) for a in saved["accounts"]] == [("Twiga", str(other))]
    assert saved["opportunities"] == []
    assert saved["to_review"] == {"opportunities": 0, "accounts": 1, "competitors": 1}
