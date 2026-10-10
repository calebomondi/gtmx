"""Find and profile the real companies competing with this offer.

STANDALONE, and deliberately not a node of the discovery graph. The competition
stage (`understand_competition`) answers "what does a rival look like here" and
deliberately names nobody; this agent answers "which specific companies are they,
and what do we know about each". Those are different questions with different
epistemic standards, and folding them into one stage is how a construct starts
being read as a fact. This one is re-runnable on its own, appends to a growing
watch list, and is triggered by POST + polled -- not a second WebSocket, because
it is not part of the discovery conversation and has no interrupts to answer.

THE TWO STANDARDS, AND WHY THEY NEVER MIX
-----------------------------------------
`understand_competition` builds an IdealCompetitorProfile: archetypes like "the
regional incumbent undercutting on price". That is a construct. No firm is
claimed to exist, so the profile is allowed to be aggressive, speculative and
unsourced -- an invented archetype costs nothing because it is not about anyone.

Everything here is the opposite. Each row is a claim that a NAMED, REAL company
exists and does specific things. An invented weakness attributed to a real named
business is not a hypothesis, it is a factual error about an identifiable
company. So the instruction to "be aggressive" that shapes the profile has NO
counterpart here, and its absence is the point:

  - a candidate with no findable public website is DROPPED, not stored with a
    blank URL;
  - `SourcedFinding` requires `evidence`, so an unsourced claim about a real
    company cannot even be constructed (see schema_states.py);
  - anything research could not establish goes in `unsourced_fields` and is
    rendered as "not found", so a gap is never dressed up as a finding;
  - our own brand never enters a query, and our own site is never returned as
    our own competitor.

The one place aggression IS allowed is `opportunities`. The brief requires them
even when no pain signal exists -- better quality, faster, cheaper -- and that is
sound, because an opportunity is a claim about US ("we could beat them on
price"), derived from cited facts about them, not an assertion about them. It
lives in its own field so it cannot be misread as a sourced observation.

WHAT A RUN DOES
---------------
    plan_hunt  -> per-archetype search tasks, local AND international
    hunt_candidates -> search, extract candidate firms WITH their websites
    screen_candidates -> the hard website filter, plus dedup and self-exclusion
    profile_competitors -> read each survivor's own site, build a sourced profile
    persist -> write to the competitors table, upserting ones already tracked

Costs one planner call, one distill + one extraction per task, then one deep
profile per surviving competitor. Re-running appends: firms already on the list
are refreshed rather than duplicated, and `last_seen_at` moves.
"""

import re
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from typing import Optional
from urllib.parse import urlparse

from langgraph.graph import END, START, StateGraph

from config import get_settings
from agents.context_budget import distill_documents
from agents.llm.main import invoke_structured_with_fallback
from agents.schemas.competition import IdealCompetitorProfile
from data_sources.scraping.exa import scrape_url, search_and_scrape

from ..web_utils import call_with_timeout, search_cache_get, search_cache_put, timed_node

_SEARCH_TIMEOUT_S = get_settings().competitor_search_timeout_s
_SCRAPE_TIMEOUT_S = get_settings().competitor_scrape_timeout_s


def _search_and_scrape(query, config, num_results=5, start_published_date=None):
    """search_and_scrape with a small TTL cache and a hard timeout."""
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

from agents.schemas.competition import CandidateFinding, CompetitorHuntBundle, CompetitorHuntPlan, CompetitorHuntTask, CompetitorProfile, CompetitorProfileBatch, CompetitorRunOutcome, SourcedFinding
from agents.schemas.sessions import CompetitorSessionState


# Bounds. The archetype count comes from the profile (3-8 in practice); the
# per-task cap keeps a pathological profile from turning one run into forty
# searches, and the candidate cap keeps one chatty directory page from becoming
# forty competitor profiles.
MAX_HUNT_TASKS = 8
SEARCH_RESULTS_PER_QUERY = 4
MAX_CANDIDATES_PER_TASK = 8
MAX_CANDIDATES_PER_RUN = 24
# Concurrency for the deep phase: each profile is several network round-trips, so
# this is the difference between a run finishing in a minute and in five.
PROFILE_WORKERS = get_settings().competitor_profile_workers

# A website has to look like one. The screening stage applies this before a
# candidate is allowed to become a tracked company -- the brief's filter is "a
# publicly available website", and "publicly available" has to mean more than
# "some string appeared in a search result".
_WEBSITE_SHAPE = re.compile(r"^https?://[^\s/$.?#].[^\s]*$", re.IGNORECASE)

# Hosts that are not a competitor's own site. A directory listing, a news write
# -up or a social profile is evidence ABOUT a firm, not the firm. Accepting one
# as `website` would put a tracking URL in the column the whole dedup and
# monitoring story is built on.
_NON_SITE_HOSTS = (
    "linkedin.com", "facebook.com", "instagram.com", "twitter.com", "x.com",
    "tiktok.com", "youtube.com", "reddit.com", "medium.com", "wikipedia.org",
    "crunchbase.com", "g2.com", "capterra.com", "trustpilot.com", "glassdoor.com",
    "producthunt.com", "github.com", "gitlab.com", "notion.so", "docs.google.com",
    "amazon.com", "ebay.com", "alibaba.com", "indeed.com", "glassdoor.co.uk",
    "bloomberg.com", "techcrunch.com", "forbes.com", "wired.com", "theverge.com",
)


# ---------------------------------------------------------------------------
# Prompt templates
# ---------------------------------------------------------------------------

