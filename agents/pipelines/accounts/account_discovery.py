"""Account discovery: surfacing real customers/channels from an ICP context.

This is a standalone helper in `agents/pipelines` that:

1. produces trigger-first search queries from the ICP (and optionally the ideal competitor profile),
2. runs those queries with Exa, recency-gated and deduplicated, and
3. extracts a verified, deduplicated, trigger-signaled account list.

It can be wired into a parent LangGraph or used as a CLI harness.
"""

from __future__ import annotations

import json
from datetime import date, timedelta
from typing import Optional

from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import MemorySaver
from langchain_core.messages import SystemMessage, HumanMessage

from config import Settings, get_settings
from agents.llm.main import invoke_structured_with_fallback, cheap_providers
from agents.schemas.accounts import AccountList, AccountRecord, ContactRecord, TriggerEvent
from agents.schemas.icp import ICP
from agents.schemas.sessions import IcpSessionState
from data_sources.scraping.exa import search_and_scrape
from data_sources.socials import instagram, linkedin, tiktok, x
from utils.log import logger
from agents.pipelines.accounts import contacts
from agents.pipelines.web_utils import (
    call_with_timeout,
    run_parallel,
    search_cache_get,
    search_cache_put,
    timed_node,
)

MAX_QUERY_RESULTS = 4
_SEARCH_TIMEOUT_S = get_settings().account_search_timeout_s
_SCRAPE_TIMEOUT_S = get_settings().account_scrape_timeout_s
_ENRICH_WORKERS = get_settings().account_enrich_workers
_SOCIALS_WORKERS = get_settings().account_socials_workers


def _search_and_scrape(query, config, num_results=5, start_published_date=None):
    """search_and_scrape with a small TTL cache and a hard timeout.

    The module-level `search_and_scrape` is looked up at call time so tests
    can keep patching `account_discovery.search_and_scrape`.
    """
    key = (query, num_results, start_published_date)
    cached = search_cache_get(key)
    if cached is not None:
        return cached
    results = call_with_timeout(
        lambda: search_and_scrape(
            query, config, num_results=num_results, start_published_date=start_published_date
        ),
        _SEARCH_TIMEOUT_S,
        default=[],
        label=f"search[{query}]",
    )
    return search_cache_put(key, results or [])
MAX_ACCOUNT_ROWS = 8
# Extraction over-fetches so accounts dropped for having no contact are
# replaced by the next candidates instead of shrinking the list.
MAX_ACCOUNT_CANDIDATES = 10
MIN_DEFENSIBLE = 4
MAX_ACCOUNT_CONTACTS = 6
MAX_PERSONAL_EMAIL_LOOKUPS = 3

# Test/dev fast mode: shrink query fan-out, socials, and extraction excerpt
# so a live LLM + Exa run completes in ~minutes, not tens of minutes.
_FAST_DISCOVERY = get_settings().account_discovery_fast


def _offer_noun_for(state: IcpSessionState) -> str:
    return "service" if state.get("offer_type") == "service" else "product"


def _recency_cutoff(days: int) -> str:
    """ISO date (YYYY-MM-DD) for the oldest source the account search may use."""
    return (date.today() - timedelta(days=days)).isoformat()


def _geos_for(state: IcpSessionState, icp: Optional[ICP]) -> list[str]:
    geos = list(icp.geo) if icp and icp.geo else (state.get("target_market") or [])
    return geos or ["the target market"]


def _reach_emphasis(icp: Optional[ICP]) -> str:
    buyer_type = (icp.buyer_type or "b2b").lower() if icp else "b2b"
    if buyer_type == "b2c":
        return (
            "This is a CONSUMER offer. The targets are mostly NOT companies — they are the "
            "channels/communities/events/creators/platforms where the ICP congregates (from "
            "`target_channels` and `event_focus`): LinkedIn/Facebook groups, subreddits, Discords, "
            "newsletters, creators, marketplaces, and events/summits/conferences with their "
            "organisers. Find those venues as first-class targets, alongside any direct businesses."
        )
    if buyer_type == "both":
        return (
            "This offer serves BOTH companies and consumers. Find the company targets from the "
            "firmographics AND the consumer-reach venues (channels/communities/events/creators) "
            "from `target_channels` and `event_focus`. Both are first-class targets."
        )
    return (
        "This is a B2B offer. Find real COMPANIES that fit the firmographics; only surface a "
        "channel/event if it clearly concentrates multiple target accounts."
    )


def _trigger_line() -> str:
    return (
        "TRIGGER_SIGNAL_TYPES: hiring_post, competitor_review_mention, payment_integration, "
        "social_growth_spike, community_growth_spike, product_listing, funding_round, event_upcoming."
    )


