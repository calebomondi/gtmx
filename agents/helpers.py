from utils.log import logger
from agents.schemas.offer import FollowUp, OfferDataSnapshot
from .context_budget import offer_brief

import re

from data_sources.scraping.quality import decode_entities

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
    scope = (
        f"SCOPE: this material is about {name} only. The same company may sell other products or "
        f"services; anything about them is out of scope -- never attribute their features, claims or "
        f"numbers to {name}."
    )
    return f'<Document href="{href}"/>\n{name} — {noun}\'s own material\n{scope}\n-----\n{body}\n</Document>'


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


def with_target_geo(chosen: list[str] | None, found: list[str] | None) -> list[str]:
    """The user's target countries, always, plus any further markets the
    evidence adds. A stage may widen the market; it may not drop a country the
    user asked for."""
    out = [g for g in (chosen or []) if g]
    seen = {g.lower() for g in out}
    return out + [g for g in (found or []) if g and g.lower() not in seen]


# Words that carry no identifying signal in an offer name. Dropping them is what makes
# "&" and "and" interchangeable: "Engineering and Innovation Consultancy" and
# "Engineering & Innovation Consultancy" reduce to the same significant tokens, so
# neither can fail to match the other on punctuation alone.
_NAME_STOPWORDS = frozenset({
    "and", "the", "of", "for", "a", "an", "to", "in", "on", "with", "or", "at", "by",
})

# Fraction of significant tokens that must be present for a multi-word name to match.
# Most of the name has to be there. 3/3 and 4/5 pass; 2/3 does not. The gap matters:
# a descriptive phrase like "quantum blockchain consulting" scores 2/3 purely on
# generic domain vocabulary, and treating that as a confirmed NAME is wrong — it
# should fall through to be handled as a description instead. A genuinely wrong
# company scores 0 either way, so the loose cases cost nothing to reject.
_NAME_MATCH_THRESHOLD = 0.7

# Minimum shared prefix for treating two words as the same word inflected differently.
# Long enough that "man"/"many" cannot collide, short enough to bridge the regular
# English derivational pairs that show up in service names: manufacture/manufacturing,
# consult/consultancy, design/designer.
_STEM_PREFIX = 6

_WORD_SPLIT_RE = re.compile(r"[^a-z0-9]+")


def _name_tokens(name: str) -> list[str]:
    """Significant lowercase tokens of an offer name, stopwords removed."""
    return [t for t in _WORD_SPLIT_RE.split(name.lower()) if t and t not in _NAME_STOPWORDS]


def name_in_text(name: str, content: str) -> bool:
    """Is this name (an offer's, or an account's) present in the text?

    Originally a single substring test against the name with all non-alphanumerics
    stripped. That is brittle in two ways that both bite on real pages:

      * "&" is stripped to nothing while "and" survives, so the SAME service name
        typed either way produced different keys and could never match the other.
        Verified: "Engineering and Innovation Consultancy" failed against a page
        listing "Engineering & Innovation Consultancy" — which is literally Service
        01 on that site.
      * it also depended on whether Exa returned HTML-escaped or decoded text, so
        "&amp;" vs "&" silently flipped the verdict.

    So: decode entities first, then score token overlap. Tokens also match on a shared
    >=6-char prefix, so a user typing "manufacturing" still matches a page saying
    "manufacture". An all-stopword name ("The Company") falls back to the old
    substring test rather than matching everything.
    """
    if not name or not content:
        return False

    haystack = decode_entities(content).lower()
    tokens = _name_tokens(name)
    if not tokens:
        norm = lambda s: re.sub(r"[^a-z0-9]", "", s.lower())
        return norm(name) in norm(haystack)

    words = set(_WORD_SPLIT_RE.split(haystack))

    def matches(token: str) -> bool:
        if token in haystack:
            return True
        stem = token[:_STEM_PREFIX]
        if len(stem) < _STEM_PREFIX:
            return False
        return any(w.startswith(stem) for w in words if len(w) >= _STEM_PREFIX)

    present = sum(1 for t in tokens if matches(t))
    if present == len(tokens):
        return True
    return present / len(tokens) >= _NAME_MATCH_THRESHOLD