plan_instructions = """\
You are planning a hunt for the REAL companies competing with a {offer_noun}.

You are given an ideal competitor profile. It is a set of ARCHETYPES -- shapes
of competitor, not names. Your job is to turn each archetype into web searches
that would surface actual companies matching it.

Hunt BOTH local and international competitors — but locals first. The
profile carries a `geography_scope` per archetype and separate
`global_entry_signals` and `local_defence_signals`; use all of it. Where
`target_geo` is provided, put at least one country/region-specific query for
that archetype before the broad fallback (e.g. "... companies in Kenya", then
"... companies in Africa", then "... companies globally"). Do not widen
globally before you have exhausted the local phrasing.

For each archetype, produce 2-3 queries. Query shape that works:
  - the archetype's category words plus a buyer or directory word
    ("vector database companies Europe", "enterprise rag platform vendors")
  - list-shaped phrasings people actually search
    ("best on-device inference tools", "companies building X in Kenya")
  - the substitution the archetype represents, in the substitute's own language

HARD RULES
1. NEVER name the offer in a query. "alternatives to {offer_name}" returns SEO
   listicles and comparison pages, not the competitors. Search the CATEGORY.
2. Never invent a company name into a query. You are looking for firms you do
   not know yet; if you seed a query with a name you recall, you will only ever
   find that name and its SEO echo.
3. Cover every archetype. If the profile has 6 archetypes, produce tasks for all
   6 -- a run that quietly skips archetypes is a run that quietly under-reports.

Produce {max_tasks} tasks at most.
"""

extract_instructions = """\
From the research notes below, list the actual COMPANIES that were found.

A candidate is a real, named business with a public website. For each one give:

- `name`: the company as it brands itself.
- `website`: its own public site, EXACTLY as it appeared in the notes. This is
  the single most important field. A candidate with no website is dropped by
  the next stage, so a missing one costs you a real competitor.
  Rules:
    * Give the company's OWN domain, not the page you read about it. If the
      notes mention Acme on a directory listing, the website is acme.com, not
      the directory's URL.
    * Reject social and directory hosts as the website: linkedin.com,
      facebook.com, instagram.com, twitter.com, x.com, tiktok.com, reddit.com,
      medium.com, wikipedia.org, crunchbase.com, g2.com, capterra.com,
      trustpilot.com, glassdoor.com, producthunt.com, github.com, notion.so,
      amazon.com, and any news site. Those are evidence about a firm, not the
      firm. If a candidate's ONLY address is one of those, set `website` to null
      and let it be dropped.
    * Copy the URL, do not construct one. If the notes never state the domain,
      `website` is null. Never guess a company's domain from its name --
      "acme" might be acme.com, acme.ai, acmehq.com or getacme.com, and a
      plausible invention here becomes a tracked company that does not exist.
- `evidence_urls`: the notes pages that named this company and showed its site.
- `why_it_might_match`: one line tying it to the archetype being hunted. If you
  are guessing, say so in this line -- it is checked later.
- `geography_hint`: where the notes suggest it is based, if stated.

ONLY list companies the notes actually name. If the notes discuss the category
without naming firms, return an empty list: an empty result is a real answer
here, and a padded one is a list of companies nobody found.

Notes for the archetype "{archetype_label}" ({geography_scope}):
---
{notes}
---
"""

profile_instructions = """\
Build a sourced profile of ONE real company, for a workspace selling this
{offer_noun}.

The company: {name}
Its website: {website}
The archetype it was found under: {archetype}

You are writing about a REAL, IDENTIFIABLE BUSINESS. Every claim you make about
it can be checked against it, and a wrong claim does real damage to a real
company's reputation. So the standard here is the opposite of the archetype
profile this hunt was planned from -- that one is a construct and may speculate
freely; this one may not.

Retrieved material about {name}:
---
{evidence}
---
Their own website:
---
{site}
---

EVERY FIELD FOLLOWS THE SAME RULE: either you can point at where you got it,
or you record that you could not.

- `evidence`: a map of field name -> the URLs that support it. Populate it for
  every substantive field you fill.
- `unsourced_fields`: the fields you could NOT establish. This is not a
  confession of failure, it is the honest result, and it is what the user sees
  as "not found". A field listed here renders as not-found; a field you filled
  with a plausible guess renders as a fact. Guess nothing.

`strengths` and `weaknesses` are lists of {finding_type}, each REQUIRING an
`evidence` quote or close paraphrase and its `source_url`. This is enforced by
the schema -- an unsourced finding cannot be saved. If you cannot evidence a
weakness, there is no weakness on this list, and that is a legitimate outcome:
most rivals are simply competent, and a fabricated weakness is worse than none.

`pain_signals`: specific evidenced complaints customers actually voice. Empty is
common and normal. It means nobody complained in what was retrieved -- NOT that
the company has no problems. Do not manufacture a complaint to fill the list.

`customer_sentiment`: what customers say about them overall, evidenced the same
way. Kept separate from pain signals because a well-liked company can still beat
us on price, and flattening those two into one field destroys that distinction.

`opportunities`: openings for the user's {offer_noun} -- better quality, faster,
cheaper, a segment they ignore, a channel they are absent from. GENERATE THESE
EVEN IF `pain_signals` IS EMPTY; that is an explicit requirement, and "they have
no complaints" is itself an opening (a competitor nobody complains about is a
competitor nobody is fighting). Unlike the fields above, an opportunity is a
claim about US rather than about them, so it is a judgement derived from the
cited facts and the user's offer, not a quote. Say what the opening is and what
fact about them creates it.

`tracking_sources`: their socials -- Instagram, TikTok, X, LinkedIn, plus
website and github if you find them. Use `confidence` honestly:
  - `high`: read off the company's own site (a link in its footer or contact page)
  - `medium`: found beside the company name in a retrieved page
  - `low`: inferred from the handle pattern alone
If a network was not found, leave it out. Do NOT construct a plausible handle
from the company name -- "@acmehq" is a real account belonging to someone else.

`geography_scope`: local | regional | global | any. Judge from their own site --
where they ship, where their customers are, where they are registered. Say
`global` when they serve anywhere; do not mark a firm local merely because the
search that found them was local.

`comparison`: how the user's {offer_noun} compares to this company, on the axes
the evidence above actually establishes. If the evidence is thin, say the
comparison is thin rather than reaching for a generic one.

`matched_archetype`: keep "{archetype}" if it fits, or give the better label.
"""