def create_account_queries(state: IcpSessionState) -> dict:
    """Build trigger-first query families, fan-out per target geography.

    Family mix per geo: direct firmographic, need-signal (hiring/growth),
    competitor-customer pain, and channel/persona reach for consumer offers."""
    icp: Optional[ICP] = state.get("icp_data")
    noun = _offer_noun_for(state)
    offer_label = state.get("offer_name") or noun
    geos = _geos_for(state, icp)
    buyer_type = (icp.buyer_type or "b2b").lower() if icp else "b2b"
    want_b2b = buyer_type in ("b2b", "both")
    want_b2c = buyer_type in ("b2c", "both")

    queries_by_geo: dict[str, list[str]] = {g: [] for g in geos}
    for geo in geos:
        geo_q = queries_by_geo[geo]
        if want_b2b:
            # 1) Direct firmographic: industries + titles in this geo.
            for industry in (icp.industries if icp and icp.industries else [])[:2]:
                geo_q.append(f"{industry} companies in {geo}")
            for title in (icp.buyer_titles if icp and icp.buyer_titles else [])[:1]:
                geo_q.append(f"{title} {geo}")

            # 2) Need signals: hiring / growth / funding imply budget and urgency.
            for pain in (icp.pain_signals if icp else [])[:1]:
                geo_q.append(f"{pain} companies {geo}")
            for kw in (icp.intent_keywords if icp else [])[:1]:
                geo_q.append(f"{kw} {geo}")
            geo_q.append(f"{noun} buyers hiring {geo}")

            # 3) Competitor customers and their pain.
            for comp in (icp.competitor_leads if icp and icp.competitor_leads else [])[:2]:
                geo_q.append(f"{comp.competitor_name} customers {geo}")
                if comp.pain_angles:
                    geo_q.append(f"{comp.competitor_name} {comp.pain_angles[0]} {geo}")

            # 4) Smaller / earlier-stage targets — listicle-sized firms still
            #    get covered if we ask for them by stage, not just by name.
            for industry in (icp.industries if icp and icp.industries else [])[:2]:
                geo_q.append(f"{industry} startups in {geo}")
                geo_q.append(f"small {industry} companies in {geo}")

        if want_b2c:
            # Consumer reach: creators, communities, events — the venues an
            # individual audience already gathers in. Outreach there, not DMs.
            for persona in (icp.buyer_personas if icp and icp.buyer_personas else [])[:2]:
                geo_q.append(f"{persona.name} influencers {geo}")
                for venue in persona.where_they_congregate[:1]:
                    geo_q.append(f"{venue} {geo}")
            for ch in (icp.target_channels if icp and icp.target_channels else [])[:2]:
                geo_q.append(f"{ch.name} {geo}")
            for pain in (icp.pain_signals if icp else [])[:1]:
                geo_q.append(f"{pain} community {geo}")
            geo_q.append(f"{offer_label} users community {geo}")
            # Creators discovered by platform, not just LinkedIn: X, IG, TikTok.
            for kw in (icp.intent_keywords if icp else [])[:2]:
                geo_q.append(f"{kw} instagram {geo}")
                geo_q.append(f"{kw} tiktok {geo}")
                geo_q.append(f"{kw} x.com {geo}")
            for pain in (icp.pain_signals if icp else [])[:1]:
                geo_q.append(f"{pain} instagram {geo}")
            # Events in the offer's topic area, per geo.
            for kw in (icp.intent_keywords if icp else [])[:2]:
                geo_q.append(f"{kw} workshops events {geo} 2026")
                geo_q.append(f"{kw} conference {geo}")

    # Round-robin across geos so neither geo gets crowded out of the cap.
    queries: list[str] = []
    still = True
    while still:
        still = False
        for g in geos:
            if queries_by_geo[g]:
                queries.append(queries_by_geo[g].pop(0))
                still = True

    # Fallback from the ideal competitor profile if the ICP lacks leads.
    if icp and not icp.competitor_leads:
        prof = state.get("ideal_competitor_profile")
        if isinstance(prof, dict):
            for arch in (prof.get("archetypes") or [])[:2]:
                label = arch.get("label") if isinstance(arch, dict) else None
                if label:
                    queries.append(f"{label} companies in {geos[0]}")

    if not queries:
        queries = [f"{noun}s in {g}" for g in geos]

    queries = list(dict.fromkeys(queries))[:8 if _FAST_DISCOVERY else 20]
    print(f"Account discovery queries: {queries}")
    return {"account_discovery_queries": queries}


def search_accounts(state: IcpSessionState) -> dict:
    """Run the queries through Exa, recency-gated, deduplicated by URL."""
    queries = state.get("account_discovery_queries") or []
    if not queries:
        return {"account_discovery_docs": []}
    cfg = get_settings()
    cutoff = _recency_cutoff(cfg.market_recency_days)
    todo = queries[:8 if _FAST_DISCOVERY else 16]
    per_query = run_parallel(
        [
            (lambda q=q: _search_and_scrape(
                q, cfg, num_results=2 if _FAST_DISCOVERY else MAX_QUERY_RESULTS,
                start_published_date=cutoff,
            ))
            for q in todo
        ],
        workers=8,
    )
    docs: list[dict] = []
    seen: set[str] = set()
    for q, results in zip(todo, per_query):
        if not results:
            print(f"  -> empty: {q}")
            continue
        for r in results:
            if r.get("url") and r["url"] not in seen:
                seen.add(r["url"])
                docs.append({"url": r.get("url"), "title": r.get("title"), "text": r.get("text")})
    print(f"search_accounts produced {len(docs)} docs from {len(queries)} queries (after {cutoff})")
    return {"account_discovery_docs": docs}


