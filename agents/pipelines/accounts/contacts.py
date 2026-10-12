"""Make every target account reachable: find the people and addresses to
contact, in priority order, and check that emails can actually be delivered.

Priority: a named person's email, then a named person's LinkedIn, then the
organisation's email, then its social pages. Sources, cheapest first: the
account's own contact/about/team pages, then a people search on LinkedIn for
the ICP's buyer titles. Nothing is invented: every contact comes from a page
that names it.
"""

from __future__ import annotations

import re
from functools import lru_cache
from urllib.parse import urljoin

import dns.exception
import dns.resolver

from agents.pipelines.web_utils import call_with_timeout
from agents.schemas.accounts import AccountRecord, ContactRecord
from config import Settings
from data_sources.scraping.exa import scrape_url, search_and_scrape
from utils.log import logger

EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
_PERSON_LINKEDIN_RE = re.compile(r"https?://(?:[a-z]{2,3}\.)?linkedin\.com/in/[A-Za-z0-9_%-]+/?", re.I)
# Pages where organisations publish who to contact.
_CONTACT_PATHS = ("contact", "contact-us", "about", "about-us", "team", "our-team")
_PAGE_CHARS = 20_000
_PAGE_TIMEOUT_S = 20
_PEOPLE_RESULTS = 5
_PEOPLE_TITLES = 3
_SEARCH_TIMEOUT_S = 20
_DNS_TIMEOUT_S = 5.0
# Addresses that never reach a person.
_NO_REPLY = ("noreply", "no-reply", "donotreply", "mailer-daemon", "postmaster", "abuse", "privacy", "gdpr")
_ASSET_SUFFIX = re.compile(r"\.(png|jpe?g|gif|svg|webp)$", re.I)
GENERIC_LOCALS = ("hello", "info", "sales", "contact", "support", "team", "office", "admin", "enquiries", "inquiries")


@lru_cache(maxsize=1024)
def accepts_mail(domain: str) -> bool:
    """Whether the domain publishes a mail server (MX, or an A record as the
    RFC 5321 fallback). A free check that keeps dead addresses out of drafts,
    since bounces hurt the sender's reputation."""
    resolver = dns.resolver.Resolver()
    resolver.lifetime = _DNS_TIMEOUT_S
    for record in ("MX", "A"):
        try:
            if resolver.resolve(domain, record):
                return True
        except (dns.resolver.NXDOMAIN, dns.resolver.NoAnswer, dns.resolver.NoNameservers):
            continue
        except dns.exception.Timeout:
            logger.info("MX lookup for %s timed out; keeping its addresses", domain)
            return True  # unknown is not evidence of a dead domain
    return False


def deliverable(email: str) -> bool:
    local, _, domain = email.lower().partition("@")
    if not domain or local.startswith(_NO_REPLY) or _ASSET_SUFFIX.search(email):
        return False
    return accepts_mail(domain)


def _belongs(email: str, domain: str | None) -> bool:
    host = email.lower().rsplit("@", 1)[-1]
    return not domain or host == domain or host.endswith("." + domain)


def _site_pages(acc: AccountRecord, cfg: Settings) -> list[str]:
    if not acc.website:
        return []
    base = acc.website if acc.website.endswith("/") else acc.website + "/"
    pages = []
    for url in [acc.website, *(urljoin(base, path) for path in _CONTACT_PATHS)]:
        text = call_with_timeout(lambda u=url: scrape_url(u, cfg), _PAGE_TIMEOUT_S, default="",
                                 label=f"contact_page[{url}]") or ""
        if text.strip():
            pages.append(text[:_PAGE_CHARS])
    return pages


def from_site(acc: AccountRecord, cfg: Settings) -> list[ContactRecord]:
    """Emails and people's LinkedIn URLs published on the account's own site."""
    found: list[ContactRecord] = []
    for text in _site_pages(acc, cfg):
        for email in dict.fromkeys(e.lower() for e in EMAIL_RE.findall(text)):
            if _belongs(email, acc.domain):
                found.append(ContactRecord(email=email))
        for url in dict.fromkeys(_PERSON_LINKEDIN_RE.findall(text)):
            found.append(ContactRecord(linkedin=url))
    return found


def _person_from_result(title: str, company: str) -> tuple[str | None, str | None]:
    """'Jane Doe - Head of Growth - Acme | LinkedIn' -> (name, title) when the
    result is about someone at `company`."""
    head = title.split("|")[0]
    parts = [p.strip() for p in re.split(r"\s[-–—]\s", head) if p.strip()]
    if len(parts) < 2 or company.lower() not in head.lower():
        return None, None
    role = parts[1] if company.lower() not in parts[1].lower() else None
    return parts[0], role


def people_on_linkedin(acc: AccountRecord, titles: list[str], cfg: Settings) -> list[ContactRecord]:
    """Named decision makers at the account, from a LinkedIn people search
    for the ICP's buyer titles. Only results naming the account are kept."""
    if not acc.name:
        return []
    wanted = " OR ".join(f'"{t}"' for t in titles[:_PEOPLE_TITLES]) or "founder OR CEO OR head"
    query = f'site:linkedin.com/in "{acc.name}" {wanted}'
    hits = call_with_timeout(lambda: search_and_scrape(query, cfg, num_results=_PEOPLE_RESULTS),
                             _SEARCH_TIMEOUT_S, default=[], label=f"people[{acc.name}]") or []
    people = []
    for hit in hits:
        url = (_PERSON_LINKEDIN_RE.search(hit.get("url") or "") or [None])[0]
        name, role = _person_from_result(hit.get("title") or "", acc.name)
        if url and name:
            people.append(ContactRecord(name=name, title=role, linkedin=url))
    return people


def _rank(contact: ContactRecord) -> int:
    named = bool(contact.name)
    if contact.email and named:
        return 0
    if contact.linkedin and named:
        return 1
    if contact.email:
        return 2 if not contact.email.split("@")[0].startswith(GENERIC_LOCALS) else 3
    return 4


def merge(existing: list[ContactRecord], found: list[ContactRecord], limit: int) -> list[ContactRecord]:
    """Existing contacts plus new ones, de-duplicated by email and LinkedIn,
    undeliverable emails dropped, best first."""
    merged: list[ContactRecord] = []
    seen: set[str] = set()
    for contact in [*existing, *found]:
        keys = {k for k in ((contact.email or "").lower(), (contact.linkedin or "").lower().rstrip("/")) if k}
        if not keys or keys & seen:
            continue
        if contact.email and not deliverable(contact.email):
            logger.info("Dropping undeliverable address %s", contact.email)
            contact = contact.model_copy(update={"email": None})
            if not (contact.linkedin or contact.name):
                continue
        seen |= keys
        merged.append(contact)
    return sorted(merged, key=_rank)[:limit]


def complete(acc: AccountRecord, buyer_titles: list[str], cfg: Settings, limit: int) -> None:
    """Fill in the account's contacts until it has a named person, searching
    its own site first and LinkedIn second."""
    def has_person() -> bool:
        return any(c.name and (c.email or c.linkedin) for c in acc.key_contacts)

    if not has_person() or not any(c.email for c in acc.key_contacts):
        acc.key_contacts = merge(acc.key_contacts, from_site(acc, cfg), limit)
    if not has_person():
        acc.key_contacts = merge(acc.key_contacts, people_on_linkedin(acc, buyer_titles, cfg), limit)
    else:
        acc.key_contacts = merge(acc.key_contacts, [], limit)


def reachable(acc: AccountRecord) -> bool:
    return any(c.email or c.linkedin for c in acc.key_contacts) or bool(acc.socials)