# ---------------------------------------------------------------------------
# Small helpers
# ---------------------------------------------------------------------------


def _offer_noun(state: CompetitorSessionState) -> str:
	return "service" if state.get("offer_type") == "service" else "product"


def _clean_website(raw: Optional[str]) -> Optional[str]:
    """Normalise a claimed website, or reject it.

    Returns None for anything that is not a usable http(s) URL. This is where the
    brief's hard filter becomes real: a candidate survives screening only if this
    returns a string, so the shape check and the directory/social rejection both
    happen before a row can be written.

    Also strips tracking noise, which matters more than it looks: the same firm
    arriving as `acme.com?utm_source=x` and `acme.com` must dedup to one row.
    """
    if not raw:
        return None
    candidate = raw.strip().strip("<>\"'")
    if not candidate:
        return None
    if not re.match(r"^https?://", candidate, re.IGNORECASE):
        candidate = f"https://{candidate}"
    if not _WEBSITE_SHAPE.match(candidate):
        return None
    host = (urlparse(candidate).netloc or "").lower()
    if not host:
        return None
    if any(host == bad or host.endswith(f".{bad}") for bad in _NON_SITE_HOSTS):
        return None
    # www is stripped here, not only inside _domain_key, so the URL actually
    # stored matches the key the dedup constraint is built on. Keeping both would
    # file `www.acme.com` and `acme.com` as two rows that both claim to be the
    # same company.
    host = host.removeprefix("www.")
    if not host or "." not in host:
        # A bare label like "localhost" or a single word is not a public site.
        return None
    # Drop the query and fragment; keep a path only when it is not the bare root,
    # since companies brand their apex domain and not /en/pricing.
    path = (urlparse(candidate).path or "").rstrip("/")
    return f"https://{host}{path}" if path else f"https://{host}"


def _domain_key(website: str) -> str:
    """The host, minus scheme and www -- the firm's identity for dedup.

    Mirrors `backend/app/api/v1/endpoints/competitors.py::_domain_key` on purpose.
    The agent writes rows the API also has to recognise as the same company, so
    the two normalisers must agree; a divergence would let the agent insert a
    duplicate the API then refuses to match.
    """
    host = (urlparse(website).netloc or "").strip().lower()
    if not host:
        return website.strip().lower()
    host = host.split("@")[-1].split(":")[0]
    return host.removeprefix("www.").rstrip(".")


def _self_domain(state: CompetitorSessionState) -> str:
    """Our own host, so a run never reports the user as their own competitor.

    Search engines will happily return the offer's own site for a category query,
    and a self-referential competitor row would be the most visible possible
    failure of this feature.
    """
    return _domain_key(_clean_website(state.get("own_website") or "") or "")


def _brand_patterns(state: CompetitorSessionState) -> list[re.Pattern[str]]:
    """Regexes matching the offer's own name, for keeping queries brand-free.

    Same shape as the competition stage's version, and for the same reason: the
    prompt rule is not reliable enough to be the guarantee. Matches the FULL name
    only -- splitting a multi-word name strips category nouns out of honest
    queries ("Acme Vector DB" would lose "vector") -- plus the stem of a
    single-word brand, which is often written with a suffix.
    """
    name = (state.get("offer_name") or "").strip()
    if not name:
        return []
    tokens = [t for t in re.split(r"[^\w]+", name.lower()) if t]
    if not tokens:
        return []
    phrase = r"\s+".join(re.escape(t) for t in tokens)
    patterns = [re.compile(rf"\b{phrase}\b", re.IGNORECASE)]
    if len(tokens) == 1 and len(tokens[0]) > 3:
        patterns.append(re.compile(rf"\b{re.escape(tokens[0])}\w{{0,6}}\b", re.IGNORECASE))
    return patterns