def extract_accounts(state: IcpSessionState) -> dict:
    icp: Optional[ICP] = state.get("icp_data")
    docs = state.get("account_discovery_docs") or []
    context = "\n\n---\n\n".join(
        f'<Document href="{d["url"]}"/>\n{d.get("title", "")}\n-----\n{d.get("text", "")[:1500]}\n</Document>'
        for d in docs[:6 if _FAST_DISCOVERY else 10]
    )

    system_prompt = (
        "You are an outbound researcher. From the CURRENT web research below, extract the targets "
        f"(the { _offer_noun_for(state) }'s target accounts AND, for consumer offers, its reachable "
        "channels/communities/events/creators/platforms) worth reaching out to.\n\n"
        f"ICP:\n{icp.model_dump_json(indent=2) if icp else 'None'}\n\n"
        f"REACH EMPHASIS\n{_reach_emphasis(icp)}\n\n"
        f"Research context:\n{context or 'No research context available.'}\n\n"
        "Rules:\n"
        f"- Find between 4 and {MAX_ACCOUNT_CANDIDATES} REAL targets that fit the ICP. Each must be grounded "
        "in the research context and MUST have a `trigger_event` — a current, verifiable signal observed "
        "in the sources that makes outreach timely now. If a candidate has no current trigger, exclude it. "
        "Never invent a target, a trigger, or a source. Leave `socials` empty — enrichment fills it.\n"
        f"  {_trigger_line()}\n"
        "- For each target set: name, account_type (company/community/event/creator/platform), "
        "a one-to-two sentence `summary` of what the target does and who it serves (from the sources), "
        "website/domain/industry/geo only as stated. `size` is the company's ACTUAL headcount or revenue "
        "as a source states it (e.g. '120 employees'); never copy one of the ICP's size bands onto an "
        "account, and leave it null when no source states it. platform/venue/event_date/member_size where "
        "stated, key_contacts ONLY when present in the sources, pain_signals/hiring_signals, sources "
        "(URLs proving existence + current trigger), score 0-1 with a short score_breakdown "
        "(ICP fit .30, reach/geo fit .20, pain fit .20, trigger strength .15, defensibility .15), "
        "why_selected (exactly 5 reasons), why_reach_out (exactly 5 angles).\n"
        "- Hard constraints from the ICP must hold: exclude `exclusions`, keep to the ICP's geographies "
        "and, for companies, `company_sizes`.\n\n"
        "Return only the structured fields — no commentary."
    )
    print("Extracting account list from documents...")
    accounts = invoke_structured_with_fallback(
        messages=[
            SystemMessage(content=system_prompt),
            HumanMessage(content="return the structured JSON now"),
        ],
        schema=AccountList,
        log_label="extract_accounts",
        providers=cheap_providers(),
        thinking=False,
    )

    # Empty-result fallback: broad firmographic queries often return listicles
    # with no trigger-carrying targets. One retry aimed at where the ICP's
    # buyers actually congregate before accepting an empty list.
    if not accounts.accounts:
        print("⚠️ extract returned 0 accounts — one fallback round on channels/personas.")
        noun = _offer_noun_for(state)
        geos = _geos_for(state, icp)
        fallback_queries: list[str] = []
        for geo in geos:
            for ch in (icp.target_channels if icp and icp.target_channels else [])[:3]:
                fallback_queries.append(f"{ch.name} {geo}")
            for persona in (icp.buyer_personas if icp and icp.buyer_personas else [])[:2]:
                fallback_queries.append(f"{persona.name} community {geo}")
            for pain in (icp.pain_signals if icp else [])[:1]:
                fallback_queries.append(f"{pain} community {geo}")
            fallback_queries.append(f"{noun} users {geo}")
        fallback_queries = list(dict.fromkeys(fallback_queries))[:4 if _FAST_DISCOVERY else 8]
        cfg = get_settings()
        cutoff = _recency_cutoff(cfg.market_recency_days)
        seen = {d["url"] for d in docs}
        fallback_hits = run_parallel(
            [
                (lambda q=q: _search_and_scrape(
                    q, cfg, num_results=2 if _FAST_DISCOVERY else MAX_QUERY_RESULTS,
                    start_published_date=cutoff,
                ))
                for q in fallback_queries
            ],
            workers=8,
        )
        for results in fallback_hits:
            for r in results or []:
                if r.get("url") and r["url"] not in seen:
                    seen.add(r["url"])
                    docs.append({"url": r.get("url"), "title": r.get("title"), "text": r.get("text")})
        old_context = context
        context = "\n\n---\n\n".join(
            f'<Document href="{d["url"]}"/>\n{d.get("title", "")}\n-----\n{d.get("text", "")[:1500]}\n</Document>'
            for d in docs[:8 if _FAST_DISCOVERY else 12]
        )
        if fallback_queries:
            print(f"Fallback queries: {fallback_queries}")
            system_prompt_fb = system_prompt.replace(
                old_context or "No research context available.", context
            )
            accounts = invoke_structured_with_fallback(
                messages=[
                    SystemMessage(content=system_prompt_fb),
                    HumanMessage(content="return the structured JSON now"),
                ],
                schema=AccountList,
                log_label="extract_accounts_fallback",
                providers=cheap_providers(),
                thinking=False,
            )
    return {"accounts": accounts, "account_discovery_docs": docs}


import re

_EMAIL_RE = contacts.EMAIL_RE
_LINKEDIN_RE = re.compile(r"https?://(?:www\.)?linkedin\.com/(?:in|company)/[^\s\"')]+", re.I)
# Aggregator/directory hosts that should never be picked as an account's own site.
_BAD_HOSTS = ("linkedin.com", "facebook.com", "twitter.com", "x.com", "instagram.com",
              "youtube.com", "exa.ai", "google.com", "glassdoor", "wikipedia.org",
              "crunchbase.com", "bloomberg.com", "africabusiness", "capitalfm", "kbc.co.ke")


def _host_ok(url: str) -> bool:
    u = url.lower()
    return not any(b in u for b in _BAD_HOSTS)


_ASSET_RE = re.compile(r"\.(pdf|docx?|xlsx?|png|jpe?g|gif|svg|zip)(\?|#|$)|/wp-content/uploads/|/uploads/|/media/", re.I)


