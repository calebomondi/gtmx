"""A lead search's contact step: social-profile lookups stop at their time
budget, but an account's email is always looked for (outreach goes by
email)."""

from agents.pipelines.accounts import account_discovery as ad
from agents.schemas.accounts import AccountList, AccountRecord, TriggerEvent
from agents.schemas.icp import ICP


def _run(monkeypatch, budget_s: float) -> tuple[list[str], list[list[str]], AccountRecord]:
    searched, email_queries = [], []
    monkeypatch.setattr(ad, "_SOCIALS_BUDGET_S", budget_s)
    monkeypatch.setattr(ad, "_search_and_scrape", lambda q, cfg, **k: searched.append(q) or [])
    monkeypatch.setattr(ad, "_domain_emails_from_queries",
                        lambda queries, acc, cfg, cutoff: email_queries.append(queries) or ["info@acme.test"])
    monkeypatch.setattr(ad.contacts, "complete", lambda acc, titles, cfg, limit: None)
    account = AccountRecord(name="Acme", account_type="company", website="https://acme.test", domain="acme.test",
                            trigger_event=TriggerEvent(event="Hiring a clinic manager", signal_type="hiring_post",
                                                       source="https://news.test/acme"))
    ad.collect_socials_and_emails({"accounts": AccountList(accounts=[account]), "account_discovery_docs": [],
                                   "icp_data": ICP(buyer_type="b2b", industries=["Clinics"])})
    return searched, email_queries, account


def test_social_lookups_stop_at_the_budget_but_emails_are_still_found(monkeypatch):
    searched, email_queries, account = _run(monkeypatch, budget_s=-1)
    assert searched == [] and email_queries
    assert [c.email for c in account.key_contacts] == ["info@acme.test"]


def test_within_the_budget_linkedin_is_looked_up(monkeypatch):
    searched, _, _ = _run(monkeypatch, budget_s=60)
    assert searched == ['"Acme" site:linkedin.com/company acme.test']