# Words that cannot carry a search on their own. A residue built only from these
# is what is left when a branded comparison is dismantled: "alternatives to
# Acme" becomes "alternatives", "who competes with Acme" becomes "who competes
# with". Neither searches for anything -- they return the query's own tail back
# with the noun gone -- so they are dropped instead.
#
# Split in two because they fail differently. COMPARISON words are the ones that
# _scrub_brand's connective regex removes first. FILLER is everything else that
# is grammatically load-bearing and semantically empty: without it, "who competes
# with" looks like it has content, because "who" and "with" are not comparison
# words. The test is "no word left that is neither", which is what catches both
# cases for one reason instead of a list per failure mode.
_COMPARISON_WORDS = frozenset({
    "competitor", "competitors", "competition", "competing", "compete", "competes",
    "alternative", "alternatives", "alts", "vs", "versus",
    "compare", "compared", "comparing", "comparison", "reviews", "review",
    "pricing", "price", "prices", "options", "best", "top", "good",
})
_FILLER_WORDS = frozenset({
    "a", "an", "the", "to", "of", "for", "with", "and", "or", "in", "on", "at",
    "who", "what", "which", "whom", "whose", "is", "are", "was", "were", "be",
    "being", "been", "by", "from", "that", "this", "these", "those", "it",
    "my", "our", "your", "their", "his", "her", "its", "us", "them", "me",
    "list", "lists", "find", "finding", "look", "looking", "get", "getting",
    "search", "searching", "show", "find",
})


def _has_searchable_content(query: str) -> bool:
    """Does this query still name something worth searching for?

    False means every word is comparison scaffolding or filler, so the query is
    the tail of a branded one with its subject removed. Running it wastes a
    search and returns either nothing or, worse, the comparison pages the
    original query was scrubbed to avoid.
    """
    words = re.findall(r"[a-z0-9]+", query.lower())
    return any(w not in _COMPARISON_WORDS and w not in _FILLER_WORDS for w in words)


def _scrub_brand(query: str, patterns: list[re.Pattern[str]]) -> str:
    """Rewrite a branded query into a category query, or drop it.

    "alternatives to Acme" is the single worst query this agent could run: it
    returns comparison listicles rather than the competitors themselves, and it
    puts the offer's own name into a search engine's query log for every user who
    runs it. A query that was nothing but the comparison is dropped rather than
    stripped down to the word "competitors".
    """
    if not patterns:
        return query
    scrubbed = query
    for pattern in patterns:
        scrubbed = pattern.sub("", scrubbed)
    if scrubbed == query:
        return query
    scrubbed = re.sub(
        r"\b(alternatives?\s+to|competitors?\s+(?:to|of|for)|versus|vs\.?|compared?\s+(?:to|with))\b",
        " ",
        scrubbed,
        flags=re.IGNORECASE,
    )
    scrubbed = re.sub(r"\s{2,}", " ", scrubbed).strip(" -,&")
    if not _has_searchable_content(scrubbed):
        return ""
    return scrubbed


def _archetype_rows(profile: Optional[IdealCompetitorProfile]) -> list[dict]:
    """The profile's archetypes as plain dicts, tolerating a raw dict input.

    The profile reaches this agent as a persisted JSON blob (the standalone agent
    cannot resume the discovery checkpoint), so it arrives as a dict rather than
    a validated model. Accepting both keeps this function from being the place
    where a dict-shaped profile silently hunts nothing.
    """
    if profile is None:
        return []
    archetypes = getattr(profile, "archetypes", None)
    if archetypes is None and isinstance(profile, dict):
        archetypes = profile.get("archetypes")
    rows: list[dict] = []
    for archetype in archetypes or []:
        if isinstance(archetype, dict):
            rows.append(archetype)
        elif hasattr(archetype, "model_dump"):
            rows.append(archetype.model_dump())
        else:  # pragma: no cover -- defensive
            rows.append(
                {
                    "label": getattr(archetype, "label", ""),
                    "geography_scope": getattr(archetype, "geography_scope", "any"),
                }
            )
    return rows


# ---------------------------------------------------------------------------
# Node 1: plan the hunt
# ---------------------------------------------------------------------------


def plan_hunt(state: CompetitorSessionState) -> dict:
    """One search assignment per archetype, local and international alike.

    Fails loudly, like the other planners in this codebase. A planner failure
    means the agent does not know what shape of company to look for, and a
    default "search for competitors" task would return listicles and file them as
    companies -- worse than reporting nothing.
    """
    archetypes = _archetype_rows(state.get("ideal_competitor_profile"))
    if not archetypes:
        raise ValueError(
            "get_competitors: no ideal competitor profile. The competition stage "
            "produces it; run discovery before hunting for competitors."
        )

    noun = _offer_noun(state)
    system_message = plan_instructions.format(
        offer_noun=noun,
        offer_name=state.get("offer_name") or "the offer",
        max_tasks=MAX_HUNT_TASKS,
    )
    target_geo = state.get("target_market") or []
    user_message = (
        f"The ideal competitor profile:\n{state['ideal_competitor_profile']}\n\n"
        f"Archetypes to hunt ({len(archetypes)}): "
        + "; ".join(
            f"{a.get('label')} [{a.get('geography_scope', 'any')}]" for a in archetypes
        )
        + (f"\nTarget geography(ies): {', '.join(target_geo)}" if target_geo else "")
    )

    plan = invoke_structured_with_fallback(
        [system_message, user_message],
        CompetitorHuntPlan,
        log_label="get_competitors:plan_hunt",
    )

    tasks = list(plan.tasks or [])[:MAX_HUNT_TASKS]

    # Enforce the brand-free invariant in code. The planner is told not to name
    # the offer and usually complies, but "alternatives to <us>" is exactly the
    # query this feature must never run, and a prompt rule is not a guarantee.
    patterns = _brand_patterns(state)
    cleaned: list[CompetitorHuntTask] = []
    for task in tasks:
        # Guarantee locality: prepend country-specific queries for each target geo
        # so the hunter always starts inside the offer's market.
        locals = []
        for geo in target_geo:
            locals.append(f"{task.archetype_label} companies in {geo}")
        all_queries = locals + list(task.queries or [])
        queries = [q for q in (_scrub_brand(q or "", patterns) for q in all_queries) if q]
        if not queries:
            # Every query was a branded comparison: this task has nothing left to
            # search for, so it is dropped rather than run as a null hunt.
            continue
        cleaned.append(task.model_copy(update={"queries": queries}))

    print(
        f"plan_hunt: {len(cleaned)} hunt task(s) from {len(archetypes)} archetype(s)"
    )
    for i, task in enumerate(cleaned, start=1):
        print(f"  {i}. [{task.geography_scope}] {task.archetype_label} ({len(task.queries)} queries)")
    return {"competitor_hunt_tasks": cleaned}