def _is_homepage_like(url: str) -> bool:
    """Reject asset/deep-link URLs when picking an account's own site."""
    return not _ASSET_RE.search(url.lower())


_LINKEDIN_COMPANY_RE = re.compile(r"https?://(?:[a-z]{2}\.)?linkedin\.com/company/[^\s\"')]+", re.I)
_INSTAGRAM_RE = re.compile(r"https?://(?:www\.)?instagram\.com/[^\s\"')]+/?", re.I)
_TIKTOK_RE = re.compile(r"https?://(?:www\.)?tiktok\.com/@[^\s\"')]+/?", re.I)
_X_RE = re.compile(r"https?://(?:www\.)?x\.com/[^\s\"')]+/?", re.I)


def _platform_url_for(platform: str, value: str) -> str | None:
    patterns: dict[str, list[re.Pattern]] = {
        "linkedin": [_LINKEDIN_COMPANY_RE, _LINKEDIN_RE],
        "instagram": [_INSTAGRAM_RE],
        "tiktok": [_TIKTOK_RE],
        "x": [_X_RE],
    }
    for pattern in patterns.get(platform, []):
        match = pattern.search(value or "")
        if match:
            return match.group(0)
    return None


def _record_matches_account(raw: dict, account: AccountRecord) -> bool:
    text = json.dumps(raw, ensure_ascii=False, default=str).lower()
    needle = re.sub(r"[^a-z0-9]+", "", (account.name or "").lower())
    hay = re.sub(r"[^a-z0-9]+", "", text)
    if needle and needle in hay:
        return True
    domain = (account.domain or "").lower()
    if domain and domain in text:
        return True
    if account.platform and account.platform.lower() in text:
        return True
    return False


_GENERIC_EMAIL_LOCALS = contacts.GENERIC_LOCALS


def _domain_emails_from_queries(queries: list[str], acc: AccountRecord, cfg: Settings, cutoff: str) -> list[str]:
    """Run targeted Exa queries and return domain-matched emails, de-duplicated."""
    found: list[str] = []
    for query in queries[:2]:
        try:
            hits = _search_and_scrape(query, cfg, num_results=3, start_published_date=cutoff)
        except Exception as e:
            print(f"⚠️ email search failed for '{acc.name}': {e}")
            continue
        for hit in hits:
            text = f"{hit.get('title', '') or ''}\n{hit.get('text', '') or ''}"
            for email in _EMAIL_RE.findall(text):
                email = email.lower().strip()
                domain = email.split("@", 1)[-1]
                if not acc.domain or domain == acc.domain or domain.endswith("." + acc.domain):
                    found.append(email)
        if found:
            break
    seen: set[str] = set()
    out: list[str] = []
    for e in found:
        if e not in seen:
            seen.add(e)
            out.append(e)
    return out


def _pick_email(emails: list[str], contact_name: str | None) -> str | None:
    """Named people: prefer name-matching or non-generic addresses; otherwise
    prefer generic org mailboxes."""
    if not emails:
        return None

    def score(e: str) -> tuple[int, str]:
        local = e.split("@", 1)[0].lower()
        generic = 1 if local.startswith(_GENERIC_EMAIL_LOCALS) else 0
        if contact_name:
            parts = [p for p in re.split(r"[^a-z]+", contact_name.lower()) if len(p) >= 3]
            return (0 if any(p in local for p in parts) else (2 if generic else 1), e)
        return (0 if generic else 1, e)

    return sorted(emails, key=score)[0]


