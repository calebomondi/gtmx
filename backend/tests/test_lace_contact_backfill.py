"""The contacts backfill: people already in account records become contact
rows keyed exactly as the app keys them, once, without touching rows that
were synced since."""

import importlib.util
import json
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path

import psycopg

from agents.schemas.accounts import ContactRecord
from backend.app.services.lace_contacts import contact_key
from backend.tests.test_lace_jobs import lace  # noqa: F401 -- fixture
from backend.tests.test_laces_api import lace_runtime  # noqa: F401 -- fixture
from config import settings

_MIGRATION = (Path(__file__).parents[1] / "app/database/migrations/versions/20261019_0927_backfill_lace_contacts.py")


def _backfill_sql() -> str:
    spec = importlib.util.spec_from_file_location("backfill_lace_contacts", _MIGRATION)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.BACKFILL_SQL


PEOPLE = [
    {"name": "  Amina Otieno ", "title": "COO", "email": " Amina@SunCulture.test ", "linkedin": None},
    {"name": "Kip Mwangi", "title": "Head of Ops", "email": "", "linkedin": "https://linkedin.com/in/Kip/ "},
    {"name": "Wanjiru", "title": None, "email": None, "linkedin": None},
    {"name": None, "title": "CEO", "email": None, "linkedin": None},  # nobody to key on: skipped
]


def _account(conn, lace_id, key, contacts, checked: bool, seen: datetime) -> uuid.UUID:
    account_id = uuid.uuid4()
    conn.execute(
        "INSERT INTO lace_accounts (id, lace_id, key, name, account_type, record, contacts_checked_at, last_seen_at)"
        " VALUES (%s, %s, %s, %s, 'company', %s, %s, %s)",
        (account_id, lace_id, key, key, json.dumps({"name": key, "key_contacts": contacts}),
         seen if checked else None, seen))
    return account_id


def test_backfill_keys_like_the_app_once(lace):  # noqa: F811
    now = datetime.now(UTC)
    with psycopg.connect(settings.database_url, autocommit=True) as conn:
        older = _account(conn, lace, "old.test", PEOPLE, checked=False, seen=now - timedelta(days=2))
        newer = _account(conn, lace, "new.test", [PEOPLE[2]], checked=True, seen=now)  # Wanjiru again
        _account(conn, lace, "none.test", None, checked=False, seen=now)  # no key_contacts at all
        # Synced since the table existed: the backfill must leave it alone.
        conn.execute("INSERT INTO lace_contacts (id, lace_id, account_id, key, name, title, source) VALUES"
                     " (%s, %s, %s, 'amina@sunculture.test', 'Amina O.', 'Chief Operating Officer', 'contact_search')",
                     (uuid.uuid4(), lace, older))
        sql = _backfill_sql()
        conn.execute(sql)
        conn.execute(sql)  # idempotent
        rows = {r[0]: r[1:] for r in conn.execute(
            "SELECT key, account_id, name, title, email, linkedin, source FROM lace_contacts WHERE lace_id = %s",
            (lace,)).fetchall()}

    assert set(rows) == {contact_key(ContactRecord(**p)) for p in PEOPLE[:3]}
    assert rows["amina@sunculture.test"][1:3] == ("Amina O.", "Chief Operating Officer")  # untouched
    assert rows["https://linkedin.com/in/kip"] == (older, "Kip Mwangi", "Head of Ops", None,
                                                   "https://linkedin.com/in/Kip/", "discovery")
    assert rows["wanjiru"][0] == newer and rows["wanjiru"][-1] == "contact_search"  # most recent account wins
