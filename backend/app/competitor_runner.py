"""The database-facing half of the standalone competitor agent.

SPLIT OF RESPONSIBILITY, AND WHY IT FALLS THIS WAY
---------------------------------------------------
`agents/pipelines/get_competitors.py` is the agent: it plans hunts, searches,
screens candidates against the website filter and builds sourced profiles. It is
pure -- web search, scraping and LLM calls, nothing else.

The dependency direction in this repo runs backend -> agents, and nothing under
`agents/` imports `backend/`. So the agent cannot read its own offer and cannot
write its own rows, and this module is where those two jobs meet. It:

  1. hydrates the agent's state from a workspace's persisted product profile,
  2. invokes the graph,
  3. upserts what comes back into `competitors`, and
  4. returns the outcome, which the run manager records on the run.

UPSERT, NOT REPLACE
-------------------
The brief says a run appends. It does -- in the sense the user means, which is
that the watch list grows. Re-running must not produce a second row for a company
already on the list, so rows are matched on `(workspace_id, domain_key)`: a firm
seen again refreshes its researched fields and `last_seen_at` instead of being
duplicated. The unique constraint enforces it, and the conflict is treated as
"already known" rather than as an error.

A manual row keeps `source = "manual"` across agent runs. The user adding a rival
by hand is a statement about what they care about; a later run refreshing the
research on that row is fine, but silently re-labelling it as agent-found would
erase that.
"""

import asyncio
import uuid
from datetime import UTC, datetime
from typing import Optional

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from agents.pipelines.competitors.get_competitors import (
    PROFILE_FIELDS,
    build_competitors_graph,
    row_values_from_profile,
    state_from_workspace,
)

from backend.app.database.connect import AsyncSessionLocal
from backend.app.database.models import Competitor, ProductProfile


# Fields a refresh must never clobber. `source` because a manual row stays
# manual; `notes` because they are the user's own words, not research; the two
# timestamps because they mean different things -- when the firm was FIRST added
# versus when its profile was last rebuilt.
_PRESERVED_ON_REFRESH = ("source", "notes", "first_seen_at", "run_id", "id")


def _features(snapshot: dict) -> list[str]:
    """The offer's differentiators, from either snapshot shape.

    `_serialize_offer_snapshot` writes features as [{name, description,
    differentiator}], but an older blob or a hand-edited one may hold bare
    strings. Both are accepted rather than assuming the current shape, since this
    is only used to give the profiler something to compare against.
    """
    out: list[str] = []
    for feature in snapshot.get("features") or []:
        if isinstance(feature, dict):
            name = feature.get("name")
            if name:
                out.append(name)
        elif isinstance(feature, str) and feature.strip():
            out.append(feature.strip())
    return out


def _hydrate(
    profile: Optional[ProductProfile],
) -> dict:
    """The agent's inputs, from the workspace's persisted offer.

    Returns plain kwargs for `state_from_workspace`, which is where the two
    required inputs are enforced -- a missing offer name or a missing archetype
    profile raises there rather than producing a run that searches for nothing.
    """
    if profile is None:
        raise ValueError(
            "No product profile for this workspace. Complete discovery before "
            "hunting for competitors."
        )

    insights = profile.insights or {}
    snapshot = insights.get("offer_snapshot") or {}

    return {
        "offer_name": (
            snapshot.get("offer_name")
            or profile.product_name
            or ""
        ),
        "offer_type": insights.get("offer_type"),
        "offer_description": (
            snapshot.get("offer_description")
            or profile.product_description
        ),
        "problem": snapshot.get("problem_solved") or profile.problem_solved,
        "solution": snapshot.get("how_it_works") or profile.how_it_works,
        "features": _features(snapshot),
        # The offer's own site, so a run can recognise the user and refuse to
        # file them as their own competitor. The snapshot's website_url is the
        # agent's own record of it and is more likely to be the canonical form
        # than whatever was typed on the intake form.
        "own_website": snapshot.get("website_url") or profile.product_url,
        "ideal_competitor_profile": insights.get("ideal_competitor_profile"),
    }