def collect_socials_and_emails(state: IcpSessionState) -> dict:
    """Find/fill social pages and emails for the kept accounts.

    Companies: Exa search -> URL match -> Bright Data scrape only when the URL
    match is ambiguous. Venues: use the platform from the extractor, hydrate via
    the matching social module. Contacts: hydrate missing name/title. Emails:
    regex-harvested from already-retrieved page text/profile bios first, Exa
    email-search last. All failures are logged and non-fatal.

    Platform effort is ordered by buyer type: B2B spends its budget on email +
    LinkedIn, B2C prioritises Instagram/TikTok (where creators put their
    contact email in the bio, so we harvest it from the profile payload
    instead of paying for extra searches). Countries that used to re-search
    the same URL get short-circuited by the per-platform seeds.
    """
    accounts = state.get("accounts")
    if not accounts or not accounts.accounts:
        return {}

    cfg = get_settings()
    cutoff = _recency_cutoff(cfg.market_recency_days)
    docs = state.get("account_discovery_docs") or []
    icp = state.get("icp_data")
    buyer_type = (icp.buyer_type or "b2b").lower() if icp else "b2b"
    consumer_first = buyer_type in ("b2c", "both")
    buyer_titles = list(icp.buyer_titles or []) if icp else []
    if _FAST_DISCOVERY or buyer_type == "b2b":
        _platforms = ("linkedin", "x", "instagram", "tiktok")
    else:
        _platforms = ("instagram", "tiktok", "x", "linkedin")

    def _bio_emails(raw: dict) -> list[str]:
        """Contact emails published in a creator's/venue's own profile fields."""
        blob = json.dumps(raw, ensure_ascii=False, default=str)
        return sorted(set(_EMAIL_RE.findall(blob)))

    def _docs_emails(acc) -> list[str]:
        """Emails sitting in page text we already scraped — free, no new calls."""
        out: list[str] = []
        for d in docs:
            text = d.get("text") or ""
            title = d.get("title") or ""
            if acc.domain and acc.domain.lower() not in (text + title).lower() and (acc.name or "").lower() not in (text + title).lower():
                continue
            for e in _EMAIL_RE.findall(text):
                e = e.lower()
                if not acc.domain or e.endswith("@" + acc.domain) or e.endswith("." + acc.domain) or acc.domain in e:
                    out.append(e)
        return list(dict.fromkeys(out))

    def _process(acc):
        # Seed socials from URLs we already collected (trigger source /
        # sources list) — those hosts are a free, authoritative hit and
        # let us skip the paid Exa search for that platform entirely.
        for _platform in _platforms:
            if _platform in (acc.socials or {}):
                continue
            for _src in list(acc.sources or []):
                _url = _platform_url_for(_platform, getattr(_src, "url", "") or "")
                if _url:
                    acc.socials = {**(acc.socials or {}), _platform: _url}
                    break
            else:
                _url = _platform_url_for(
                    _platform,
                    acc.trigger_event.source if acc.trigger_event else "",
                )
                if _url:
                    acc.socials = {**(acc.socials or {}), _platform: _url}
        is_company = not acc.account_type or acc.account_type == "company"
        if is_company:
            queries = {
                "linkedin": f'"{acc.name}" site:linkedin.com/company {acc.domain or ""}'.strip(),
                "instagram": f'"{acc.name}" site:instagram.com {acc.domain or ""}'.strip(),
                "tiktok": f'"{acc.name}" site:tiktok.com {acc.domain or ""}'.strip(),
                "x": f'"{acc.name}" site:x.com {acc.domain or ""}'.strip(),
            }
            if _FAST_DISCOVERY:
                wanted = {"linkedin"}
            elif consumer_first:
                wanted = set(_platforms)
            else:
                # B2B: LinkedIn first; only keep searching platforms while we
                # still have neither a social nor any email path for this account.
                wanted = {"linkedin"}
            for platform_name in _platforms:
                if platform_name not in wanted:
                    if buyer_type == "b2b" and (acc.socials or any(c.email for c in acc.key_contacts)):
                        break  # enough for a B2B account
                    continue
                if platform_name in (acc.socials or {}):
                    continue
                query = queries[platform_name]
                try:
                    hits = _search_and_scrape(query, cfg, num_results=MAX_QUERY_RESULTS, start_published_date=cutoff)
                except Exception as e:
                    print(f"⚠️ social search failed for '{acc.name}' ({platform_name}): {e}")
                    continue
                for hit in hits:
                    candidate_url = _platform_url_for(platform_name, hit.get("url", "") or "") or _platform_url_for(
                        platform_name, hit.get("text", "") or ""
                    )
                    if not candidate_url:
                        continue
                    # Cheap acceptance: if this URL's slug obviously matches the
                    # account's domain, skip the Bright Data validation scrape
                    # (it costs several seconds per platform per account).
                    slug_ok = bool(acc.domain) and acc.domain.split(".")[0].lower() in candidate_url.lower()
                    if slug_ok:
                        acc.socials = {**(acc.socials or {}), platform_name: candidate_url}
                        print(f"🔗 '{acc.name}' {platform_name} -> {candidate_url} (url match, no hydration)")
                        break
                    handler = {
                        "linkedin": linkedin.get_company,
                        "instagram": instagram.get_profile,
                        "tiktok": tiktok.get_profile,
                        "x": x.get_profile,
                    }[platform_name]
                    raw = call_with_timeout(lambda: handler(candidate_url, cfg), _SCRAPE_TIMEOUT_S, default=None, label=f'social[{platform_name}]')
                    if isinstance(raw, dict) and _record_matches_account(raw, acc):
                        acc.socials = {**(acc.socials or {}), platform_name: candidate_url}
                        if platform_name == "linkedin" and raw.get("company_size"):
                            acc.size = raw["company_size"]  # real headcount beats any model claim
                        print(f"🔗 '{acc.name}' {platform_name} -> {candidate_url}")
                        break
        else:
            inferred = (acc.platform or "").lower()
            platform_key = {
                "linkedin": "linkedin",
                "instagram": "instagram",
                "tiktok": "tiktok",
                "x": "x",
                "twitter": "x",
            }.get(inferred)
            url = _platform_url_for(platform_key or "", acc.platform or "") if platform_key else None
            if not url and platform_key:
                for source in acc.sources or []:
                    url = _platform_url_for(platform_key, source.url or "")
                    if url:
                        break
            if platform_key in ("linkedin", "instagram", "tiktok", "x") and url:
                handler = {
                    "linkedin": linkedin.get_profile,
                    "instagram": instagram.get_profile,
                    "tiktok": tiktok.get_profile,
                    "x": x.get_profile,
                }[platform_key]
                raw = call_with_timeout(lambda: handler(url, cfg), _SCRAPE_TIMEOUT_S, default=None, label=f'social[{platform_key}]')
                if isinstance(raw, dict):
                    acc.socials = {**(acc.socials or {}), platform_key: url}
                    followers = raw.get("followers") or raw.get("follower_count")
                    if not acc.member_size and isinstance(followers, (int, float)):
                        acc.member_size = str(followers)
                    # B2C venue/creator: contact email is usually in the bio.
                    for e in _bio_emails(raw):
                        if not any(c.email == e for c in acc.key_contacts):
                            acc.key_contacts.append(ContactRecord(email=e))
                            print(f"📧 '{acc.name}' bio email -> {e}")
                            break
                    print(f"🔗 venue '{acc.name}' {platform_key} -> {url}")

        # Hydrate contact details for people who already have a LinkedIn URL.
        for contact in acc.key_contacts[:1 if _FAST_DISCOVERY else 3]:
            if contact.linkedin and "linkedin.com/in" in contact.linkedin and (not contact.name or not contact.title):
                raw = call_with_timeout(lambda: linkedin.get_profile(contact.linkedin, cfg), _SCRAPE_TIMEOUT_S, default=None, label='linkedin[contact]')
                if isinstance(raw, dict):
                    hay = json.dumps(raw, ensure_ascii=False, default=str).lower()
                    if (acc.name or "").lower() in hay:
                        contact.name = contact.name or raw.get("name") or raw.get("full_name")
                        contact.title = contact.title or raw.get("headline") or raw.get("title")

        # Named people first: use Exa to find a domain-matched email per person.
        for contact in acc.key_contacts[:0 if _FAST_DISCOVERY else MAX_PERSONAL_EMAIL_LOOKUPS]:
            if contact.email or not contact.name:
                continue
            # Try pages we already retrieved before spending an Exa query.
            free = [e for e in _docs_emails(acc) if any(p in e for p in [p for p in re.split(r"[^a-z]+", contact.name.lower()) if len(p) >= 3])]
            if free:
                contact.email = free[0]
                print(f"📧 '{acc.name}' person '{contact.name}' -> {free[0]} (from retrieved pages)")
                continue
            queries = [
                f'"{contact.name}" "{acc.domain}" email' if acc.domain else f'"{contact.name}" "{acc.name}" email',
            ]
            emails = _domain_emails_from_queries(queries, acc, cfg, cutoff)
            chosen = _pick_email(emails, contact.name)
            if chosen:
                contact.email = chosen
                print(f"📧 '{acc.name}' person '{contact.name}' -> {chosen}")

        # Org-level email: harvest already-retrieved page text first, then one
        # careful Exa query, then (only when nothing found) a broad one.
        has_org_email = any(not c.name and c.email for c in acc.key_contacts)
        if not has_org_email:
            free_org = _docs_emails(acc)
            chosen = _pick_email(free_org, None)
            if chosen:
                acc.key_contacts.append(ContactRecord(email=chosen))
                print(f"📧 '{acc.name}' org email -> {chosen} (from retrieved pages)")
            else:
                org_queries = [
                    f'"{acc.name}" "{acc.domain}" email contact' if acc.domain else f'"{acc.name}" email contact',
                    f'"{acc.name}" email',
                ][:1 if _FAST_DISCOVERY else 2]
                org_emails = _domain_emails_from_queries(org_queries, acc, cfg, cutoff)
                chosen = _pick_email(org_emails, None)
                if chosen:
                    acc.key_contacts.append(ContactRecord(email=chosen))
                    print(f"📧 '{acc.name}' org email -> {chosen}")

        # Fill in contacts until there is a named person to reach, best first;
        # undeliverable addresses are dropped here.
        contacts.complete(acc, buyer_titles, cfg, MAX_ACCOUNT_CONTACTS)

    run_parallel(
        [lambda a=acc: (_enrich_one_account(a, cfg), _process(a))[1] for acc in accounts.accounts],
        workers=_SOCIALS_WORKERS,
    )
    return {"accounts": accounts}


