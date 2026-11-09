"""Learning a customer from its own site: what it is, as a sourced fact;
an unreadable or empty site gives nothing, never a guess."""

from agents.lace.customers import customer_fact, describe_customer
from agents.schemas.icp import CustomerTraits
from config import get_settings
from data_sources.scraping.firecrawl import FirecrawlError

TRAITS = CustomerTraits(what_they_do="Runs a chain of clinics.", industry="Healthcare", size="12 sites",
                        location="Nairobi, Kenya")


def test_a_customer_is_described_from_its_own_page():
    seen = {}

    def read(url, cfg):
        seen["url"] = url
        return "# Acme Clinics\nTwelve clinics across Nairobi."

    def describe(messages):
        seen["prompt"] = messages[0].content
        return TRAITS
    assert describe_customer("Acme Clinics", "https://acme.test", "Payline", get_settings(), read, describe) == TRAITS
    assert seen["url"] == "https://acme.test" and "Twelve clinics across Nairobi" in seen["prompt"]
    assert "a customer of Payline" in seen["prompt"] and "never guess" in seen["prompt"]


def test_an_unreadable_or_empty_site_gives_nothing():
    def unreadable(url, cfg):
        raise FirecrawlError("blocked")
    assert describe_customer("A", "https://a.test", "P", get_settings(), unreadable, lambda m: TRAITS) is None
    assert describe_customer("A", "https://a.test", "P", get_settings(), lambda u, c: "  ", lambda m: TRAITS) is None
    assert describe_customer("A", "https://a.test", "P", get_settings(), lambda u, c: "page",
                             lambda m: CustomerTraits()) is None


def test_the_fact_names_the_customer_and_its_source():
    fact = customer_fact("Acme Clinics", "https://acme.test", TRAITS)
    assert (fact.topic, fact.source_url, fact.origin) == ("customers", "https://acme.test", "research")
    assert fact.claim == "Customer Acme Clinics: Runs a chain of clinics (Healthcare, 12 sites, Nairobi, Kenya)."
