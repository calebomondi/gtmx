"""Suggested, then saved: what a search finds waits for the founder, the Lace
can show it, the brief and the sidebar say it is waiting, and nothing is
worked from until it is saved."""

import uuid
from datetime import UTC, datetime

import psycopg

from agents.lace.cards import cards
from backend.app.database.connect import AsyncSessionLocal
from backend.app.services import lace_briefs
from backend.app.services.lace_store import DbLaceStore
from backend.tests.test_lace_jobs import lace  # noqa: F401 -- fixture
from backend.tests.test_laces_api import API, lace_runtime  # noqa: F401 -- fixture
from config import settings


def _suggest(lace_id) -> dict[str, str]:
    ids = {"competitor": str(uuid.uuid4()), "account": str(uuid.uuid4()), "opportunity": str(uuid.uuid4())}
    with psycopg.connect(settings.database_url, autocommit=True) as conn:
        conn.execute("INSERT INTO lace_competitors (id, lace_id, name, website, domain_key, status) VALUES"
                     " (%s, %s, 'Rival', 'https://rival.test', 'rival.test', 'suggested')", (ids["competitor"], lace_id))
        conn.execute("INSERT INTO lace_accounts (id, lace_id, key, name, account_type, record, status) VALUES"
                     " (%s, %s, 'sun.test', 'SunCulture', 'company', '{\"name\": \"SunCulture\"}', 'suggested')",
                     (ids["account"], lace_id))
        conn.execute("INSERT INTO lace_opportunities (id, lace_id, kind, title, url, url_key, status) VALUES"
                     " (%s, %s, 'sell', 'Fleet tender', 'https://t.test', 't.test', 'suggested')",
                     (ids["opportunity"], lace_id))
    return ids


def _store(lace_id) -> DbLaceStore:
    return DbLaceStore(AsyncSessionLocal, uuid.UUID(lace_id))


async def _read(lace_id):
    store = _store(lace_id)
    return (await store.suggestions(), await store.competitors(), await store.accounts(), await store.opportunities())


def test_suggestions_wait_apart_from_what_is_saved(client, lace):  # noqa: F811
    ids = _suggest(lace)
    suggested, rivals, accounts, opportunities = client.portal.call(_read, lace)
    assert [c.name for c in suggested.competitors] == ["Rival"] and rivals == []
    assert [a.name for a in suggested.accounts] == ["SunCulture"] and accounts == []
    assert [o.title for o in suggested.opportunities] == ["Fleet tender"] and opportunities == []

    # The Lace can show them, and the founder saves one.
    shown, missing = client.portal.call(cards, _store(lace), "competitor", [ids["competitor"]])
    assert [c.title for c in shown] == ["Rival"] and missing == []
    client.patch(f"{API}/laces/{lace}/competitors/{ids['competitor']}", json={"status": "tracked"})
    suggested, rivals, _, _ = client.portal.call(_read, lace)
    assert suggested.competitors == [] and [r.name for r in rivals] == ["Rival"]


def test_suggestions_keep_the_mascot_alert(client, lace):  # noqa: F811
    mood = lambda: {r["id"]: r for r in client.get(f"{API}/laces").json()}[lace]["mood"]  # noqa: E731
    assert mood() is None
    ids = _suggest(lace)
    assert mood() == "alert"
    client.patch(f"{API}/laces/{lace}/competitors/{ids['competitor']}", json={"status": "dismissed"})
    client.patch(f"{API}/laces/{lace}/accounts/{ids['account']}", json={"status": "target"})
    client.patch(f"{API}/laces/{lace}/opportunities/{ids['opportunity']}", json={"status": "open"})
    assert mood() is None


async def _digest(lace_id):
    async with AsyncSessionLocal() as db:
        return await lace_briefs.digest(db, uuid.UUID(lace_id), datetime(2000, 1, 1, tzinfo=UTC),
                                        datetime.now(UTC).date())


def test_the_brief_says_what_waits(client, lace):  # noqa: F811
    _suggest(lace)
    text = client.portal.call(_digest, lace)
    assert "New competitors found:\n- Rival (https://rival.test)" in text
    assert "Suggestions waiting for the founder to save or dismiss: 1 competitors, 1 accounts, 1 opportunities" in text