def _enrich_one_account(acc, cfg):
    # Only companies need a verifiable own website; venues are validated
    # differently in verify_accounts (platform + size/date, not a homepage).
    is_company = not acc.account_type or acc.account_type == "company"
    if not is_company or (acc.website and acc.domain):
        return acc
    geo = acc.geo or ""
    query = f'"{acc.name}" {geo} official website'
    try:
        hits = _search_and_scrape(query, cfg, num_results=3)
    except Exception as e:  # search failure must not sink the run
        print(f"⚠️ enrich search failed for '{acc.name}': {e}")
        return acc
    site = next((h for h in hits if _host_ok(h.get("url", "")) and _is_homepage_like(h.get("url", ""))), None)
    if site is None:
        print(f"⚠️ no own-site hit for '{acc.name}'")
        return acc
    url = site["url"]
    acc.website = acc.website or url
    acc.domain = acc.domain or re.sub(r"^https?://(www\.)?", "", url).split("/")[0]
    print(f"🔧 enriched '{acc.name}' -> {acc.website}")

    # Pull any public contact details off the page text we already have.
    try:
        page_text = site.get("text") or ""
        emails = sorted(set(_EMAIL_RE.findall(page_text)))[:3]
        linkedins = sorted(set(_LINKEDIN_RE.findall(page_text)))[:2]
        if not acc.key_contacts and (emails or linkedins):
            acc.key_contacts = (
                [ContactRecord(email=e) for e in emails]
                + [ContactRecord(linkedin=l) for l in linkedins]
            )
    except Exception:
        pass
    return acc


def enrich_accounts(state: IcpSessionState) -> dict:
    """Repair pass between extraction and verification.

    Extraction only fills fields present in search snippets, so most accounts
    arrive without a website. For each such account, run one targeted Exa
    search for the account's own site, scrape it, and fill website/domain plus
    any email/LinkedIn visible on the page (never invented). Accounts that
    still have no website are dropped by verify_accounts.
    """
    accounts = state.get("accounts")
    if not accounts or not accounts.accounts:
        return {}

    cfg = get_settings()

    repaired = run_parallel(
        [lambda a=acc: _enrich_one_account(a, cfg) for acc in accounts.accounts],
        workers=_ENRICH_WORKERS,
    )
    repaired = [a if a is not None else orig for a, orig in zip(repaired, accounts.accounts)]
    return {"accounts": AccountList(accounts=repaired)}


