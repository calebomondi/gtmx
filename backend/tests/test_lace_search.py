"""Search across a founder's Laces: everything each Lace knows and found, by
name or text, scoped to the founder, with dismissed and archived things left
out and matches that start with the query first."""

import uuid

import psycopg

from backend.tests.helpers import make_user
from backend.tests.test_lace_jobs import lace  # noqa: F401 -- fixture
from backend.tests.test_laces_api import API, lace_runtime  # noqa: F401 -- fixture
from config import settings


def _seed(lace_id, user_id):
    with psycopg.connect(settings.database_url, autocommit=True) as conn:
        def add(sql, *params):
            conn.execute(sql, (uuid.uuid4(), lace_id, *params))
        add("INSERT INTO lace_facts (id, lace_id, topic, claim, source_url, confidence, origin) VALUES"
            " (%s, %s, 'pricing', 'Fleet tracking costs KES 1,500 per vehicle.', 'https://a.test', 'high', 'crawl')")
        add("INSERT INTO lace_competitors (id, lace_id, name, website, domain_key, status) VALUES"
            " (%s, %s, 'Fleetsmart', 'https://fleetsmart.test', 'fleetsmart.test', 'suggested')")
        add("INSERT INTO lace_competitors (id, lace_id, name, website, domain_key, status) VALUES"
            " (%s, %s, 'Fleetgone', 'https://fleetgone.test', 'fleetgone.test', 'dismissed')")
        account = uuid.uuid4()
        conn.execute("INSERT INTO lace_accounts (id, lace_id, key, name, account_type, record, geo) VALUES"
                     " (%s, %s, 'sun.test', 'SunCulture', 'company', '{}', 'Kenya')", (account, lace_id))
        conn.execute("INSERT INTO lace_contacts (id, lace_id, account_id, key, name, title, email, source) VALUES"
                     " (%s, %s, %s, 'amina@sun.test', 'Amina Otieno', 'Head of fleet', 'amina@sun.test', 'discovery')",
                     (uuid.uuid4(), lace_id, account))
        add("INSERT INTO lace_opportunities (id, lace_id, kind, title, url, url_key, organiser) VALUES"
            " (%s, %s, 'sell', 'County fleet tender', 'https://t.test', 't.test', 'Nairobi County')")
        add("INSERT INTO lace_outreach (id, lace_id, user_id, account_id, channel, status, recipient_name,"
            " recipient_company, subject, body) VALUES (%s, %s, %s, %s, 'email', 'sent', 'Amina Otieno', 'SunCulture',"
            " 'Fleet costs', 'Hi Amina')", user_id, account)


def _search(client, q, **params):
    response = client.get(f"{API}/laces/search", params={"q": q, **params})
    assert response.status_code == 200, response.text
    return [(h["kind"], h["title"]) for h in response.json()]


def test_search_finds_what_each_lace_has(client, lace, user):  # noqa: F811
    _seed(lace, user.id)
    hits = _search(client, "fleet")
    assert ("fact", "Fleet tracking costs KES 1,500 per vehicle.") in hits
    assert ("competitor", "Fleetsmart") in hits and ("competitor", "Fleetgone") not in hits  # dismissed
    assert ("contact", "Amina Otieno") in hits  # by title
    assert ("opportunity", "County fleet tender") in hits
    assert ("conversation", "Amina Otieno") in hits  # by subject
    assert _search(client, "kenya") == [("account", "SunCulture")]
    first = client.get(f"{API}/laces/search", params={"q": "acme"}).json()[0]  # the Lace's site
    assert (first["kind"], first["lace_id"]) == ("lace", lace)


def test_search_is_scoped_bounded_and_escaped(client, lace, user):  # noqa: F811
    _seed(lace, user.id)
    assert len(_search(client, "fleet", per_kind=1)) <= 7
    assert _search(client, "100%") == []  # a literal %, not a wildcard
    assert client.get(f"{API}/laces/search", params={"q": "f"}).status_code == 422
    with psycopg.connect(settings.database_url, autocommit=True) as conn:
        conn.execute("UPDATE laces SET status = 'archived' WHERE id = %s", (lace,))
    assert _search(client, "fleet") == []
    with psycopg.connect(settings.database_url, autocommit=True) as conn:
        conn.execute("UPDATE laces SET status = 'active' WHERE id = %s", (lace,))
    client.sign_in(make_user("Intruder"))
    assert _search(client, "fleet") == []
