from langchain.messages import HumanMessage

from utils.log import logger
from .states import OfferDataSnapshot, FollowUp, IndepthIntakeStep, IntakeStep, MarketExtraction, CompetitionExtraction, ICP
from .sub_graphs.gather_context import gather_context_graph
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


def market_context_block(market_data: MarketExtraction | None) -> str:
    """Render the market understanding so the GTM specialist can scope the ICP."""
    if not market_data:
        return "No market data available — scope to the offer/category alone."
    return market_data.model_dump_json(indent=2, exclude_none=True)


def competition_context_block(competition_data: CompetitionExtraction | None) -> str:
    """Render the offer-vs-standard SWOD so the GTM specialist has the
    competitive context behind its competitor leads (accounts/audiences
    evaluating or using competitors are prime targets).

    The named competitor list this used to render is gone from
    CompetitionExtraction — the stage now emits archetypes, and real rivals come
    from the standalone get_competitors agent. Named leads still reach the GTM
    specialist through the competition FINDINGS prose, which retained the rivals
    the research actually named.
    """
    if not competition_data:
        return "No competition data available."
    return competition_data.model_dump_json(indent=2, exclude_none=True)


def icp_block(icp: ICP | None) -> str:
    return icp.model_dump_json(indent=2, exclude_none=True) if icp else "No ICP available."

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


def merge_snapshot(snapshot: OfferDataSnapshot, step: IndepthIntakeStep | IntakeStep | MarketExtraction) -> OfferDataSnapshot:
    updates = step.model_dump(exclude_none=True, exclude={"follow_up_question"})
    fill = {}
    for field, value in updates.items():
        if not hasattr(snapshot, field):
            # Extraction-only fields (pricing_source, market_fit_reasoning, ...)
            # feed the report, not the profile schema — skip them.
            continue
        value = normalize_optional_text(value)
        if value is None:
            continue
        current = getattr(snapshot, field)
        if current in (None, "", [], {}) and value not in (None, "", [], {}):
            fill[field] = value
    return (
        OfferDataSnapshot.model_validate({
            **snapshot.model_dump(),
            **fill,
        })
        if fill
        else snapshot
    )


_URL_RE = re.compile(r"^\s*(https?://)", re.IGNORECASE)


def gather_content(source: str) -> str:
    """Scrape/parse the source, returning "" on any failure so the agent can
    fall back to asking the user instead of crashing on a dead URL.

    Plain URLs are scraped deterministically (exactly as provided — the model is
    never allowed to pick or rewrite the URL, so it can't append paths or jump to
    subpages). Non-URL sources (documents) go through the gather_context graph.

    A body that comes back but is a placeholder ("Coming Soon", "under construction")
    is treated as a FAILURE, not content. `scrape_website` only tests the scraped text
    for emptiness, so boilerplate would otherwise sail through, the run would proceed
    on it, and the workspace would report `confirmed: True` having learned nothing.
    Returning "" routes it to `notify_unscrappable_url` instead, which asks the user —
    the loud failure this used to skip."""
    try:
        if _URL_RE.match(source.strip()):
            from config import Config
            from data_sources.scraping.exa import scrape_url as _scrape_url
            from data_sources.scraping.quality import is_usable_body, rejection_reason
            raw = _scrape_url(source.strip(), Config())
            if not is_usable_body(raw):
                logger.warning(
                    "Rejected unusable body for %r: %s", source.strip(), rejection_reason(raw)
                )
                return ""
            if raw.strip():
                return raw
            return ""
        gather_result = gather_context_graph().invoke({
            "messages": [HumanMessage(content=source)]
        })
        raw = gather_result["messages"][-1].content
        if raw.strip() and raw.strip() != "No content to gather.":
            return raw
    except Exception as e:
        logger.warning("Gather failed for source %r: %s", source, e)
    return ""