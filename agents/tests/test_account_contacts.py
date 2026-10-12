"""Every kept account has someone to contact: people come from the account's
own pages and a LinkedIn people search, ranked best-first, and addresses on
domains with no mail server are dropped."""

import pytest

from agents.pipelines.accounts import account_discovery as discovery
from agents.pipelines.accounts import contacts
from agents.schemas.accounts import AccountList, AccountRecord, ContactRecord


def _account(**kw) -> AccountRecord:
    return AccountRecord(
        name="Acme", website="https://acme.example", domain="acme.example",
        trigger_event={"event": "Hiring", "signal_type": "hiring_post", "source": "https://acme.example/jobs"},
        **kw,
    )


@pytest.fixture(autouse=True)
def mail(monkeypatch):
    dead = {"dead.example"}
    monkeypatch.setattr(contacts, "accepts_mail", lambda domain: domain not in dead)


def test_linkedin_result_titles_become_named_people():
    assert contacts._person_from_result("Jane Doe - Head of Growth - Acme | LinkedIn", "Acme") == ("Jane Doe", "Head of Growth")
    assert contacts._person_from_result("Jane Doe - Acme | LinkedIn", "Acme") == ("Jane Doe", None)
    assert contacts._person_from_result("Jane Doe - Head of Growth - Other Co", "Acme") == (None, None)


def test_merge_ranks_people_first_and_drops_dead_addresses():
    merged = contacts.merge(
        [ContactRecord(email="info@acme.example")],
        [ContactRecord(email="sam@dead.example"), ContactRecord(name="Jane", linkedin="https://linkedin.com/in/jane"),
         ContactRecord(name="Bo", email="bo@acme.example"), ContactRecord(email="INFO@acme.example"),
         ContactRecord(email="noreply@acme.example")],
        limit=6,
    )
    assert [(c.name, c.email, c.linkedin) for c in merged] == [
        ("Bo", "bo@acme.example", None),
        ("Jane", None, "https://linkedin.com/in/jane"),
        (None, "info@acme.example", None),
    ]


def test_complete_searches_the_site_then_linkedin(monkeypatch):
    monkeypatch.setattr(contacts, "_site_pages", lambda acc, cfg: ["Write to hello@acme.example or press@gmail.com"])
    searched = []

    def people(query, cfg, num_results):
        searched.append(query)
        return [{"url": "https://www.linkedin.com/in/jane-doe", "title": "Jane Doe - CTO - Acme | LinkedIn"}]
    monkeypatch.setattr(contacts, "search_and_scrape", people)

    acc = _account()
    contacts.complete(acc, ["CTO", "VP Engineering"], cfg=None, limit=6)
    assert [(c.name, c.email, c.linkedin) for c in acc.key_contacts] == [
        ("Jane Doe", None, "https://www.linkedin.com/in/jane-doe"),
        (None, "hello@acme.example", None),  # off-domain gmail ignored
    ]
    assert searched == ['site:linkedin.com/in "Acme" "CTO" OR "VP Engineering"']


def test_a_named_contact_with_email_needs_no_searching(monkeypatch):
    monkeypatch.setattr(contacts, "_site_pages", lambda *a: pytest.fail("site scraped"))
    monkeypatch.setattr(contacts, "search_and_scrape", lambda *a, **k: pytest.fail("searched"))
    acc = _account(key_contacts=[ContactRecord(name="Bo", email="bo@acme.example")])
    contacts.complete(acc, ["CTO"], cfg=None, limit=6)
    assert acc.key_contacts[0].email == "bo@acme.example"


def test_accounts_nobody_can_be_reached_at_are_dropped():
    reachable = _account(key_contacts=[ContactRecord(email="bo@acme.example")])
    social_only = _account(socials={"linkedin": "https://linkedin.com/company/acme"})
    social_only.name, social_only.domain, social_only.website = "Beta", "beta.example", "https://beta.example"
    nobody = _account()
    nobody.name, nobody.domain, nobody.website = "Gamma", "gamma.example", "https://gamma.example"
    kept = discovery.verify_accounts({"accounts": AccountList(accounts=[reachable, social_only, nobody])})
    assert [a.name for a in kept["accounts"].accounts] == ["Acme", "Beta"]