# ---------------------------------------------------------------------------
# Node 2: hunt for candidate firms
# ---------------------------------------------------------------------------


def _hunt_one(task: CompetitorHuntTask) -> CompetitorHuntBundle:
    """Search one archetype's queries and extract named firms from the results.

    Runs on a worker thread: takes no state and shares nothing mutable.
    """
    cfg = get_settings()
    issued: list[str] = []
    docs: list[dict] = []
    seen: set[str] = set()

    for query in task.queries or []:
        query = (query or "").strip()
        if not query:
            continue
        issued.append(query)
        try:
            from datetime import date, timedelta

            # Keep the hunt fresh — stale directory listings poison candidate
            # quality more than a thin result set does.
            cfg = get_settings()
            recency_cutoff = (date.today() - timedelta(days=cfg.market_recency_days)).isoformat()
            results = _search_and_scrape(
                query,
                cfg,
                num_results=SEARCH_RESULTS_PER_QUERY,
                start_published_date=recency_cutoff,
            )
        except Exception as exc:  # noqa: BLE001 -- one dead query must not kill the task
            print(f"hunt_candidates: query failed ({task.archetype_label}): {query} -> {exc}")
            continue
        for doc in results or []:
            url = doc.get("url") or ""
            if url and url in seen:
                continue
            if url:
                seen.add(url)
            docs.append(doc)
        if docs:
            # Queries are ordered specific-first with a broad fallback last, so
            # stopping here is the fallback working as designed.
            break

    bundle = CompetitorHuntBundle(
        archetype_label=task.archetype_label,
        geography_scope=task.geography_scope,
        queries=issued,
        search_failed=not docs,
        sources=docs,
    )
    if not docs:
        print(f"hunt_candidates: {task.archetype_label}: no sources")
        return bundle

    notes = distill_documents(
        docs,
        focus=(
            f"Named companies matching: {task.archetype_label}. "
            "Record each company's own name AND its own website domain if the page "
            "gives one. Keep social and directory URLs separate from the company's site."
        ),
        log_label=f"get_competitors:hunt:{task.archetype_label}",
    )

    extracted = invoke_structured_with_fallback(
        [
            extract_instructions.format(
                archetype_label=task.archetype_label,
                geography_scope=task.geography_scope,
                notes=notes,
            )
        ],
        CandidateFinding,
        log_label=f"get_competitors:extract:{task.archetype_label}",
    )

    # The schema is a single candidate; the prompt asks for a list, so accept
    # either shape. A model returning one finding where a list was requested is a
    # shape mismatch, not an empty result, and must not read as "found nothing".
    if isinstance(extracted, CandidateFinding):
        candidates = [extracted]
    elif isinstance(extracted, list):
        candidates = [c for c in extracted if isinstance(c, CandidateFinding)]
    else:  # pragma: no cover -- defensive
        candidates = []
    bundle.candidates = candidates[:MAX_CANDIDATES_PER_TASK]
    print(
        f"hunt_candidates: {task.archetype_label}: {len(bundle.candidates)} candidate(s) "
        f"from {len(issued)} query/queries"
    )
    return bundle


def hunt_candidates(state: CompetitorSessionState) -> dict:
    tasks = list(state.get("competitor_hunt_tasks") or [])
    if not tasks:
        print("hunt_candidates: no tasks")
        return {"competitor_hunt_bundles": []}

    with ThreadPoolExecutor(max_workers=min(len(tasks), MAX_HUNT_TASKS)) as pool:
        bundles = list(pool.map(_hunt_one, tasks))

    total = sum(len(b.candidates) for b in bundles)
    print(f"hunt_candidates: {total} raw candidate(s) across {len(bundles)} task(s)")
    return {"competitor_hunt_bundles": bundles}


# ---------------------------------------------------------------------------
# Node 3: the hard website filter
# ---------------------------------------------------------------------------