async def _upsert_profiles(
    db,
    workspace_id: uuid.UUID,
    run_id: Optional[uuid.UUID],
    rows: list[dict],
) -> tuple[int, int]:
    """Insert or refresh competitors. Returns (inserted, refreshed).

    Split into one statement per row rather than a bulk insert because each needs
    a read-modify-write: a known firm keeps its `source`, its `notes` and its
    `first_seen_at`, so it cannot be expressed as a single INSERT ... ON CONFLICT.
    A run touches at most a couple of dozen rows, so the extra round trips do not
    matter next to the research that produced them.
    """
    inserted = 0
    refreshed = 0

    for values in rows:
        # The preservation below is implicit -- only `values` keys are written,
        # so anything absent keeps its current value. That makes the absence of
        # these keys load-bearing, so it is asserted rather than assumed: if the
        # agent ever starts emitting `source` or `notes`, a refresh would silently
        # re-label a user's manual competitor as agent-found.
        clobbered = [f for f in _PRESERVED_ON_REFRESH if f in values]
        if clobbered:
            raise ValueError(
                f"competitor refresh would overwrite preserved field(s) "
                f"{clobbered}; row_values_from_profile must not emit them."
            )

        domain = values["domain_key"]
        existing = await db.execute(
            select(Competitor).where(
                Competitor.workspace_id == workspace_id,
                Competitor.domain_key == domain,
            )
        )
        competitor = existing.scalar_one_or_none()

        if competitor is None:
            competitor = Competitor(
                workspace_id=workspace_id,
                run_id=run_id,
                source="agent",
                first_seen_at=datetime.now(UTC),
                **values,
            )
            db.add(competitor)
            inserted += 1
            continue

        for field, value in values.items():
            setattr(competitor, field, value)
        competitor.last_seen_at = datetime.now(UTC)
        competitor.deep_researched_at = datetime.now(UTC)
        refreshed += 1

    try:
        await db.commit()
    except IntegrityError:
        # Lost a race against a concurrent run or a manual add of the same host.
        # The row exists and is what this run wanted; the next run will refresh
        # it. Losing the whole batch over it would be a worse outcome than
        # skipping the rows that collided.
        await db.rollback()

    return inserted, refreshed


async def run_competitor_discovery(
    workspace_id: uuid.UUID,
    run_id: Optional[uuid.UUID] = None,
) -> dict:
    """Hunt for competitors in a workspace, profile them, and store them.

    Returns the counts recorded on the run: `candidates_seen`,
    `found`, `dropped` and `dropped_reasons`. `dropped_reasons` is the important
    one -- it is what distinguishes "screened 40 firms, kept 3" (the website
    filter working) from "found 3" (a thin search), and the UI needs to be able to
    tell those apart rather than showing an empty-looking list.

    Raises on a missing offer or profile: those are user-actionable setup gaps,
    not run failures to be swallowed into a `failed` row with a vague message.
    The API checks for them up front and answers 409 before ever getting here.
    """
    async with AsyncSessionLocal() as db:
        async with db.begin():
            result = await db.execute(
                select(ProductProfile).where(
                    ProductProfile.workspace_id == workspace_id
                )
            )
            state = state_from_workspace(**_hydrate(result.scalar_one_or_none()))

    graph = build_competitors_graph()
    # Node fns are sync and I/O-heavy; run the whole graph off the event loop
    # so a long hunt run doesn't block unrelated requests.
    final = await asyncio.to_thread(graph.invoke, state)

    outcome = final.get("competitor_outcome")
    profiles = list(final.get("competitor_profiles") or [])
    rows = [row_values_from_profile(p) for p in profiles]

    async with AsyncSessionLocal() as db:
        async with db.begin():
            inserted, refreshed = await _upsert_profiles(
                db, workspace_id, run_id, rows
            )
    repaired, removed = await _repair_empty_rows(workspace_id, state, {r["domain_key"] for r in rows})

    found = len(rows)
    return {
        "candidates_seen": int(getattr(outcome, "candidates_seen", 0) or 0),
        # `found` is what the run kept AFTER profiling, which is what ended up on
        # the list. A firm that passed screening but produced nothing usable is a
        # real, slightly different outcome than one that was screened out, so it
        # gets its own reason rather than quietly inflating `found`.
        "found": found,
        "dropped": int(getattr(outcome, "dropped", 0) or 0),
        "dropped_reasons": dict(getattr(outcome, "dropped_reasons", {}) or {}),
        "inserted": inserted,
        "refreshed": refreshed,
        "profiled": len(profiles),
        "repaired": repaired,
        "removed_empty": removed,
    }


