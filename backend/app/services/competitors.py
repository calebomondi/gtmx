"""Tracked competitors: a growing watch list per workspace, filled by the
competitor agent and by the user adding rivals by URL."""

import re
import uuid
from typing import Any
from urllib.parse import urlparse

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.database import models
from backend.app.services.errors import ConflictError, InvalidInputError, NotFoundError

# Only one run may be in flight per workspace: concurrent runs would race on
# the unique (workspace_id, domain_key) and the loser's inserts would fail for
# no reason the user could act on.
ACTIVE_RUN_STATUSES = ("pending", "running")

# A manual row has no research yet; say so in the agent's vocabulary so the UI
# shows "not researched yet" instead of a profile of empty fields.
_UNRESEARCHED_FIELDS = ["description", "offering", "strengths", "weaknesses"]


def normalize_website(website: str) -> str:
    """A bare host ("acme.com") means https://acme.com."""
    website = website.strip()
    if not re.match(r"^https?://", website, re.IGNORECASE):
        website = f"https://{website}"
    return website


def domain_key(website: str) -> str:
    """The host that identifies the firm behind a URL.

    The same rival is reachable at http://acme.com, https://www.acme.com/ and
    https://acme.com/about; deduping on the raw URL would file one company three
    times. Falls back to the lowercased input when there is no parseable host,
    so a malformed URL still yields a stable, non-empty key.
    """
    host = (urlparse(website).netloc or "").strip().lower()
    if not host:
        return website.strip().lower()
    host = host.split("@")[-1]  # drop any userinfo
    host = host.split(":")[0]  # drop the port
    return host.removeprefix("www.").rstrip(".")


async def list_for_workspace(db: AsyncSession, workspace_id: uuid.UUID) -> list[models.Competitor]:
    """Newest first. Rows accumulate across runs (re-runs refresh known firms)."""
    result = await db.execute(
        select(models.Competitor)
        .where(models.Competitor.workspace_id == workspace_id)
        .order_by(models.Competitor.first_seen_at.desc())
    )
    return list(result.scalars().all())


async def count_for_workspace(db: AsyncSession, workspace_id: uuid.UUID) -> int:
    return int(await db.scalar(
        select(func.count()).select_from(models.Competitor).where(models.Competitor.workspace_id == workspace_id)
    ) or 0)


async def get_in_workspace(db: AsyncSession, workspace_id: uuid.UUID, competitor_id: uuid.UUID) -> models.Competitor:
    """Scoped by workspace, so an id from another workspace is a 404."""
    result = await db.execute(
        select(models.Competitor).where(
            models.Competitor.id == competitor_id,
            models.Competitor.workspace_id == workspace_id,
        )
    )
    competitor = result.scalar_one_or_none()
    if competitor is None:
        raise NotFoundError("Competitor not found")
    return competitor


async def _get_by_domain(db: AsyncSession, workspace_id: uuid.UUID, domain: str) -> models.Competitor | None:
    result = await db.execute(
        select(models.Competitor).where(
            models.Competitor.workspace_id == workspace_id,
            models.Competitor.domain_key == domain,
        )
    )
    return result.scalar_one_or_none()


async def add_manual(
    db: AsyncSession, workspace_id: uuid.UUID, website: str, name: str | None
) -> tuple[models.Competitor, bool]:
    """Track a rival the user supplied by URL. Returns (row, created).

    Idempotent: a host already on the list returns the existing row with
    created=False -- adding a rival you already track is not an error.
    """
    website = normalize_website(website)
    domain = domain_key(website)
    existing = await _get_by_domain(db, workspace_id, domain)
    if existing is not None:
        return existing, False

    competitor = models.Competitor(
        workspace_id=workspace_id,
        # Manual, so a later agent run refreshes rather than relabels it.
        source="manual",
        name=(name or domain).strip(),
        website=website,
        domain_key=domain,
        unsourced_fields=list(_UNRESEARCHED_FIELDS),
    )
    db.add(competitor)
    try:
        await db.commit()
    except IntegrityError:
        # Lost a race with a concurrent add of the same host: the row the
        # caller wanted exists, so return it rather than an error.
        await db.rollback()
        existing = await _get_by_domain(db, workspace_id, domain)
        if existing is None:
            raise
        return existing, False
    await db.refresh(competitor)
    return competitor, True


async def update(db: AsyncSession, competitor: models.Competitor, changes: dict[str, Any]) -> models.Competitor:
    """Edit the user-owned fields only (the request schema limits which).
    Researched claims carry sourcing requirements and are never writable here."""
    for required in ("name", "website"):
        if required in changes and not (changes[required] or "").strip():
            raise InvalidInputError(f"A tracked competitor must keep a {required}.")
    if "website" in changes:
        changes["website"] = normalize_website(changes["website"])
        changes["domain_key"] = domain_key(changes["website"])
    for field, value in changes.items():
        setattr(competitor, field, value)
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise ConflictError("Another tracked competitor already uses that website")
    await db.refresh(competitor)
    return competitor


async def delete(db: AsyncSession, competitor: models.Competitor) -> None:
    """Hard delete: keeping tombstones for rivals the user removed would make
    'tracked' mean something other than what it says."""
    await db.delete(competitor)
    await db.commit()


async def list_runs(db: AsyncSession, workspace_id: uuid.UUID, limit: int) -> list[models.CompetitorRun]:
    result = await db.execute(
        select(models.CompetitorRun)
        .where(models.CompetitorRun.workspace_id == workspace_id)
        .order_by(models.CompetitorRun.created_at.desc())
        .limit(max(1, min(limit, 100)))
    )
    return list(result.scalars().all())


async def get_run(db: AsyncSession, workspace_id: uuid.UUID, run_id: uuid.UUID) -> models.CompetitorRun:
    result = await db.execute(
        select(models.CompetitorRun).where(
            models.CompetitorRun.id == run_id,
            models.CompetitorRun.workspace_id == workspace_id,
        )
    )
    run = result.scalar_one_or_none()
    if run is None:
        raise NotFoundError("Competitor run not found")
    return run


async def active_run(db: AsyncSession, workspace_id: uuid.UUID) -> models.CompetitorRun | None:
    result = await db.execute(
        select(models.CompetitorRun).where(
            models.CompetitorRun.workspace_id == workspace_id,
            models.CompetitorRun.status.in_(ACTIVE_RUN_STATUSES),
        )
    )
    return result.scalars().first()


async def ideal_profile(db: AsyncSession, workspace_id: uuid.UUID) -> dict | None:
    """The competition stage's archetype profile from the persisted insights --
    the only place it survives a finished discovery run."""
    insights = await db.scalar(
        select(models.ProductProfile.insights).where(models.ProductProfile.workspace_id == workspace_id)
    )
    return (insights or {}).get("ideal_competitor_profile") or None


async def create_run(db: AsyncSession, workspace_id: uuid.UUID) -> models.CompetitorRun:
    """Record a pending run. Requires a finished discovery run, because the
    agent hunts with the ideal competitor profile that run produces."""
    profile = await ideal_profile(db, workspace_id)
    if profile is None:
        raise ConflictError(
            "This workspace has no ideal competitor profile yet. Complete "
            "discovery first -- the competitor agent searches using it."
        )
    run = models.CompetitorRun(
        workspace_id=workspace_id,
        status="pending",
        profile_confidence=profile.get("confidence"),
        archetypes_targeted=len(profile.get("archetypes") or []),
    )
    db.add(run)
    await db.commit()
    await db.refresh(run)
    return run
