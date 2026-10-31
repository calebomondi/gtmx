"""Mzalendo's Bill Tracker (mzalendo.com): where each bill before Kenya's
National Assembly and Senate stands, from Parliament's own record.

Each bill is a row whose track marks the current one of five stages, so its
stage is read from the markup rather than the free-text label."""

import re
from dataclasses import dataclass
from html.parser import HTMLParser

import httpx

from agents.schemas.regulations import BillStage
from utils.log import logger

BASE_URL = "https://mzalendo.com"
TRACKER_PATH = "/legislative-trends/bills/"
HOUSES = {"National Assembly": "na", "Senate": "senate"}
# Each house's list is paged, the current session first.
MAX_PAGES = 6
REQUEST_TIMEOUT_S = 20.0
USER_AGENT = "ThalaceBot/1.0 (+https://thalace.com)"

# The track's segments, in order.
STAGES: dict[str, BillStage] = {
    "First Reading": "first_reading", "Second Reading": "second_reading",
    "Committee of the Whole House": "whole_house", "Third Reading": "third_reading",
    "Presidential Assent": "assented",
}
_NOISE = re.compile(r"^(senate|national assembly) bill no\.? \d+ of \d{4}\s*-\s*|^the\s+|[^a-z0-9 ]")
_YEAR = re.compile(r",?\s*(\d{4})\.?\s*$")


class MzalendoError(Exception):
    """Mzalendo could not be read: down, slow, or its page changed shape."""


@dataclass(frozen=True)
class BillStatus:
    title: str
    year: int | None
    house: str
    stage: BillStage
    url: str


def bill_key(title: str, year: int | None = None) -> tuple[str, int | None]:
    """A bill's identity across sources: its name without "The", punctuation
    or a "Senate Bill No. x of y -" prefix, and its year (from the title when
    it ends with one)."""
    found = _YEAR.search(title)
    if found:
        year, title = year or int(found[1]), title[:found.start()]
    name = title.lower().strip()
    for _ in range(2):
        name = _NOISE.sub("", name).strip()
    return " ".join(name.split()), year


class _Rows(HTMLParser):
    """Collects each bill row's link, name, year and current stage. Text
    belongs to the innermost span it sits in: the name's own, or its year."""

    def __init__(self) -> None:
        super().__init__()
        self.rows: list[dict] = []
        self._row: dict | None = None
        self._spans: list[list[str]] = []

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        classes = (a.get("class") or "").split()
        if tag == "a" and "bt-row__link" in classes:
            self._row, self._spans = {"href": a.get("href") or "", "name": [], "year": "", "stage": None}, []
        elif self._row is not None and tag == "span":
            self._spans.append(classes)
            if "bt-seg" in classes and "is-current" in classes:
                self._row["stage"] = a.get("title")

    def handle_data(self, data):
        if self._row is None or not self._spans:
            return
        if "bt-row__name" in self._spans[-1]:
            self._row["name"].append(data)
        elif "bt-row__year" in self._spans[-1]:
            self._row["year"] += data

    def handle_endtag(self, tag):
        if self._row is None:
            return
        if tag == "a":
            self.rows.append(self._row)
            self._row = None
        elif tag == "span" and self._spans:
            self._spans.pop()


def parse_tracker(html: str, house: str) -> list[BillStatus]:
    """The bills on one tracker page whose stage is one of the five."""
    parser = _Rows()
    parser.feed(html)
    bills = []
    for row in parser.rows:
        title = " ".join("".join(row["name"]).split())
        stage = STAGES.get(row["stage"] or "")
        if title and stage:
            year = int(row["year"]) if row["year"].strip().isdigit() else None
            bills.append(BillStatus(title=title, year=year, house=house, stage=stage, url=BASE_URL + row["href"]))
    return bills


def bill_stages(houses: list[str], client: httpx.Client | None = None) -> list[BillStatus]:
    """Every bill on the tracker for those houses, page by page until a page
    lists none. Raises MzalendoError when a page can't be read, or the first
    page lists no bills (its layout changed)."""
    own = client is None
    client = client or httpx.Client(timeout=REQUEST_TIMEOUT_S, headers={"User-Agent": USER_AGENT},
                                    follow_redirects=True)
    try:
        bills: list[BillStatus] = []
        for house in houses:
            for page in range(1, MAX_PAGES + 1):
                params = {"house": HOUSES[house], **({"page": page} if page > 1 else {})}
                try:
                    response = client.get(BASE_URL + TRACKER_PATH, params=params)
                    response.raise_for_status()
                except httpx.HTTPError as exc:
                    raise MzalendoError(f"Mzalendo's {house} tracker page {page} could not be read: {exc}") from exc
                found = parse_tracker(response.text, house)
                if not found:
                    if page == 1:
                        raise MzalendoError(f"Mzalendo's {house} tracker listed no bills; its layout may have changed")
                    break
                bills += found
        logger.info("Mzalendo: %d bills from %s", len(bills), ", ".join(houses))
        return bills
    finally:
        if own:
            client.close()
