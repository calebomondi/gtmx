"""A Lace's contact rows: the people at its target accounts, synced when an
account search or a contact search saves them, one per person."""

import uuid

import psycopg

from agents.schemas.accounts import AccountRecord, ContactRecord
from backend.app.database.connect import AsyncSessionLocal
from backend.app.services import lace_accounts
from backend.app.services.lace_contacts import contact_key
from backend.tests.helpers import make_user
from backend.tests.test_lace_accounts import _found
from backend.tests.test_lace_jobs import lace  # noqa: F401 -- fixture
from backend.tests.test_laces_api import API, lace_runtime  # noqa: F401 -- fixture
from config import settings

AMINA = ContactRecord(name="Amina Otieno", title="COO", email="Amina@SunCulture.test ")


def test_contact_key_prefers_email_then_linkedin_then_name():
    assert contact_key(AMINA) == "amina@sunculture.test"
    assert contact_key(ContactRecord(name="A", linkedin="https://linkedin.com/in/a/")) == "https://linkedin.com/in/a"
    assert contact_key(ContactRecord(name=" Bo ")) == "bo"
    assert contact_key(ContactRecord(title="CEO")) is None


async def _search(lace_id, *found):
    async with AsyncSessionLocal() as db, db.begin():
        await lace_accounts.upsert_found(db, uuid.UUID(lace_id), None, list(found))


async def _contact_search(lace_id, name, contacts):
    async with AsyncSessionLocal() as db, db.begin():
        account = next(a for a in await lace_accounts.list_for_lace(db, uuid.UUID(lace_id), "target", 10) if a.name == name)
        record = AccountRecord.model_validate(account.record).model_copy(update={"key_contacts": contacts})
        await lace_accounts.save_contacts(db, account.id, record)


def _save_accounts(lace_id):
    with psycopg.connect(settings.database_url, autocommit=True) as conn:
        conn.execute("UPDATE lace_accounts SET status = 'target' WHERE lace_id = %s", (lace_id,))


def _contacts(client, lace_id):
    return client.get(f"{API}/laces/{lace_id}/contacts").json()


def test_contacts_carry_their_own_social_accounts(client, lace):  # noqa: F811
    record, fit = _found("SunCulture", "strong")
    amina = AMINA.model_copy(update={"x": "@amina_o", "instagram": "https://instagram.com/amina.o",
                                     "facebook": "https://elsewhere.test/amina", "tiktok": None})
    client.portal.call(_search, lace, (record.model_copy(update={"key_contacts": [amina]}), fit))
    _save_accounts(lace)
    [row] = _contacts(client, lace)
    assert (row["x"], row["instagram"], row["facebook"], row["tiktok"]) == (
        "https://x.com/amina_o", "https://instagram.com/amina.o", None, None)


def test_searches_fill_contacts_one_row_per_person(client, lace):  # noqa: F811
    record, fit = _found("SunCulture", "strong")
    client.portal.call(_search, lace, (record.model_copy(update={"key_contacts": [AMINA]}), fit))
    assert _contacts(client, lace) == []  # the account is only suggested
    _save_accounts(lace)
    [row] = _contacts(client, lace)
    assert (row["name"], row["email"], row["account_name"], row["source"]) == (
        "Amina Otieno", "Amina@SunCulture.test", "SunCulture", "discovery")

    # The contact search sees her again, now with a LinkedIn, and finds someone new.
    client.portal.call(_contact_search, lace, "SunCulture", [
        ContactRecord(name="Amina Otieno", email="amina@sunculture.test", linkedin="https://linkedin.com/in/amina"),
        ContactRecord(name="Kip Mwangi", title="Head of Ops", linkedin="https://linkedin.com/in/kip/"),
    ])
    rows = {r["name"]: r for r in _contacts(client, lace)}
    assert set(rows) == {"Amina Otieno", "Kip Mwangi"}
    assert rows["Amina Otieno"]["title"] == "COO"  # kept: the new sighting had no title
    assert rows["Amina Otieno"]["linkedin"] == "https://linkedin.com/in/amina"
    assert rows["Kip Mwangi"]["source"] == "contact_search"


def test_dismissed_accounts_people_are_not_listed(client, lace):  # noqa: F811
    record, fit = _found("Twiga", "moderate")
    client.portal.call(_search, lace, (record.model_copy(update={"key_contacts": [AMINA]}), fit))
    with psycopg.connect(settings.database_url, autocommit=True) as conn:
        conn.execute("UPDATE lace_accounts SET status = 'dismissed' WHERE lace_id = %s", (lace,))
    assert _contacts(client, lace) == []
    client.sign_in(make_user("Intruder"))
    assert client.get(f"{API}/laces/{lace}/contacts").status_code == 404