_HEADCOUNT_RE = re.compile(r"(\d[\d,]*)\s*(?:[-–—]|to)\s*(\d[\d,]*)(\+)?|(\d[\d,]*)\s*(\+|employees)", re.I)


def _headcount_range(text: str | None) -> tuple[int, float] | None:
    """(low, high) employees from '51-200 employees', '10,001+', '501–2,000+',
    '120 employees'. None when no headcount is stated."""
    match = _HEADCOUNT_RE.search(text or "")
    if not match:
        return None
    if match.group(4):  # a single number: "10,001+" or "120 employees"
        lo = int(match.group(4).replace(",", ""))
        return lo, float("inf") if match.group(5) == "+" else lo
    lo, hi = (int(match.group(i).replace(",", "")) for i in (1, 2))
    return lo, float("inf") if match.group(3) else hi


def _size_verdict(acc, icp_sizes: list[str]) -> str | None:
    """'too_large' when the account's stated headcount starts above the ICP's
    largest band. A size copied verbatim from an ICP band is not evidence and
    is cleared first."""
    if acc.size and acc.size.strip().lower() in {b.strip().lower() for b in icp_sizes}:
        acc.size = None
    bands = [r for r in (_headcount_range(b) for b in icp_sizes) if r]
    account = _headcount_range(acc.size)
    if not bands or not account:
        return None
    return "too_large" if account[0] > max(hi for _, hi in bands) else None


def verify_accounts(state: IcpSessionState) -> dict:
    """Hard-constraint pass: drop trigger-less targets, require the trigger's
    source to exist in the retrieved docs, dedupe by domain (or platform::name
    for venues), cap at MAX_ACCOUNT_ROWS."""
    accounts = state.get("accounts")
    if not accounts or not accounts.accounts:
        return {"accounts": AccountList(accounts=[])}

    doc_urls = {d.get("url") for d in (state.get("account_discovery_docs") or [])}
    icp = state.get("icp_data")
    icp_sizes = list(icp.company_sizes or []) if icp else []
    kept, seen = [], set()
    for acc in accounts.accounts:
        if (not acc.account_type or acc.account_type == "company") and _size_verdict(acc, icp_sizes) == "too_large":
            print(f"❌ Dropping '{acc.name}' — {acc.size} is larger than any ICP size band.")
            continue
        if acc.trigger_event is None:
            print(f"❌ Dropping '{acc.name}' — no current trigger_event.")
            continue
        src = acc.trigger_event.source if isinstance(acc.trigger_event, TriggerEvent) else None
        if not src:
            print(f"❌ Dropping '{acc.name}' — trigger has no source.")
            continue
        if src not in doc_urls:
            print(f"⚠️ '{acc.name}' trigger source not in retrieved docs: {src}")
        is_company = not acc.account_type or acc.account_type == "company"
        if is_company:
            # Website is a hard requirement for companies: without it the
            # account is not verifiable. Contacts are NOT hard-dropped —
            # many real SMEs publish none; flagged instead.
            if not acc.website:
                print(f"❌ Dropping '{acc.name}' — no verifiable website after enrichment.")
                continue
        else:
            # Venues (community/event/creator/platform): require the reach
            # evidence instead of a homepage — platform + a size or date.
            if not acc.platform:
                # Infer from the trigger source URL host before dropping.
                src_l = (acc.trigger_event.source or "").lower() if acc.trigger_event else ""
                for needle, label in (
                    ("linkedin.com", "LinkedIn"), ("instagram.com", "Instagram"),
                    ("tiktok.com", "TikTok"), ("x.com", "X"), ("twitter.com", "X"),
                    ("wattpad.com", "Wattpad"), ("discord", "Discord"),
                    ("reddit.com", "Reddit"), ("facebook.com", "Facebook"),
                    ("substack.com", "Substack"), ("youtube.com", "YouTube"),
                ):
                    if needle in src_l:
                        acc.platform = label
                        break
            if not acc.platform:
                print(f"❌ Dropping '{acc.name}' — venue target has no platform.")
                continue
            if not (acc.member_size or acc.event_date):
                print(f"⚠️ '{acc.name}' kept without audience size / event date.")

        # Contacts are what makes a target actionable: no email, no person on
        # LinkedIn and no social page means nobody to reach, so it is dropped
        # (extraction over-fetches to make up for it).
        if not contacts.reachable(acc):
            logger.info("Dropping %s -- no contact, LinkedIn person or social page found", acc.name)
            continue
        if acc.account_type and acc.account_type != "company":
            key = f"{acc.platform or acc.account_type}::{acc.name}".strip().lower()
        else:
            key = (acc.domain or acc.website or acc.name).strip().lower()
        if key in seen:
            print(f"❌ Dropping duplicate '{acc.name}' (already kept).")
            continue
        seen.add(key)
        kept.append(acc)

    kept = kept[:MAX_ACCOUNT_ROWS]
    print(f"✅ Verified targets: {len(kept)} (dropped {len(accounts.accounts) - len(kept)})")
    if len(kept) < MIN_DEFENSIBLE:
        print(f"⚠️ Fewer than {MIN_DEFENSIBLE} defensible targets — keeping the defensible set, not inventing more.")
    return {"accounts": AccountList(accounts=kept)}