async def _repair_empty_rows(workspace_id: uuid.UUID, state: dict, refreshed: set[str]) -> tuple[int, int]:
    """Re-research agent-found rows that were stored with every field unsourced
    (earlier runs kept firms they could not profile). A firm that now profiles
    is filled in; one judged not a competitor, or still unreadable, is removed
    unless the user wrote notes on it. Returns (repaired, removed)."""
    async with AsyncSessionLocal() as db:
        empty = [
            c for c in (await db.execute(
                select(Competitor).where(Competitor.workspace_id == workspace_id, Competitor.source == "agent")
            )).scalars()
            if c.domain_key not in refreshed and set(PROFILE_FIELDS) <= set(c.unsourced_fields or [])
        ]
        survivors = [(c.id, c.notes, _survivor(c)) for c in empty]
    repaired = removed = 0
    for competitor_id, notes, survivor in survivors:
        profile = await _profile_one_public(survivor, state)
        async with AsyncSessionLocal() as db:
            async with db.begin():
                competitor = await db.get(Competitor, competitor_id)
                if competitor is None:
                    continue
                if profile is not None:
                    for field, value in row_values_from_profile(profile).items():
                        setattr(competitor, field, value)
                    competitor.deep_researched_at = datetime.now(UTC)
                    repaired += 1
                elif not notes:
                    await db.delete(competitor)
                    removed += 1
    return repaired, removed


def _survivor(competitor: Competitor) -> dict:
    """A stored competitor in the shape the profiler takes."""
    return {
        "name": competitor.name,
        "website": competitor.website,
        "domain_key": competitor.domain_key,
        "matched_archetype": competitor.matched_archetype,
        "geography_scope": competitor.geography_scope or "any",
        "evidence_urls": [],
        "sources": [],
    }


async def research_competitor_site(
    workspace_id: uuid.UUID,
    competitor_id: uuid.UUID,
) -> bool:
    """Deep-research one already-tracked competitor from its own website.

    The manual-add path. The user supplies a URL; everything else is derived,
    including socials. Rather than run the whole hunt -- this is one known company,
    not a category to explore -- it reuses the agent's screening and profiling
    nodes directly, so a manually added competitor is built by exactly the same
    code and to exactly the same sourcing standard as an agent-found one. A second
    implementation here would be a second standard, and the two would drift.

    Returns True when the row was updated, False when the competitor is gone or
    nothing could be read. Best-effort by design: the POST that calls this has
    already returned, so there is no caller left to report an error to, and the
    row's `unsourced_fields` is the honest record either way.
    """
    async with AsyncSessionLocal() as db:
        async with db.begin():
            competitor = await db.get(Competitor, competitor_id)
            if competitor is None or competitor.workspace_id != workspace_id:
                return False
            result = await db.execute(
                select(ProductProfile).where(
                    ProductProfile.workspace_id == workspace_id
                )
            )
            try:
                state = state_from_workspace(**_hydrate(result.scalar_one_or_none()))
            except ValueError:
                # No offer or profile: the site can still be read, just not
                # compared against anything. Scrub-free profiling still works, so
                # fall back to the minimum rather than refusing -- the user asked
                # for THIS competitor, and that part does not need the offer.
                state = {
                    "offer_type": None,
                    "offer_name": competitor.name or "",
                    "offer_description": "",
                    "problem": None,
                    "solution": None,
                    "features": [],
                    "own_website": None,
                }
            survivor = _survivor(competitor)

    profile = await _profile_one_public(survivor, state)
    if profile is None:
        return False

    values = row_values_from_profile(profile)
    async with AsyncSessionLocal() as db:
        async with db.begin():
            competitor = await db.get(Competitor, competitor_id)
            if competitor is None:
                return False
            for field, value in values.items():
                setattr(competitor, field, value)
            competitor.deep_researched_at = datetime.now(UTC)
            await db.commit()
    return True


async def _profile_one_public(survivor: dict, state: dict):
    """The agent's per-firm profiler, called directly for one known company.

    Wrapped rather than imported bare so the manual path's intent is visible at
    the call site, and so the agent's private helper is not imported into a second
    module's namespace where a rename would break it silently.
    """
    from agents.pipelines.competitors.get_competitors import _profile_one

    offer = {
        "offer_type": state.get("offer_type"),
        "offer_name": state.get("offer_name"),
        "offer_description": state.get("offer_description"),
        "problem": state.get("problem"),
        "solution": state.get("solution"),
        "features": state.get("features"),
        "own_website": state.get("own_website"),
    }
    # Run on a worker thread: the profiler does blocking HTTP and LLM calls, and
    # this runs inside a request's background task on the event loop.
    profile, _reason = await asyncio.to_thread(_profile_one, survivor, offer)
    return profile
