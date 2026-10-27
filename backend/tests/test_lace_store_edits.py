"""Changes a Lace makes for the founder through its store: only to its own
rows, removals that hide rather than delete, people added as approved, and
drafts that can be rewritten or discarded but never once sent."""

import uuid

import psycopg
import pytest

from agents.schemas.lace import NewContact, NewFact
from backend.app.database.connect import AsyncSessionLocal
from backend.app.services.lace_store import DbLaceStore
from backend.tests.test_lace_contacts import _account
from backend.tests.test_lace_store import _seed_lace
from config import settings


@pytest.fixture
def lace_id() -> uuid.UUID:
    return _seed_lace()


@pytest.fixture
def store(lace_id) -> DbLaceStore:
    return DbLaceStore(AsyncSessionLocal, lace_id)


def _sql(query: str, *args):
    with psycopg.connect(settings.database_url, autocommit=True) as conn:
        return conn.execute(query, args).fetchall() if query.lstrip().upper().startswith(("SELECT", "INSERT")) \
            else conn.execute(query, args)


def _opportunity(lace_id, title: str) -> str:
    [(row_id,)] = _sql("INSERT INTO lace_opportunities (id, lace_id, kind, title, url, url_key, why_it_fits, status)"
                       " VALUES (%s, %s, 'showcase', %s, %s, %s, 'Fits.', 'open') RETURNING id",
                       uuid.uuid4(), lace_id, title, f"https://{title}.test", f"{title}.test")
    return str(row_id)


def _draft(lace_id, status: str = "draft") -> str:
    [(user_id,)] = _sql("SELECT user_id FROM laces WHERE id = %s", lace_id)
    [(row_id,)] = _sql("INSERT INTO lace_outreach (id, lace_id, user_id, channel, recipient_company, recipient_name,"
                       " subject, body, status, direction) VALUES (%s, %s, %s, 'email', 'SunCulture', 'Amina', 'Hi',"
                       " 'Long note', %s, 'outbound') RETURNING id", uuid.uuid4(), lace_id, user_id, status)
    return str(row_id)


async def test_removed_items_leave_the_lists_and_can_come_back(store, lace_id):
    expo, tender = _opportunity(lace_id, "expo"), _opportunity(lace_id, "tender")
    theirs = _opportunity(_seed_lace("Other"), "theirs")
    result = await store.set_saved("opportunity", [expo, theirs, "not-an-id"], "remove")
    assert [c.name for c in result.changed] == ["expo"] and result.missing == [theirs, "not-an-id"]
    assert [o.id for o in await store.opportunities()] == [tender]
    assert [r.name for r in await store.removed("opportunity")] == ["expo"]
    await store.set_saved("opportunity", [expo], "save")
    assert {o.id for o in await store.opportunities()} == {expo, tender}
    [(status,)] = _sql("SELECT status FROM lace_opportunities WHERE id = %s", theirs)
    assert status == "open"


async def test_accounts_and_competitors_are_removed_or_brought_back(store, lace_id):
    account = str(_account(lace_id, "SunCulture"))
    await store.set_saved("account", [account], "remove")
    assert await store.accounts() == [] and [r.id for r in await store.removed("account")] == [account]
    [(rival,)] = _sql("INSERT INTO lace_competitors (id, lace_id, name, website, domain_key, status) VALUES"
                      " (%s, %s, 'Rival', 'https://rival.test', 'rival.test', 'suggested') RETURNING id",
                      uuid.uuid4(), lace_id)
    # A suggestion is the founder's to save: the Lace's save leaves it for them.
    result = await store.set_saved("competitor", [str(rival)], "save")
    assert result.changed == [] and [i.name for i in result.for_founder] == ["Rival"]
    assert await store.competitors() == []
    await store.set_saved("competitor", [str(rival)], "remove")
    await store.set_saved("competitor", [str(rival)], "save")
    assert [c.name for c in await store.competitors()] == ["Rival"]


async def test_a_wrong_fact_is_forgotten(store):
    fact = await store.record_fact(NewFact(topic="offer", claim="Sells payroll.", source_url="https://acme.test"))
    result = await store.retract_facts([fact.id, str(uuid.uuid4())])
    assert [c.name for c in result.changed] == ["Sells payroll."] and len(result.missing) == 1
    assert await store.facts() == []


async def test_a_named_person_is_added_approved_at_a_new_or_existing_account(store, lace_id):
    added = await store.add_contact(NewContact(company="Thalace", name="Kaleb Mokua", email="kaleb@thalace.test"))
    assert (added.company, added.email, added.approved) == ("Thalace", "kaleb@thalace.test", True)
    [account] = await store.accounts()
    assert account.name == "Thalace" and account.contacts == [{"name": "Kaleb Mokua", "email": "kaleb@thalace.test"}]
    [(source, trigger)] = _sql("SELECT c.source, a.record->'trigger_event'->>'signal_type' FROM lace_contacts c"
                               " JOIN lace_accounts a ON a.id = c.account_id WHERE c.id = %s", added.id)
    assert (source, trigger) == ("founder", "founder_added")

    existing = str(_account(lace_id, "SunCulture"))
    _sql("UPDATE lace_accounts SET status = 'dismissed' WHERE id = %s", existing)
    amina = await store.add_contact(NewContact(company="sunculture", name="Amina", title="COO", email="a@sun.test"))
    assert amina.account_id == existing
    assert {c.name for c in await store.contacts()} == {"Kaleb Mokua", "Amina"}

    removed = await store.remove_contacts([added.id, str(uuid.uuid4())])
    assert [c.name for c in removed.changed] == ["Kaleb Mokua"] and len(removed.missing) == 1
    assert [c.name for c in await store.contacts()] == ["Amina"]
    assert next(a for a in await store.accounts() if a.name == "Thalace").contacts == []


async def test_drafts_are_rewritten_or_discarded_but_sent_ones_are_kept(store, lace_id):
    draft, sent = _draft(lace_id), _draft(lace_id, "sent")
    rewritten = await store.edit_draft(draft, None, "Short note")
    assert (rewritten.subject, rewritten.body) == ("Hi", "Short note")
    with pytest.raises(ValueError):
        await store.edit_draft(sent, None, "Too late")
    with pytest.raises(KeyError):
        await store.edit_draft(_draft(_seed_lace("Other")), None, "Not mine")
    result = await store.discard_drafts([draft, sent])
    assert [c.name for c in result.changed] == ["Amina"] and result.missing == [sent]
    assert [(r,) for (r,) in _sql("SELECT status FROM lace_outreach WHERE lace_id = %s", lace_id)] == [("sent",)]
