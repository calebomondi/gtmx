"""Exercise the competitor agent's screening and persistence logic, stubbed.

No network and no tokens: `search_and_scrape`, `scrape_url`, the distiller and
the LLM are all replaced with canned answers. What is under test is the logic
that decides which companies are allowed to become tracked rows -- the website
filter, the self-exclusion, the dedup, the drop reasons, and the row mapping --
because that is the part where a plausible-looking wrong answer becomes a
fabricated competitor on someone's list.

Run directly (pytest is not installed in this venv):
    PYTHONPATH=/home/mokuaxv/gtmx2/gtmx .venv/bin/python \
        agents/tests/pipelines/dry_run_get_competitors.py
"""

import asyncio


PASS: list[str] = []
_real_search_and_scrape = None


def check(label: str, condition: bool, detail: str = "") -> None:
	if not condition:
		raise AssertionError(f"{label}{(' -- ' + detail) if detail else ''}")
	PASS.append(label)


# ---------------------------------------------------------------------------
# Stub the network and the LLM BEFORE importing the agent, so the agent's own
# module-level imports resolve to these and nothing reaches out.
# ---------------------------------------------------------------------------

PROFILE_CALLS: list[dict] = []


def _stub_search(query, config, num_results=5, start_published_date=None):
	return [
        {"url": "https://directory.example/list", "title": "Rivals", "text": "canned"}
    ]


def _stub_scrape(url, config):
    return f"[site] {url}\ncanned site text"


def _stub_distill(docs, focus, log_label="distill_document"):
    return "canned notes naming Acme and Globex"


def _candidate(name, website, **kw):
    from agents.schemas.competition import CandidateFinding

    return CandidateFinding(name=name, website=website, **kw)


class _Bundle:
    def __init__(self, archetype, geo, candidates):
        self.archetype_label = archetype
        self.geography_scope = geo
        self.candidates = candidates
        self.search_failed = False
        self.queries = ["q"]
        self.sources = [{"url": "https://directory.example/list", "text": "canned"}]


def _fake_llm(messages, schema=None, **kw):
    """Answer the two call shapes the pipeline makes.

    Returns REAL model instances. The agent filters its extraction result with
    isinstance, so a stub returning look-alikes would be silently discarded --
    which is the filter working, and the reason this stub builds real ones.
    """
    name = getattr(schema, "__name__", "")
    if name == "CompetitorRelevance":
        from agents.schemas.competition import CompetitorRelevance

        return CompetitorRelevance(offer_job="x", their_job="x", same_buyer=True, substitute=True)
    if name == "CompetitorHuntPlan":
        return schema(
            tasks=[
                _task(
                    "Local incumbent",
                    "local",
                    ["vector database companies Kenya", "alternatives to Heather"],
                ),
                _task(
                    "Global incumbent",
                    "global",
                    ["enterprise vector database vendors"],
                ),
            ]
        )
    if name == "CandidateFindingList":
        from agents.schemas.competition import CandidateFindingList

        return CandidateFindingList(candidates=[
            _candidate("Acme Vector", "https://acme.com", evidence_urls=["https://directory.example/list"]),
            _candidate("Acme Vector", "https://www.acme.com/about"),  # dup spelling
            _candidate("Globex", "https://globex.io"),
            _candidate("Heather", "https://heather.dev"),  # the offer itself
            _candidate("No Site Co", None),  # no website -> dropped
            _candidate("Directory Entry", "https://g2.com/products/nosite"),
            _candidate("Social Only", "https://linkedin.com/company/socialonly"),
            _candidate("Plausible But Invented", "https://acme-vector-db.io"),
        ])
    if name == "CompetitorProfile":
        PROFILE_CALLS.append({"messages": messages})
        return _profile()
    return None


def _install_stubs():
    import data_sources.scraping.exa as exa

    exa.search_and_scrape = _stub_search
    exa.scrape_url = _stub_scrape

    import agents.context_budget as cb

    cb.distill_documents = _stub_distill

    import agents.pipelines.competitors.get_competitors as gc

    gc.search_and_scrape = _stub_search
    gc.scrape_url = _stub_scrape
    gc.social_profiles.find_on_site = lambda website, name: {}
    gc.distill_documents = _stub_distill

    gc.invoke_structured_with_fallback = _fake_llm
    global _real_search_and_scrape
    _real_search_and_scrape = gc._search_and_scrape


def _task(label, geo, queries):
    from agents.schemas.competition import CompetitorHuntTask

    return CompetitorHuntTask(
        archetype_label=label, geography_scope=geo, objective="find them", queries=queries
    )