def screen_candidates(state: CompetitorSessionState) -> dict:
    """Drop every candidate without a usable public website, then dedup.

    This is the brief's hard filter, and it runs BEFORE anything is written rather
    than as a constraint on write. A rival with no findable site cannot be
    verified, cannot be monitored, and cannot be re-found on the next run -- it
    would be a row that could never be checked or refreshed. Storing it would
    trade an honest gap for a permanent liability.

    Drop reasons are counted rather than discarded silently. "No public website"
    dominating the tally is the filter WORKING, and the run reports it so a thin
    result is not mistaken for a failed search.
    """
    bundles = list(state.get("competitor_hunt_bundles") or [])
    own = _self_domain(state)

    survivors: list[dict] = []
    seen_domains: set[str] = set()
    reasons: dict[str, int] = {}
    candidates_seen = 0

    def drop(reason: str) -> None:
        reasons[reason] = reasons.get(reason, 0) + 1

    for bundle in bundles:
        for candidate in bundle.candidates or []:
            candidates_seen += 1
            website = _clean_website(candidate.website)

            if not website:
                drop("no_public_website")
                continue

            domain = _domain_key(website)
            if own and domain == own:
                # Our own site came back for a category query. Not a competitor.
                drop("is_the_offer_itself")
                continue
            if domain in seen_domains:
                # Two archetypes can surface the same firm; it is one company.
                drop("duplicate_in_this_run")
                continue

            seen_domains.add(domain)
            survivors.append(
                {
                    "name": candidate.name,
                    "website": website,
                    "domain_key": domain,
                    "matched_archetype": bundle.archetype_label,
                    "geography_scope": bundle.geography_scope,
                    "geography_hint": candidate.geography_hint,
                    "evidence_urls": candidate.evidence_urls,
                    "why_it_might_match": candidate.why_it_might_match,
                    "search_failed": bundle.search_failed,
                    "queries": list(bundle.queries or []),
                    "sources": list(bundle.sources or []),
                }
            )

    survivors = survivors[:MAX_CANDIDATES_PER_RUN]
    if len(survivors) > MAX_CANDIDATES_PER_RUN:
        reasons["over_per_run_cap"] = len(survivors) - MAX_CANDIDATES_PER_RUN
        survivors = survivors[:MAX_CANDIDATES_PER_RUN]

    outcome = CompetitorRunOutcome(
        candidates_seen=candidates_seen,
        found=len(survivors),
        dropped=candidates_seen - len(survivors),
        dropped_reasons=reasons,
    )
    print(
        f"screen_candidates: {candidates_seen} seen -> {len(survivors)} kept "
        f"({outcome.dropped} dropped: {reasons or 'none'})"
    )
    return {"competitor_survivors": survivors, "competitor_outcome": outcome}


# ---------------------------------------------------------------------------
# Node 4: profile each survivor
# ---------------------------------------------------------------------------


def _gather_profile_evidence(survivor: dict) -> tuple[str, str]:
    """Everything retrievable about one firm, as notes for the profiling call.

    Two sources, and both matter. The pages that MENTION the firm carry the third
    party's read of it -- pricing comparisons, review roundups, "alternatives to
    X" listicles -- which is where customer sentiment and pain signals actually
    live. The company's OWN site carries what it claims about itself, which is
    where socials, pricing and geography come from. Neither source can be
    substituted for the other, so both are collected and labelled.
    """
    cfg = get_settings()
    chunks: list[str] = []
    seen: set[str] = set()

    for doc in survivor.get("sources") or []:
        url = doc.get("url") or ""
        text = (doc.get("text") or "").strip()
        if not url or url in seen or not text:
            continue
        seen.add(url)
        chunks.append(f"[third-party page] {url}\n{text[:4000]}")

    site_text = ""
    try:
        site_text = call_with_timeout(lambda: scrape_url(survivor["website"], cfg), _SCRAPE_TIMEOUT_S, default="", label=f"scrape[{survivor['website']}]") or ""
    except Exception as exc:  # noqa: BLE001 -- many sites block scrapers
        print(f"profile_competitors: could not read {survivor['website']} -> {exc}")
    if site_text.strip():
        chunks.append(f"[the company's own site] {survivor['website']}\n{site_text[:8000]}")

    evidence = "\n\n".join(chunks)
    if not evidence:
        # Nothing retrievable at all. The firm still passed the website filter --
        # the site exists, it just would not serve text -- so it stays, and the
        # profiler is told it has nothing to work from rather than being handed
        # an empty prompt that invites it to fill the gap from memory.
        evidence = (
            "[no retrievable material: the site returned no readable text and no "
            "third-party page was captured]"
        )
    return evidence, site_text


def _profile_one(survivor: dict, offer: dict) -> Optional[CompetitorProfile]:
    """Deep-research one surviving firm into a sourced profile.

    Returns None when the profile cannot be built at all, which is different from
    a profile full of gaps: a company with no readable site and no third-party
    mention cannot be described honestly even as "mostly unknown", and storing
    that would be a row of nulls pretending to be research.
    """
    evidence, site_text = _gather_profile_evidence(survivor)
    if evidence.startswith("[no retrievable material"):
        print(f"profile_competitors: dropping {survivor['name']} -- nothing retrievable")
        return None

    noun = "service" if offer.get("offer_type") == "service" else "product"
    user_message = (
        f"Company: {survivor['name']}\n"
        f"Website: {survivor['website']}\n"
        f"Archetype: {survivor.get('matched_archetype')}\n\n"
        f"The user's {noun}:\n"
        f"  name: {offer.get('offer_name')}\n"
        f"  description: {offer.get('offer_description')}\n"
        f"  problem: {offer.get('problem')}\n"
        f"  solution: {offer.get('solution')}\n"
        f"  differentiators: {offer.get('features')}\n\n"
        f"Retrieved material:\n{evidence}\n\n"
        f"Build the profile. Cite or record as not-found; do not fill gaps."
    )

    batch = invoke_structured_with_fallback(
        [profile_instructions.format(
            finding_type="sourced findings, each with a quote",
            name=survivor["name"],
            website=survivor["website"],
            archetype=survivor.get("matched_archetype") or "unspecified",
            offer_noun=noun,
            evidence=evidence[:16000],
            site=site_text[:6000] or "(could not read)",
        ), user_message],
        CompetitorProfile,
        log_label=f"get_competitors:profile:{survivor['name']}",
    )

    profile = batch if isinstance(batch, CompetitorProfile) else None
    if profile is None:
        print(f"profile_competitors: {survivor['name']} produced no profile")
        return None

    # The website is the one field the agent does not get a vote on. The screening
    # stage already verified it; letting a model re-assert a possibly social URL
    # here could undo that filter at the last step.
    profile.website = survivor["website"]
    profile.name = survivor.get("name") or profile.name or _domain_key(survivor["website"])
    profile.matched_archetype = profile.matched_archetype or survivor.get("matched_archetype")

    # Merge in the hunt's own evidence URLs so a field the profiler cited from a
    # directory listing is still auditable after the third-party pages are gone.
    merged = dict(profile.evidence or {})
    for url in survivor.get("evidence_urls") or []:
        if url:
            merged.setdefault("identity", []).append(url)
    profile.evidence = merged

    found = len(profile.strengths) + len(profile.weaknesses) + len(profile.pain_signals) + len(profile.customer_sentiment)
    print(
        f"profile_competitors: {profile.name} -- {len(profile.strengths)} strength(s), "
        f"{len(profile.weaknesses)} weakness(es), {len(profile.pain_signals)} pain signal(s), "
        f"{len(profile.opportunities)} opportunit(ies), {len(profile.tracking_sources)} social(s), "
        f"{len(profile.unsourced_fields)} field(s) not found"
    )
    if not found and not profile.opportunities:
        print(f"profile_competitors: {profile.name} yielded nothing -- dropping")
        return None
    return profile


