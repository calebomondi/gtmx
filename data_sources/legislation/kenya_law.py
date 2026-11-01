"""Kenya Law (kenyalaw.org): the bills published for Parliament.

Each bill is an Akoma Ntoso work whose link carries its chamber and date
(/akn/ke/bill/<na|senate>/<YYYY-MM-DD>/<slug>/eng@<date>), so the listing
alone gives what a bill is, where and when, without opening it."""

import re
from dataclasses import dataclass
from datetime import date
from html.parser import HTMLParser

import httpx

from utils.log import logger

BASE_URL = "https://kenyalaw.org"
BILLS_PATH = "/bills/"
# The listing is newest first, about 50 bills a page.
DEFAULT_PAGES = 2
REQUEST_TIMEOUT_S = 20.0
USER_AGENT = "ThalaceBot/1.0 (+https://thalace.com)"
CHAMBERS = {"na": "National Assembly", "senate": "Senate"}

_BILL_LINK = re.compile(r"^/akn/ke/bill/(?P<chamber>na|senate)/(?P<date>\d{4}-\d{2}-\d{2})/")


class KenyaLawError(Exception):
    """Kenya Law could not be read: down, slow, or its page changed shape."""


@dataclass(frozen=True)
class Bill:
    title: str
    url: str
    chamber: str
    published: date


class _BillLinks(HTMLParser):
    """Collects (href, text) for every bill link on a listing page."""

    def __init__(self) -> None:
        super().__init__()
        self.links: list[tuple[str, str]] = []
        self._href: str | None = None
        self._text: list[str] = []

    def handle_starttag(self, tag, attrs):
        href = dict(attrs).get("href") or ""
        if tag == "a" and _BILL_LINK.match(href):
            self._href, self._text = href, []

    def handle_data(self, data):
        if self._href is not None:
            self._text.append(data)

    def handle_endtag(self, tag):
        if tag == "a" and self._href is not None:
            self.links.append((self._href, " ".join("".join(self._text).split())))
            self._href = None


def parse_bills(html: str) -> list[Bill]:
    """The bills on one listing page, in its order. Raises KenyaLawError when
    the page has none, which means its shape changed."""
    parser = _BillLinks()
    parser.feed(html)
    bills = []
    for href, title in parser.links:
        found = _BILL_LINK.match(href)
        if found and title:
            bills.append(Bill(title=title, url=BASE_URL + href, chamber=CHAMBERS[found["chamber"]],
                              published=date.fromisoformat(found["date"])))
    if not bills:
        raise KenyaLawError("Kenya Law's bills page listed no bills; its layout may have changed")
    return bills


def recent_bills(pages: int = DEFAULT_PAGES, client: httpx.Client | None = None) -> list[Bill]:
    """The newest bills, newest first, from the first `pages` listing pages."""
    own = client is None
    client = client or httpx.Client(timeout=REQUEST_TIMEOUT_S, headers={"User-Agent": USER_AGENT},
                                    follow_redirects=True)
    try:
        bills: list[Bill] = []
        for page in range(1, pages + 1):
            try:
                response = client.get(BASE_URL + BILLS_PATH, params={"page": page} if page > 1 else None)
                response.raise_for_status()
            except httpx.HTTPError as exc:
                raise KenyaLawError(f"Kenya Law's bills page {page} could not be read: {exc}") from exc
            bills += parse_bills(response.text)
        unique = list({b.url: b for b in bills}.values())
        logger.info("Kenya Law: %d bills from %d page(s)", len(unique), pages)
        return unique
    finally:
        if own:
            client.close()