def _profile():
    from agents.schemas.competition import CompetitorProfile, SourcedFinding

    return CompetitorProfile(
        name="Acme Vector",
        website="https://acme.com",
        description="A vector database",
        pricing="$99/mo",
        strengths=[SourcedFinding(text="fast", evidence="\"2ms p99\"", source_url="https://acme.com/bench")],
        weaknesses=[SourcedFinding(text="no SSO", evidence="docs omit SSO", source_url="https://acme.com/docs")],
        opportunities=["Undercut on price: they list $99/mo"],
        pain_signals=[SourcedFinding(text="slow dashboard", evidence="\"dashboard hangs\"", source_url="https://news.example")],
        customer_sentiment=[SourcedFinding(text="liked by devs", evidence="\"great DX\"", source_url="https://blog.example")],
        tracking_sources=[
            {"kind": "linkedin", "value": "https://linkedin.com/company/acme", "confidence": "high"},
            {"kind": "tiktok", "value": "https://tiktok.com/@acme", "confidence": "low"},
        ],
        evidence={"pricing": ["https://acme.com/pricing"]},
        # `pricing` and `description` WERE filled, to prove the contradiction is
        # cleaned up. `business_model` and `headquarters` were NOT, to prove a
        # genuine gap survives into the row.
        unsourced_fields=["pricing", "description", "business_model", "headquarters"],
    )


def _state(**kw):
    base = {
        "offer_type": "product",
        "offer_name": "Heather",
        "offer_description": "A vector DB",
        "problem": "slow search",
        "solution": "fast search",
        "features": ["low latency"],
        "own_website": "https://heather.dev",
        "ideal_competitor_profile": {
            "category_definition": "vector databases",
            "archetypes": [
                {"label": "Local incumbent", "geography_scope": "local"},
                {"label": "Global incumbent", "geography_scope": "global"},
            ],
            "confidence": "high",
        },
    }
    base.update(kw)
    return base