def profile_competitors(state: CompetitorSessionState) -> dict:
    """Profile every survivor, in parallel."""
    survivors = list(state.get("competitor_survivors") or [])
    if not survivors:
        print("profile_competitors: nothing survived screening")
        return {"competitor_profiles": []}

    offer = {
        "offer_type": state.get("offer_type"),
        "offer_name": state.get("offer_name"),
        "offer_description": state.get("offer_description"),
        "problem": state.get("problem"),
        "solution": state.get("solution"),
        "features": state.get("features"),
        "own_website": state.get("own_website"),
    }

    with ThreadPoolExecutor(max_workers=PROFILE_WORKERS) as pool:
        results = list(pool.map(lambda s: _profile_one(s, offer), survivors))

    profiles = [p for p in results if p is not None]
    print(f"profile_competitors: {len(profiles)} profile(s) built from {len(survivors)} survivor(s)")
    return {"competitor_profiles": profiles}


# ---------------------------------------------------------------------------
# Graph
# ---------------------------------------------------------------------------


def build_competitors_graph():
    """plan -> hunt -> screen -> profile. Persistence happens in the caller.

    No LangGraph checkpointer: a run is a background job whose outcome the API
    records on its own `competitor_runs` row, so there is no graph state to resume
    and nothing for a checkpointer to protect. The run row IS the resume point.
    """
    builder = StateGraph(CompetitorSessionState)
    builder.add_node("plan_hunt", timed_node(plan_hunt))
    builder.add_node("hunt_candidates", timed_node(hunt_candidates))
    builder.add_node("screen_candidates", timed_node(screen_candidates))
    builder.add_node("profile_competitors", timed_node(profile_competitors))

    builder.add_edge(START, "plan_hunt")
    builder.add_edge("plan_hunt", "hunt_candidates")
    builder.add_edge("hunt_candidates", "screen_candidates")
    builder.add_edge("screen_candidates", "profile_competitors")
    builder.add_edge("profile_competitors", END)

    return builder.compile()


# ---------------------------------------------------------------------------
# The two seams the backend drives
# ---------------------------------------------------------------------------
#
# Everything below the graph is PURE: web search, scraping and LLM calls, and no
# database. The dependency direction in this repo runs backend -> agents and
# nothing in `agents/` imports `backend/`, so the agent cannot read its own offer
# or write its own rows. The backend hydrates the state from the workspace and
# persists what comes back. Two pure functions mark that seam: `state_from_`
# builds the state from plain dicts, and `row_values_from_profile` turns a
# profile into column values. Neither needs a session, and both are the only
# place the agent and the schema have to agree on a shape.


def state_from_workspace(
    *,
    offer_name: str,
    offer_type: Optional[str] = None,
    offer_description: Optional[str] = None,
    problem: Optional[str] = None,
    solution: Optional[str] = None,
    features: Optional[list[str]] = None,
    own_website: Optional[str] = None,
    ideal_competitor_profile: Optional[dict] = None,
    target_market: Optional[list[str]] = None,
) -> CompetitorSessionState:
    """Build the initial state from a workspace's persisted offer.

    Takes plain values rather than ORM rows so it can be called from either side
    and tested without a database.

    Raises on a missing profile, deliberately and early. Everything downstream
    is shaped by the archetypes -- how many hunts run, which geographies are
    covered, which local-vs-global verdicts are even considered. Without them the
    run would fall back to a generic "find competitors" search, which returns
    listicles and files SEO pages as companies. Refusing here makes the missing
    dependency a clear error instead of a quiet, wrong run.
    """
    if not offer_name:
        raise ValueError("get_competitors: the workspace has no offer name to hunt against")
    if not _archetype_rows(ideal_competitor_profile):
        raise ValueError(
            "get_competitors: no ideal competitor profile. The competition stage "
            "produces it; run discovery before hunting for competitors."
        )

    return {
        "offer_type": offer_type,
        "offer_name": offer_name,
        "offer_description": offer_description or "",
        "problem": problem,
        "solution": solution,
        "features": list(features or []),
        "own_website": own_website,
        "ideal_competitor_profile": ideal_competitor_profile,
        "target_market": list(target_market or []),
    }


