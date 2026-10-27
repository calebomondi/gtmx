"""Which URLs can be a company's own website."""

import pytest

from agents.pipelines.web_utils import is_own_site, site_host


@pytest.mark.parametrize("url", ["https://acme.co.ke", "www.acme.com/about", "https://dropbox.com", "http://shop.acme.io"])
def test_a_company_site_is_its_own(url):
    assert is_own_site(url)


@pytest.mark.parametrize("url", [
    "https://www.brightermonday.co.ke/listings/sourcing-procurement-officer-x8jp82",
    "https://ke.linkedin.com/company/acme", "https://x.com/acme", "https://www.glassdoor.co.uk/acme", "",
])
def test_a_listing_profile_or_nothing_is_not(url):
    assert not is_own_site(url)


def test_the_host_drops_www_and_ports():
    assert site_host("https://WWW.Acme.com:8443/x") == "acme.com"