def build_account_discovery_graph(checkpointer: bool = True):
    agent = StateGraph(IcpSessionState)

    agent.add_node("create_account_queries", timed_node(create_account_queries))
    agent.add_node("search_accounts", timed_node(search_accounts))
    agent.add_node("extract_accounts", timed_node(extract_accounts))
    agent.add_node("collect_socials_and_emails", timed_node(collect_socials_and_emails))
    agent.add_node("verify_accounts", timed_node(verify_accounts))

    agent.add_edge(START, "create_account_queries")
    agent.add_edge("create_account_queries", "search_accounts")
    agent.add_edge("search_accounts", "extract_accounts")
    agent.add_edge("extract_accounts", "collect_socials_and_emails")
    agent.add_edge("collect_socials_and_emails", "verify_accounts")
    agent.add_edge("verify_accounts", END)

    if checkpointer:
        return agent.compile(checkpointer=MemorySaver())
    return agent.compile()


def run_account_discovery(state: IcpSessionState) -> dict:
    """Standalone helper: build graph, invoke once, return final state."""
    graph = build_account_discovery_graph(checkpointer=False)
    result = graph.invoke(state)
    return result


# Segment fan-out ------------------------------------------------------------------

MAX_SEGMENTS = 6
MAX_MERGED_ACCOUNTS = 24
SEGMENT_MAX_WORKERS = 4


def _segments_for(state: IcpSessionState) -> list[dict]:
    """One segment per (industry × geo) for B2B, (persona/channel × geo) for B2C."""
    icp: Optional[ICP] = state.get("icp_data")
    geos = _geos_for(state, icp)[:3]
    buyer_type = (icp.buyer_type or "b2b").lower() if icp else "b2b"
    segments: list[dict] = []

    if buyer_type in ("b2b", "both") and icp:
        for ind in (icp.industries or [])[:3]:
            for geo in geos:
                segments.append({"kind": "industry", "label": ind, "geo": geo})
    if buyer_type in ("b2c", "both") and icp:
        buds = [p.name for p in (icp.buyer_personas or [])][:2]
        buds += [c.name for c in (icp.target_channels or [])][:2]
        for label in buds:
            for geo in geos:
                segments.append({"kind": "persona_channel", "label": label, "geo": geo})

    if not segments:  # no structure to segment on: single run over the whole ICP
        segments = [{"kind": "whole", "label": "all", "geo": geos[0] if geos else ""}]
    return segments[:MAX_SEGMENTS]


def _segment_state(state: IcpSessionState, seg: dict) -> IcpSessionState:
    """Narrow a copy of the session state to one segment's scope."""
    icp: Optional[ICP] = state.get("icp_data")
    seg_icp = icp.model_copy(deep=True) if icp else None
    if seg_icp is not None:
        if seg["kind"] == "industry":
            seg_icp.industries = [seg["label"]]
        elif seg["kind"] == "persona_channel":
            seg_icp.buyer_personas = [p for p in seg_icp.buyer_personas if p.name == seg["label"]]
            seg_icp.target_channels = [c for c in seg_icp.target_channels if c.name == seg["label"]]
        seg_icp.geo = [seg["geo"]] if seg["geo"] else seg_icp.geo
    out = dict(state)
    out["icp_data"] = seg_icp
    out["target_market"] = [seg["geo"]] if seg["geo"] else (state.get("target_market") or [])
    return out


def run_account_discovery_segmented(state: IcpSessionState) -> dict:
    """Run the account-discovery graph once per segment and merge the lists.

    Each segment returns its own ≤ MAX_ACCOUNT_ROWS accounts; the merged list
    is larger because the cap applies per segment. Duplicates across segments
    are resolved by domain/platform key, keeping the higher-scored record."""
    from agents.concurrency import ContextThreadPoolExecutor

    segments = _segments_for(state)
    print(f"Segmented account discovery over {len(segments)} segments: "
          f"{[(s['kind'], s['label'], s['geo']) for s in segments]}")

    def _run(seg: dict) -> dict:
        try:
            result = build_account_discovery_graph(checkpointer=False).invoke(_segment_state(state, seg))
            return result
        except Exception as e:
            # A single segment's LLM/Exa failure must not sink the merged run.
            print(f"⚠️ segment {seg} failed, continuing with the rest: {e}")
            return {}

    results: list[dict] = []
    with ContextThreadPoolExecutor(max_workers=SEGMENT_MAX_WORKERS) as pool:
        results = list(pool.map(_run, segments))

    merged: dict[str, AccountRecord] = {}
    docs: list[dict] = []
    seen_docs: set[str] = set()
    for res in results:
        accs = res.get("accounts")
        for acc in (accs.accounts if accs else []):
            # Prefer the concrete website/domain key; venue names vary how they
            # spell their platform ("Website" vs None), so platform::name alone
            # splits the same venue into two rows.
            key = (acc.domain or acc.website or "").strip().lower()
            if not key:
                # No resolvable site: fall back to the bare name so the same
                # venue (however it spells its platform) merges across segments.
                key = acc.name.strip().lower()
            prev = merged.get(key)
            if prev is None or (acc.score or 0) > (prev.score or 0):
                merged[key] = acc
        for d in (res.get("account_discovery_docs") or []):
            if d.get("url") and d["url"] not in seen_docs:
                seen_docs.add(d["url"])
                docs.append(d)

    ranked = sorted(merged.values(), key=lambda a: a.score or 0.0, reverse=True)[:MAX_MERGED_ACCOUNTS]
    print(f"Merged {len(ranked)} unique accounts across segments (was {sum(len(r.get('accounts').accounts) if r.get('accounts') else 0 for r in results)} pre-dedupe)")
    return {"accounts": AccountList(accounts=ranked), "account_discovery_docs": docs}