# Column-name -> profile-attribute, for the fields that are stored as they come
# off the profile. Kept explicit rather than model_dump-and-prune: this mapping
# is the contract between the agent and the table, and a silent prune that
# started dropping a field would be invisible on both sides.
_TEXT_FIELDS = (
    "description",
    "offering",
    "positioning",
    "business_model",
    "pricing",
    "target_customers",
    "headquarters",
    "geography_scope",
    "comparison",
    "matched_archetype",
)
_LIST_FIELDS = ("opportunities", "notable_customers")

# Every field a profile would research. Used to mark an UNPROFILED competitor as
# wholly not-yet-researched, so it renders as "not found" throughout rather than
# as a profile that legitimately found nothing in any of them.
_PROFILE_FIELDS = (
    *_TEXT_FIELDS,
    *_LIST_FIELDS,
    "strengths",
    "weaknesses",
    "pain_signals",
    "customer_sentiment",
    "tracking_sources",
)


def row_values_from_profile(profile: CompetitorProfile) -> dict:
    """A profile as the `competitors` table's column values.

    Every researched claim is flattened from `{text, evidence, source_url}` into
    the flat shape the column stores, with the URLs lifted into `evidence` so
    nothing is lost: the quote survives in the flat field and the page it came
    from survives in the audit map, which is enough to re-check any single line
    without keeping the nested structure around it.
    """
    def flatten(items: list[SourcedFinding]) -> list[dict]:
        # Keyed `text`, matching CompetitorProfile. pain_signals is the one field
        # the frontend models as {pain, evidence, source_url} -- PainSignal -- so
        # the UI maps that one field and would find no `pain` key here.
        return [
            {"text": i.text, "evidence": i.evidence, "source_url": i.source_url}
            for i in items
        ]

    values: dict = {
        "name": profile.name,
        "website": profile.website,
        "domain_key": _domain_key(profile.website),
        "strengths": flatten(profile.strengths),
        "weaknesses": flatten(profile.weaknesses),
        "pain_signals": flatten(profile.pain_signals),
        "customer_sentiment": flatten(profile.customer_sentiment),
        "tracking_sources": [s.model_dump() for s in profile.tracking_sources],
        "evidence": dict(profile.evidence or {}),
        "unsourced_fields": list(profile.unsourced_fields or []),
    }
    for field in _TEXT_FIELDS:
        values[field] = getattr(profile, field, None)
    for field in _LIST_FIELDS:
        values[field] = list(getattr(profile, field, None) or [])

    # Fold each finding's own source into the evidence map for its category, so
    # `evidence["weaknesses"]` is actually answerable rather than empty whenever
    # the profiler cited inline but did not populate the map.
    for category, items in (
        ("strengths", profile.strengths),
        ("weaknesses", profile.weaknesses),
        ("pain_signals", profile.pain_signals),
        ("customer_sentiment", profile.customer_sentiment),
    ):
        urls = [i.source_url for i in items if i.source_url]
        if urls:
            merged = list(dict.fromkeys([*values["evidence"].get(category, []), *urls]))
            values["evidence"][category] = merged

    # A field the profiler filled is by definition sourced, whatever it put in
    # the evidence map. Dropping it from unsourced_fields here stops the two from
    # contradicting each other -- "pricing: not found" beside a filled-in price
    # is worse than either alone.
    filled = {f for f in _TEXT_FIELDS if values.get(f)}
    for field in _LIST_FIELDS:
        if values.get(field):
            filled.add(field)
    for field in ("strengths", "weaknesses", "pain_signals", "customer_sentiment", "tracking_sources"):
        if values.get(field):
            filled.add(field)
    values["unsourced_fields"] = [f for f in profile.unsourced_fields if f not in filled]

    return values


def surviving_row_values(state: CompetitorSessionState) -> list[dict]:
    """Rows for candidates that survived screening but could not be profiled.

    The brief drops a candidate with no website; it does not drop one whose site
    simply would not serve text or whose profile came back empty. A named
    competitor with a verified site is still a competitor the user asked to track,
    so it is stored with its fields declared unsourced -- visible as "not
    researched yet" rather than silently absent, which would understate what the
    run actually found.
    """
    profiled = {p.website for p in state.get("competitor_profiles") or []}
    rows: list[dict] = []
    for survivor in state.get("competitor_survivors") or []:
        if survivor["website"] in profiled:
            continue
        rows.append(
            {
                "name": survivor.get("name") or survivor["domain_key"],
                "website": survivor["website"],
                "domain_key": survivor["domain_key"],
                "description": None,
                "offering": None,
                "positioning": None,
                "business_model": None,
                "pricing": None,
                "target_customers": None,
                "headquarters": None,
                "geography_scope": survivor.get("geography_scope"),
                "comparison": None,
                "matched_archetype": survivor.get("matched_archetype"),
                "strengths": [],
                "weaknesses": [],
                "opportunities": [],
                "notable_customers": [],
                "pain_signals": [],
                "customer_sentiment": [],
                "tracking_sources": [],
                "evidence": {"identity": list(survivor.get("evidence_urls") or [])},
                "unsourced_fields": list(_PROFILE_FIELDS),
            }
        )
    return rows
