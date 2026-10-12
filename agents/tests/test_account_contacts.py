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


_PROFILE = """# Nathan Nwachuku

CEO, Terra Industries

## Experience

### Co-founder and CEO - [Terra Industries](https://www.linkedin.com/company/terrahaptix)
"""


def test_profiles_titled_with_only_a_name_are_read_from_their_text():
    assert contacts._person_from_profile("nathan nwachuku", _PROFILE, "Terra Industries") == (
        "Nathan Nwachuku", "Co-founder and CEO")
    assert contacts._person_from_profile("Jo Bloggs", "# Jo Bloggs\n\nCTO at Acme\n", "Acme") == ("Jo Bloggs", "CTO")
    assert contacts._person_from_profile("Jo Bloggs", "# Jo Bloggs\n\nCTO at Other Co\n", "Acme") == (None, None)
    assert contacts._person_from_profile("Acme", "# Acme\n\nAcme is a software company\n", "Acme") == (None, None)


def test_a_namesake_company_page_is_not_the_account():
    page = "https://ng.linkedin.com/company/terra-mining"
    assert contacts._person_from_profile("n", _PROFILE, "Terra Industries", page) == (None, None)
    assert contacts._person_from_profile("n", _PROFILE, "Terra Industries", "https://linkedin.com/company/terrahaptix")[0]


def test_only_decision_makers_are_kept():
    assert contacts._decides("Co-founder and CEO", [])
    assert contacts._decides("Procurement Officer", ["procurement officer"])
    assert contacts._decides(None, [])
    assert not contacts._decides("Warehouse Assistant", ["CEO"])


def test_people_search_reads_profiles_and_skips_junior_staff(monkeypatch):
    hits = [
        {"url": "https://linkedin.com/in/nathan", "title": "nathan nwachuku", "text": _PROFILE},
        {"url": "https://linkedin.com/in/ajayi", "title": "Ajayi", "text": "# Ajayi\n\nWarehouse Assistant at Terra Industries\n"},
    ]
    monkeypatch.setattr(contacts, "search_and_scrape", lambda *a, **k: hits)
    acc = _account(socials={"linkedin": "https://www.linkedin.com/company/terrahaptix"})
    acc.name = "Terra Industries"
    people = contacts.people_on_linkedin(acc, ["CEO"], None)
    assert [(p.name, p.title) for p in people] == [("Nathan Nwachuku", "Co-founder and CEO")]


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


def _named(name, domain, event):
    acc = _account(key_contacts=[ContactRecord(email=f"info@{domain}")])
    acc.name, acc.domain, acc.website = name, domain, f"https://{domain}"
    acc.trigger_event.event = event
    return acc


def test_competitors_and_the_offer_itself_are_never_targets():
    """Geviton was both a tracked competitor and a target account."""
    accounts = [
        _named("Geviton", "geviton.co.ke", "Launched Darubini at Aga Khan University Hospital"),
        _named("Shanga Labs", "shangalabs.com", "Opened a new lab"),
        _named("Africhips", "africhip.com", "Signed an MoU with RMRDC for a semiconductor factory"),
    ]
    kept = discovery.verify_accounts({"accounts": AccountList(accounts=accounts),
                                      "exclude_domains": ["geviton.co.ke", "www.shangalabs.com"]})
    assert [a.name for a in kept["accounts"].accounts] == ["Africhips"]


@pytest.mark.parametrize("event", [
    "Long-established player (since 1997) with consistent focus on traceability",
    "Company profile indicates ongoing growth (+9.1% YoY)",
    "Active sales of electronics cases and filaments",
    "Maintaining high growth with 8 million+ customers",
])
def test_triggers_that_describe_the_company_are_not_triggers(event):
    kept = discovery.verify_accounts({"accounts": AccountList(accounts=[_named("Acme", "acme.example", event)])})
    assert kept["accounts"].accounts == []


def test_each_target_country_gets_its_own_search(monkeypatch):
    """One search over three countries returned Nigerian accounts only."""
    from agents.schemas.icp import ICP

    searched = []

    class Graph:
        def invoke(self, state):
            geo = state["target_market"][0]
            searched.append((geo, state["icp_data"].geo))
            acc = _named(f"Acme {geo}", f"acme-{geo.lower().replace(' ', '')}.example", "Raised a Series A")
            acc.score = 0.5
            return {"accounts": AccountList(accounts=[acc]), "account_discovery_docs": []}
    monkeypatch.setattr(discovery, "build_account_discovery_graph", lambda checkpointer: Graph())
    state = {"icp_data": ICP(geo=["Kenya", "Nigeria", "South Africa"]), "target_market": ["Kenya", "Nigeria", "South Africa"]}
    result = discovery.run_account_discovery_by_country(state)
    assert sorted(searched) == [("Kenya", ["Kenya"]), ("Nigeria", ["Nigeria"]), ("South Africa", ["South Africa"])]
    assert len(result["accounts"].accounts) == 3
