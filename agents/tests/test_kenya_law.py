"""Kenya Law's bills listing: each bill's title, chamber and date come from its link."""

from datetime import date

import httpx
import pytest

from data_sources.legislation.kenya_law import Bill, KenyaLawError, parse_bills, recent_bills

PAGE = """<table><tr><td><div>
  <a href="/akn/ke/bill/na/2026-09-28/the-tax-laws-amendment-bill-2026/eng@2026-09-28"
     data-key-link="document">The Tax Laws (Amendment) Bill, 2026</a></div></td></tr>
<tr><td><div><a href="/akn/ke/bill/senate/2026-09-22/the-social-protection-amendment-bill-2026/eng@2026-09-22"
     data-key-link="document">The Social Protection
     (Amendment) Bill, 2026</a></div></td></tr>
<tr><td><a href="/akn/ke/act/2019/24">The Data Protection Act, 2019</a></td></tr></table>"""


def test_bills_are_read_from_their_links():
    assert parse_bills(PAGE) == [
        Bill(title="The Tax Laws (Amendment) Bill, 2026",
             url="https://kenyalaw.org/akn/ke/bill/na/2026-09-28/the-tax-laws-amendment-bill-2026/eng@2026-09-28",
             chamber="National Assembly", published=date(2026, 9, 28)),
        Bill(title="The Social Protection (Amendment) Bill, 2026",
             url="https://kenyalaw.org/akn/ke/bill/senate/2026-09-22/the-social-protection-amendment-bill-2026/eng@2026-09-22",
             chamber="Senate", published=date(2026, 9, 22)),
    ]


def test_a_page_without_bills_means_its_layout_changed():
    with pytest.raises(KenyaLawError, match="layout"):
        parse_bills("<html><body>Maintenance</body></html>")


def test_pages_are_read_in_turn_without_repeats():
    asked = []

    def handler(request: httpx.Request) -> httpx.Response:
        asked.append(request.url.params.get("page"))
        return httpx.Response(200, text=PAGE)

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        bills = recent_bills(pages=2, client=client)
    assert asked == [None, "2"] and len(bills) == 2


def test_an_unreachable_site_is_a_kenya_law_error():
    with httpx.Client(transport=httpx.MockTransport(lambda r: httpx.Response(503))) as client:
        with pytest.raises(KenyaLawError, match="page 1"):
            recent_bills(pages=1, client=client)


@pytest.mark.live
def test_the_live_listing_still_parses():
    bills = recent_bills(pages=1)
    assert len(bills) >= 10 and all(b.url.startswith("https://kenyalaw.org/akn/ke/bill/") for b in bills)
