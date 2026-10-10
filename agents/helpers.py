from utils.log import logger
from agents.schemas.offer import FollowUp, OfferDataSnapshot
from .context_budget import offer_brief

import re

def as_offer_snapshot(value):
    if value is None:
        return OfferDataSnapshot()
    if isinstance(value, dict):
        return OfferDataSnapshot(**value)
    return value

def as_follow_up(value):
    if value is None:
        return FollowUp()
    if isinstance(value, dict):
        return FollowUp(**value)
    return value


PLACEHOLDER_VALUES = {
    "", "none", "null", "nil", "na", "n/a", "unknown",
    "not provided", "not available", "not given", "no info",
    "no information", "no information provided", "no data",
    "no description", "no description provided", "no description available",
    "no info", "no information", "no information provided", "no information available",
    "no data", "no draft yet",
    "no product information", "no product information provided",
}

# Catches free-form filler the LLM invents instead of returning None, e.g.
# "No product description provided." / "No draft yet." — short, starts with
# 'no', ends with provided/available/given/found/yet.
_PLACEHOLDER_RE = re.compile(
    r"^no\b.*\b(not\s+)?(provided|available|given|found|yet)\b\.?$",
    re.IGNORECASE,
)


def normalize_optional_text(value):
    if value is None:
        return None
    if isinstance(value, str):
        cleaned = value.strip()
        probe = cleaned.rstrip(".!?,;:")
        if probe.lower() in PLACEHOLDER_VALUES:
            return None
        if len(probe) <= 80 and _PLACEHOLDER_RE.match(probe.strip()):
            return None
        return cleaned
    return value

def format_offer_material(snapshot: OfferDataSnapshot, scraped_content: str | None = None, offer_type: str | None = None) -> str:
    """Render the offer's own content into one context block so an interview
    expert / section writer treats the offer itself as authoritative ground
    truth rather than relying only on domain search docs.

    Prefers the raw scraped content collected during discovery; falls back to a
    compact brief derived from the offer snapshot when none is available.
    """
    offer = as_offer_snapshot(snapshot)
    noun = "service" if offer_type == "service" else "product"
    name = offer.offer_name or f"Unknown {noun}"
    url = offer.website_url or None

    if scraped_content and scraped_content.strip():
        body = scraped_content.strip()
    else:
        parts = []
        if offer.offer_description:
            parts.append(f"Description: {offer.offer_description}")
        if offer.intent:
            parts.append(f"Intent: {offer.intent}")
        if offer.problem_solved:
            parts.append(f"Problem solved: {offer.problem_solved}")
        if offer.how_it_works:
            parts.append(f"How it works: {offer.how_it_works}")
        for f in offer.features:
            detail = ", ".join(
                x for x in (f.description or "", f.differentiator or "") if x
            )
            flag = (f.name or "Feature").strip()
            parts.append(f"Feature {flag}: {detail}" if detail else f"Feature {flag}")
        for f in offer.service_uniqueness:
            detail = ", ".join(
                x for x in (f.description or "", f.differentiator or "") if x
            )
            flag = (f.name or "Service element").strip()
            parts.append(f"Service element {flag}: {detail}" if detail else f"Service element {flag}")
        if offer.target_geo:
            parts.append(f"Target markets: {', '.join(offer.target_geo)}")
        body = "\n".join(parts)

    if not body:
        return ""

    # The scrape spans subpages and is never truncated at gather time, so it is
    # routinely tens of thousands of tokens and gets quoted at several prompt
    # sites per interview turn. Condense it once; the result is memoised.
    body = offer_brief(name, body)

    href = url or f"{name} (user-provided material)"
    return f'<Document href="{href}"/>\n{name} — {noun}\'s own material\n-----\n{body}\n</Document>'


_URL_RE = re.compile(r"^\s*(https?://)", re.IGNORECASE)


def gather_content(source: str) -> str:
    """Scrape the offer's website, returning "" on any failure so the agent can
    fall back to asking the user instead of crashing on a dead URL.

    The URL is scraped deterministically, exactly as provided -- the model never
    picks or rewrites it, so it can't append paths or jump to subpages. A bare
    host (an LLM-drafted "linear.app") gets https:// rather than being rejected.

    A body that comes back but is a placeholder ("Coming Soon", "under
    construction") is treated as a FAILURE, not content: the run would otherwise
    proceed on boilerplate and report `confirmed: True` having learned nothing.
    Returning "" routes it to `notify_unscrappable_url`, which asks the user."""
    from config import get_settings
    from data_sources.scraping.exa import scrape_url
    from data_sources.scraping.quality import is_usable_body, rejection_reason

    url = source.strip()
    if not url:
        return ""
    if not _URL_RE.match(url):
        url = f"https://{url}"
    try:
        raw = scrape_url(url, get_settings())
    except Exception as e:
        logger.warning("Scrape failed for %r: %s", url, e)
        return ""
    if not is_usable_body(raw):
        logger.warning("Rejected unusable body for %r: %s", url, rejection_reason(raw))
        return ""
    return raw
