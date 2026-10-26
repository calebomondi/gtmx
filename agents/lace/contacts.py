"""Making a Lace's target accounts reachable: the people to contact, and the
organisation's own channels.

People come from v1's contact search (pipelines/accounts/contacts): the
account's own contact, about and team pages, then a LinkedIn search for the
ICP's buyer titles, every email checked for a mail server. Organisation pages
are filled in for each channel discovery left empty, Facebook included: a
search result counts only when its URL is that platform's profile shape and
its title names the account. Nothing is invented; an account nobody could be
found for says so.
"""

import re
from collections.abc import Callable
from functools import lru_cache

import pycountry

from agents.helpers import name_in_text
from agents.pipelines.accounts import contacts as v1_contacts
from agents.pipelines.web_utils import call_with_timeout
from agents.schemas.accounts import AccountRecord
from agents.schemas.lace import ContactStatus
from config import Settings
from data_sources.scraping import exa
from utils.log import logger

# The organisation's channels, beside a person's email and LinkedIn.
SOCIAL_CHANNELS = ("linkedin", "instagram", "tiktok", "facebook", "x")
CONTACTS_PER_ACCOUNT = 5
_PAGE_RESULTS = 5
_SEARCH_TIMEOUT_S = 20

# A platform's profile URL, not a post, share link or search page.
_PROFILE = {
    "linkedin": re.compile(r"^https?://([a-z]{2,3}\.)?linkedin\.com/company/[^/?#]+/?$", re.I),
    "instagram": re.compile(r"^https?://(www\.)?instagram\.com/(?!p/|reel/|explore/)[A-Za-z0-9_.]+/?$", re.I),
    "tiktok": re.compile(r"^https?://(www\.)?tiktok\.com/@[A-Za-z0-9_.]+/?$", re.I),
    "facebook": re.compile(r"^https?://(www\.|m\.)?facebook\.com/(?!sharer|share|groups/|events/|watch|search)"
                           r"[A-Za-z0-9.\-]+/?$", re.I),
    "x": re.compile(r"^https?://(www\.)?(x|twitter)\.com/(?!intent/|share|search|hashtag/)[A-Za-z0-9_]+/?$", re.I),
}
_SITE = {"linkedin": "linkedin.com/company", "instagram": "instagram.com", "tiktok": "tiktok.com",
         "facebook": "facebook.com", "x": "x.com"}

# The search step, injectable so tests can script it: (query, cfg) -> results.
Search = Callable[[str, Settings], list[dict]]
# v1's people search, injectable likewise: (record, buyer titles, cfg, limit) -> None.
Complete = Callable[[AccountRecord, list[str], Settings, int], None]


def _default_search(query: str, cfg: Settings) -> list[dict]:
    return call_with_timeout(lambda: exa.search_highlights(query, cfg, search_type="fast", num_results=_PAGE_RESULTS),
                             _SEARCH_TIMEOUT_S, default=[], label=f"org_page[{query}]") or []


def org_page(record: AccountRecord, platform: str, cfg: Settings, search: Search = _default_search) -> str | None:
    """The account's own page on `platform`, or None when no result is clearly
    it. Searched with the account's country first, so a same-named firm
    elsewhere does not take its place; without it only if that finds nothing."""
    query = f'"{record.name}" site:{_SITE[platform]}'
    for q in ([f'{query} "{record.geo}"', query] if record.geo else [query]):
        for hit in search(q, cfg):
            url, title = (hit.get("url") or "").split("?")[0], hit.get("title") or ""
            if _PROFILE[platform].match(url) and name_in_text(record.name, title) \
                    and not _elsewhere(url, record.geo):
                return url
    return None


_LINKEDIN_COUNTRY = re.compile(r"^https?://([a-z]{2})\.linkedin\.com/", re.I)


@lru_cache(maxsize=256)
def _country_code(geo: str) -> str | None:
    try:
        return pycountry.countries.lookup(geo.strip()).alpha_2.lower()
    except LookupError:
        return None  # a region ("East Africa") or a city: nothing to compare


def _elsewhere(url: str, geo: str | None) -> bool:
    """A LinkedIn page localised to another country than the account's
    (vn.linkedin.com for a Kenyan firm): a same-named company elsewhere."""
    match = _LINKEDIN_COUNTRY.match(url)
    code = _country_code(geo) if geo else None
    return bool(match and code and match.group(1).lower() != code)


def contact_status(record: AccountRecord) -> ContactStatus:
    """person: a named person reachable by email, LinkedIn or their own
    social accounts. organisation: only the organisation's own channels.
    none: nothing to reach them on."""
    if any(c.name and c.addresses() for c in record.key_contacts):
        return "person"
    if any(c.addresses() for c in record.key_contacts) or record.socials:
        return "organisation"
    return "none"


def complete_contacts(record: AccountRecord, buyer_titles: list[str], cfg: Settings,
                      complete: Complete = v1_contacts.complete, search: Search = _default_search) -> AccountRecord:
    """The record with its people and organisation pages filled in as far as
    the sources allow. A copy: the caller's record is untouched."""
    out = record.model_copy(deep=True)
    try:
        complete(out, buyer_titles, cfg, CONTACTS_PER_ACCOUNT)
    except Exception:  # noqa: BLE001 -- the organisation's pages are still worth finding
        logger.exception("People search for %s failed", record.name)
    socials = dict(out.socials or {})
    for platform in SOCIAL_CHANNELS:
        if not socials.get(platform):
            page = org_page(out, platform, cfg, search)
            if page:
                socials[platform] = page
    out.socials = socials
    return out