async def main() -> None:
    _install_stubs()
    import agents.pipelines.competitors.get_competitors as gc

    # -- plan_hunt: brand-free enforcement --------------------------------
    planned = gc.plan_hunt(_state())
    tasks = planned["competitor_hunt_tasks"]
    check("planner produced tasks", len(tasks) >= 1, str(tasks))
    all_queries = [q for t in tasks for q in t.queries]
    check(
        "no query names the offer",
        not any("Heather" in q for q in all_queries),
        str(all_queries),
    )
    check(
        "the branded comparison query was dropped",
        not any("alternatives" in q.lower() for q in all_queries),
        str(all_queries),
    )
    check(
        "category queries survive",
        any("vector database" in q for q in all_queries),
        str(all_queries),
    )

    # -- hunt + screen ----------------------------------------------------
    hunted = gc.hunt_candidates({**_state(), "competitor_hunt_tasks": tasks})
    check("hunt produced bundles", len(hunted["competitor_hunt_bundles"]) >= 1)

    screened = gc.screen_candidates({**_state(), **hunted})
    outcome = screened["competitor_outcome"]
    survivors = screened["competitor_survivors"]
    kept = {s["domain_key"] for s in survivors}

    check(
        "the offer itself is not kept as a competitor",
        "heather.dev" not in kept,
        str(kept),
    )
    check("a real rival is kept", "acme.com" in kept, str(kept))
    check("a second real rival is kept", "globex.io" in kept, str(kept))
    check(
        "a candidate with no website is dropped",
        not any("nosite" in k for k in kept),
        str(kept),
    )
    check(
        "a directory URL is not accepted as a website",
        not any("g2.com" in k for k in kept),
        str(kept),
    )
    check(
        "a social URL is not accepted as a website",
        not any("linkedin" in k for k in kept),
        str(kept),
    )
    check(
        "the same firm under two URL spellings is one row",
        len([s for s in survivors if s["domain_key"] == "acme.com"]) == 1,
        str([s["domain_key"] for s in survivors]),
    )
    check("drop reasons were counted", bool(outcome.dropped_reasons), str(outcome.dropped_reasons))
    check(
        "no-website is the top drop reason",
        outcome.dropped_reasons.get("no_public_website", 0) >= 3,
        str(outcome.dropped_reasons),
    )
    check(
        "self-exclusion is recorded",
        outcome.dropped_reasons.get("is_the_offer_itself", 0) >= 1,
        str(outcome.dropped_reasons),
    )
    check(
        "counts are internally consistent",
        outcome.candidates_seen == outcome.found + outcome.dropped,
        f"{outcome.candidates_seen} != {outcome.found} + {outcome.dropped}",
    )

    # -- profile ----------------------------------------------------------
    profiled = gc.profile_competitors(
        {**_state(), "competitor_survivors": survivors}
    )
    profiles = profiled["competitor_profiles"]
    check("at least one profile was built", len(profiles) >= 1)

    acme = next((p for p in profiles if "acme.com" in p.website), None)
    check("the profiled competitor is the one kept", acme is not None)
    if acme:
        check(
            "the profiler cannot change the website",
            acme.website == "https://acme.com",
            acme.website,
        )
        check("strengths kept their evidence", acme.strengths[0].evidence == '"2ms p99"')
        check("weaknesses kept their evidence", acme.weaknesses[0].evidence == "docs omit SSO")
        check(
            "opportunities exist even with pain signals",
            len(acme.opportunities) >= 1,
            str(acme.opportunities),
        )
        check("socials captured", len(acme.tracking_sources) == 2)
        check(
            "the hunt's own evidence URL survived into the row",
            "https://directory.example/list" in acme.evidence.get("identity", []),
            str(acme.evidence),
        )

    # -- opportunities with NO pain signals, which the brief requires -------
    def _no_pain(messages, schema=None, **kw):
        from agents.schemas.competition import CompetitorProfile, CompetitorRelevance

        if schema is CompetitorRelevance:
            return CompetitorRelevance(offer_job="x", their_job="x", same_buyer=True, substitute=True)

        return CompetitorProfile(
            name="Quiet Co",
            website="https://quiet.com",
            strengths=[],
            weaknesses=[],
            opportunities=["They ship no mobile app; we could ship one"],
            pain_signals=[],
            customer_sentiment=[],
            tracking_sources=[],
            unsourced_fields=["pricing"],
        )

    gc.invoke_structured_with_fallback = _no_pain
    surv = [{
        "name": "Quiet Co", "website": "https://quiet.com", "domain_key": "quiet.com",
        "matched_archetype": "Local incumbent", "geography_scope": "local",
        "evidence_urls": [], "sources": [{"url": "https://d.example", "text": "x"}],
    }]
    only = gc.profile_competitors({**_state(), "competitor_survivors": surv})
    check(
        "a competitor with no pain signals is still profiled",
        len(only["competitor_profiles"]) == 1,
    )
    if only["competitor_profiles"]:
        p = only["competitor_profiles"][0]
        check("its opportunity survived", len(p.opportunities) == 1, str(p.opportunities))
        check("its empty pain list stayed empty", p.pain_signals == [])

    # -- a firm with nothing retrievable is dropped, not stored blank ------
    def _no_read(url, config):
        raise ValueError("403 blocked")

    gc.scrape_url = _no_read
    gc.invoke_structured_with_fallback = _fake_llm
    # An unreadable site falls back to search; with search empty too, there is
    # nothing to profile from.
    gc._search_and_scrape = lambda *a, **k: []
    dropped = gc.profile_competitors(
        {**_state(), "competitor_survivors": [surv[0] | {"sources": []}]}
    )
    gc._search_and_scrape = _real_search_and_scrape
    check(
        "a firm with nothing readable anywhere yields no profile",
        dropped["competitor_profiles"] == [],
        str(dropped["competitor_profiles"]),
    )

    # -- row mapping ------------------------------------------------------
    gc.invoke_structured_with_fallback = _fake_llm
    full = gc.profile_competitors({**_state(), "competitor_survivors": survivors})
    if full["competitor_profiles"]:
        values = gc.row_values_from_profile(full["competitor_profiles"][0])
        check("row has a website", bool(values["website"]))
        check("row has a dedup key", values["domain_key"] == "acme.com", values["domain_key"])
        check(
            "findings flattened with their evidence",
            values["weaknesses"][0]["text"] == "no SSO"
            and values["weaknesses"][0]["evidence"] == "docs omit SSO",
            str(values["weaknesses"]),
        )
        check(
            "finding sources lifted into the evidence map",
            "https://acme.com/docs" in values["evidence"].get("weaknesses", []),
            str(values["evidence"]),
        )
        check(
            "a filled field is dropped from unsourced_fields",
            "pricing" not in values["unsourced_fields"]
            and "description" not in values["unsourced_fields"],
            str(values["unsourced_fields"]),
        )
        check(
            "a genuinely unfilled field stays declared unsourced",
            "business_model" in values["unsourced_fields"]
            and "headquarters" in values["unsourced_fields"],
            str(values["unsourced_fields"]),
        )
        check(
            "no identity/provenance field is emitted for the runner",
            not ({"source", "notes", "first_seen_at", "run_id", "id"} & set(values)),
            str(sorted(values)),
        )

    # -- state_from_workspace refuses to hunt without a shape --------------
    for missing, label in [
        ({"ideal_competitor_profile": None}, "no profile"),
        ({"ideal_competitor_profile": {"archetypes": []}}, "an empty profile"),
        ({"offer_name": ""}, "no offer name"),
    ]:
        try:
            gc.state_from_workspace(**{**_state(), **missing})
        except ValueError:
            PASS.append(f"state_from_workspace refuses {label}")
        else:
            raise AssertionError(f"state_from_workspace accepted {label}")

    gc.state_from_workspace(**_state())
    PASS.append("state_from_workspace accepts a complete workspace")

    print()
    for label in PASS:
        print(f"  ok  {label}")
    print(f"\nget_competitors screening OK ({len(PASS)} checks)")


if __name__ == "__main__":
    asyncio.run(main())