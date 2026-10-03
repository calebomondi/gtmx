import re
import uuid
from datetime import UTC, datetime
from typing import Annotated
from urllib.parse import urlparse

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Response, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.database import models
from backend.app.database.connect import AsyncSessionLocal, get_db
from backend.app.schemas.competitors import (
	CompetitorCreateRequest,
	CompetitorListResponse,
	CompetitorResponse,
	CompetitorRunResponse,
	CompetitorRunStartResponse,
	CompetitorUpdateRequest,
)


router = APIRouter()


# A run is only allowed to be in flight once. A second POST while one is running
# is answered with that run rather than a second agent invocation, because two
# concurrent runs would race on the same unique (workspace_id, domain_key) and
# the loser's inserts would fail for no reason the user could act on.
_ACTIVE_STATUSES = ("pending", "running")


def _domain_key(website: str) -> str:
	"""Normalise a URL to the host that identifies the firm behind it.

	The same rival is reachable at http://acme.com, https://www.acme.com/ and
	https://acme.com/about, and an agent run will surface all three. Deduping on
	the raw URL would file one company three times, so identity is the host with
	the scheme, any `www.`, port and trailing dot removed.

	Falls back to the lowercased input when there is no parseable host, so a
	malformed URL still yields a stable key rather than an empty one that would
	collapse every bad row into a single competitor.
	"""
	host = (urlparse(website).netloc or "").strip().lower()
	if not host:
		return website.strip().lower()
	host = host.split("@")[-1]  # drop any userinfo
	host = host.split(":")[0]  # drop the port
	return host.removeprefix("www.").rstrip(".")


async def _require_workspace(
	workspace_id: uuid.UUID, db: AsyncSession
) -> models.Workspace:
	result = await db.execute(
		select(models.Workspace).where(models.Workspace.id == workspace_id)
	)
	workspace = result.scalar_one_or_none()
	if workspace is None:
		raise HTTPException(
			status_code=status.HTTP_404_NOT_FOUND,
			detail="Workspace not found",
		)
	return workspace


async def _get_competitor_or_404(
	workspace_id: uuid.UUID,
	competitor_id: uuid.UUID,
	db: AsyncSession,
) -> models.Competitor:
	result = await db.execute(
		select(models.Competitor).where(
			models.Competitor.id == competitor_id,
			# Scoped by workspace so a valid competitor id from another workspace
			# is a 404 rather than a cross-tenant read.
			models.Competitor.workspace_id == workspace_id,
		)
	)
	competitor = result.scalar_one_or_none()
	if competitor is None:
		raise HTTPException(
			status_code=status.HTTP_404_NOT_FOUND,
			detail="Competitor not found",
		)
	return competitor


@router.get(
	"/{workspace_id}/competitors",
	response_model=CompetitorListResponse,
)
async def list_competitors(
	workspace_id: uuid.UUID,
	db: Annotated[AsyncSession, Depends(get_db)],
):
	"""The workspace's tracked competitors, newest first.

	Rows accumulate across runs: a re-run appends newly found firms and refreshes
	`last_seen_at` on ones already known, so this list is a growing watch list
	rather than a snapshot of the most recent run.
	"""
	await _require_workspace(workspace_id, db)

	result = await db.execute(
		select(models.Competitor)
		.where(models.Competitor.workspace_id == workspace_id)
		.order_by(models.Competitor.first_seen_at.desc())
	)
	competitors = list(result.scalars().all())
	return CompetitorListResponse(
		competitors=[CompetitorResponse.model_validate(c) for c in competitors],
		total=len(competitors),
	)


@router.post(
	"/{workspace_id}/competitors",
	response_model=CompetitorResponse,
	status_code=status.HTTP_201_CREATED,
)
async def add_competitor(
	workspace_id: uuid.UUID,
	payload: CompetitorCreateRequest,
	response: Response,
	db: Annotated[AsyncSession, Depends(get_db)],
	background_tasks: BackgroundTasks,
):
	"""Track a competitor the user supplied by URL.

	The manual path in the brief: give a site, and the agent derives the rest --
	including socials -- rather than asking the user to fill in a profile. Only
	the URL is required, and `name` is optional because it can be read off the
	page; requiring it would hand back work the system exists to do.

	Requires a URL, because a rival with no public website cannot be verified and
	the brief drops those.

	Idempotent: re-adding a rival already on the list returns 200 with the
	existing row rather than 409 or a second copy. Adding a competitor you already
	track should leave the list alone, not read as an error to resolve -- and 200
	rather than the route's 201, because nothing was created.
	"""
	await _require_workspace(workspace_id, db)

	website = payload.website.strip()
	if not re.match(r"^https?://", website, re.IGNORECASE):
		# Accept a bare host and assume https rather than rejecting it: a user who
		# types "acme.com" means acme.com, and the agent can confirm or correct
		# the scheme when it reads the page.
		website = f"https://{website}"

	domain = _domain_key(website)
	existing = await db.execute(
		select(models.Competitor).where(
			models.Competitor.workspace_id == workspace_id,
			models.Competitor.domain_key == domain,
		)
	)
	already = existing.scalar_one_or_none()
	if already is not None:
		# Idempotent rather than a 409: adding a rival you already track should
		# leave the list alone, not read as an error the user has to resolve. The
		# deeper profile is refreshed in the background.
		response.status_code = status.HTTP_200_OK
		if payload.deep_research:
			background_tasks.add_task(
				_deep_research_manual_competitor, workspace_id, already.id
			)
		return CompetitorResponse.model_validate(already)

	competitor = models.Competitor(
		workspace_id=workspace_id,
		# Marked manual so a later agent run treats it as the user's own choice
		# and refreshes rather than replacing it.
		source="manual",
		name=(payload.name or domain).strip(),
		website=website,
		domain_key=domain,
		# No research yet, so say so in the same vocabulary the agent uses. The UI
		# reads this to say "not researched yet" rather than rendering a profile
		# of empty fields as though it were a finding of emptiness.
		unsourced_fields=["description", "offering", "strengths", "weaknesses"],
	)
	db.add(competitor)
	try:
		await db.commit()
	except IntegrityError:
		# Lost a race with a concurrent add of the same host. The row exists and
		# is what the caller wanted, so report it instead of an error -- as 200,
		# because this request did not create it either.
		await db.rollback()
		response.status_code = status.HTTP_200_OK
		return await _fetch_by_domain(workspace_id, domain, db)

	await db.refresh(competitor)
	if payload.deep_research:
		background_tasks.add_task(
			_deep_research_manual_competitor, workspace_id, competitor.id
		)
	return CompetitorResponse.model_validate(competitor)


async def _fetch_by_domain(
	workspace_id: uuid.UUID,
	domain: str,
	db: AsyncSession,
) -> models.Competitor:
	result = await db.execute(
		select(models.Competitor).where(
			models.Competitor.workspace_id == workspace_id,
			models.Competitor.domain_key == domain,
		)
	)
	competitor = result.scalar_one_or_none()
	if competitor is None:  # pragma: no cover -- the row was just committed
		raise HTTPException(
			status_code=status.HTTP_409_CONFLICT,
			detail="Competitor could not be created",
		)
	return competitor


@router.get(
	"/{workspace_id}/competitors/runs",
	response_model=list[CompetitorRunResponse],
)
async def list_competitor_runs(
	workspace_id: uuid.UUID,
	db: Annotated[AsyncSession, Depends(get_db)],
	limit: int = 20,
):
	"""Recent competitor-agent runs, newest first.

	Useful on its own: the counts say how much the agent screened away, which is
	the difference between "found 3" and "screened 40, kept 3".
	"""
	await _require_workspace(workspace_id, db)

	result = await db.execute(
		select(models.CompetitorRun)
		.where(models.CompetitorRun.workspace_id == workspace_id)
		.order_by(models.CompetitorRun.created_at.desc())
		.limit(max(1, min(limit, 100)))
	)
	return [CompetitorRunResponse.model_validate(r) for r in result.scalars().all()]


@router.post(
	"/{workspace_id}/competitors/runs",
	response_model=CompetitorRunStartResponse,
	status_code=status.HTTP_202_ACCEPTED,
)
async def start_competitor_run(
	workspace_id: uuid.UUID,
	db: Annotated[AsyncSession, Depends(get_db)],
	background_tasks: BackgroundTasks,
):
	"""Kick off a competitor discovery run and return it for polling.

	The run is a job, not a request: it does real web research across every
	archetype in the ideal profile, which is far too slow to hold a POST open for.
	So this records the run, hands the work to a background task, and returns 202
	with the run to poll.

	Requires the workspace to have completed discovery, because the agent hunts
	with the ideal competitor profile and that profile is what the competition
	stage produces. Starting before it exists would send the agent out with no
	shape to look for.
	"""
	await _require_workspace(workspace_id, db)

	in_flight = await db.execute(
		select(models.CompetitorRun).where(
			models.CompetitorRun.workspace_id == workspace_id,
			models.CompetitorRun.status.in_(_ACTIVE_STATUSES),
		)
	)
	active = in_flight.scalars().first()
	if active is not None:
		# Already running. Return it instead of starting a second one: concurrent
		# runs would race on the same unique (workspace_id, domain_key).
		count = await db.scalar(
			select(func.count())
			.select_from(models.Competitor)
			.where(models.Competitor.workspace_id == workspace_id)
		)
		return CompetitorRunStartResponse(
			run=CompetitorRunResponse.model_validate(active),
			already_tracked=int(count or 0),
		)

	profile, confidence = await _load_ideal_profile(workspace_id, db)
	if profile is None:
		raise HTTPException(
			status_code=status.HTTP_409_CONFLICT,
			detail=(
				"This workspace has no ideal competitor profile yet. Complete "
				"discovery first -- the competitor agent searches using it."
			),
		)

	count = await db.scalar(
		select(func.count())
		.select_from(models.Competitor)
		.where(models.Competitor.workspace_id == workspace_id)
	)

	run = models.CompetitorRun(
		workspace_id=workspace_id,
		status="pending",
		profile_confidence=confidence,
		archetypes_targeted=len(profile.get("archetypes") or []),
	)
	db.add(run)
	await db.commit()
	await db.refresh(run)

	background_tasks.add_task(_execute_run, run.id, workspace_id)
	return CompetitorRunStartResponse(
		run=CompetitorRunResponse.model_validate(run),
		already_tracked=int(count or 0),
	)


@router.get(
	"/{workspace_id}/competitors/runs/{run_id}",
	response_model=CompetitorRunResponse,
)
async def get_competitor_run(
	workspace_id: uuid.UUID,
	run_id: uuid.UUID,
	db: Annotated[AsyncSession, Depends(get_db)],
):
	"""Poll one run's progress and outcome."""
	result = await db.execute(
		select(models.CompetitorRun).where(
			models.CompetitorRun.id == run_id,
			models.CompetitorRun.workspace_id == workspace_id,
		)
	)
	run = result.scalar_one_or_none()
	if run is None:
		raise HTTPException(
			status_code=status.HTTP_404_NOT_FOUND,
			detail="Competitor run not found",
		)
	return CompetitorRunResponse.model_validate(run)


@router.patch(
	"/{workspace_id}/competitors/{competitor_id}",
	response_model=CompetitorResponse,
)
async def update_competitor(
	workspace_id: uuid.UUID,
	competitor_id: uuid.UUID,
	payload: CompetitorUpdateRequest,
	db: Annotated[AsyncSession, Depends(get_db)],
):
	"""Edit the user-owned fields of a tracked competitor.

	Narrow on purpose. Strengths, weaknesses, pain signals, sentiment and evidence
	are researched claims with sourcing requirements; letting an edit endpoint
	write them would let the UI replace a sourced finding with an unsourced one,
	which is the exact failure the rest of this feature is built to prevent.
	"""
	competitor = await _get_competitor_or_404(workspace_id, competitor_id, db)

	changes = payload.model_dump(exclude_unset=True)
	if "website" in changes and changes["website"]:
		website = changes["website"].strip()
		if not re.match(r"^https?://", website, re.IGNORECASE):
			website = f"https://{website}"
		changes["website"] = website
		changes["domain_key"] = _domain_key(website)

	for field, value in changes.items():
		setattr(competitor, field, value)

	try:
		await db.commit()
	except IntegrityError:
		# The edit pointed the row at a host another competitor in this
		# workspace already uses.
		await db.rollback()
		raise HTTPException(
			status_code=status.HTTP_409_CONFLICT,
			detail="Another tracked competitor already uses that website",
		)

	await db.refresh(competitor)
	return CompetitorResponse.model_validate(competitor)


@router.delete(
	"/{workspace_id}/competitors/{competitor_id}",
	status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_competitor(
	workspace_id: uuid.UUID,
	competitor_id: uuid.UUID,
	db: Annotated[AsyncSession, Depends(get_db)],
):
	"""Stop tracking a competitor.

	Deletes the row rather than flagging it: the watch list is a working list, and
	keeping tombstones for companies the user deliberately removed would make
	"tracked" mean something different from what it says.
	"""
	competitor = await _get_competitor_or_404(workspace_id, competitor_id, db)
	await db.delete(competitor)
	await db.commit()


async def _load_ideal_profile(
	workspace_id: uuid.UUID,
	db: AsyncSession,
) -> tuple[dict | None, str | None]:
	"""The competition stage's archetype profile, and its confidence.

	Read from the persisted insights because that is where a completed discovery
	run leaves it, and because the competitor agent is standalone: it cannot
	resume the discovery checkpoint (that thread id is scoped to one WebSocket
	connection) so the database is the only place the profile survives to.
	"""
	result = await db.execute(
		select(models.ProductProfile).where(
			models.ProductProfile.workspace_id == workspace_id
		)
	)
	profile_row = result.scalar_one_or_none()
	if profile_row is None or not profile_row.insights:
		return None, None
	profile = profile_row.insights.get("ideal_competitor_profile")
	if not profile:
		return None, None
	return profile, profile.get("confidence")


async def _set_run(run_id: uuid.UUID, **fields) -> None:
	"""Write run-status fields in their own short-lived session.

	One session per transition, rather than one held across the whole run. The
	agent takes minutes of real network and LLM time; a session checked out for
	that long sits idle holding a pooled connection, and on SQLite it holds a
	read lock that blocks every other writer in the app for the duration.
	"""
	async with AsyncSessionLocal() as db:
		async with db.begin():
			run = await db.get(models.CompetitorRun, run_id)
			if run is None:
				# Workspace deleted mid-flight. Nothing left to report to.
				return None
			for field, value in fields.items():
				setattr(run, field, value)
			return run


async def _execute_run(run_id: uuid.UUID, workspace_id: uuid.UUID) -> None:
	"""Run the agent and record the outcome on the run row.

	Every failure path writes `failed` and a reason rather than leaving the run
	`running` forever. A run stuck in `running` is indistinguishable from a slow
	one in a polled UI, and the user has no way to tell that apart from "still
	working" -- so an error the user cannot see is worse than a visible stop.
	"""
	if await _set_run(run_id, status="running", started_at=datetime.now(UTC)) is None:
		return

	try:
		# The runner, not the agent: the agent is pure and cannot reach the
		# database, so hydration and persistence live in
		# backend/app/competitor_runner.py. Imported lazily because that module
		# pulls in the LLM and scraping stacks, and this one is loaded by
		# routes.py at app start -- the other six endpoints stay usable
		# regardless of the agent's dependencies.
		from backend.app.competitor_runner import run_competitor_discovery

		outcome = await run_competitor_discovery(
			workspace_id=workspace_id, run_id=run_id
		)
	except Exception as exc:  # noqa: BLE001 -- the reason is recorded, not raised
		await _set_run(
			run_id,
			status="failed",
			error=f"{type(exc).__name__}: {exc}"[:2000],
			finished_at=datetime.now(UTC),
		)
		return

	await _set_run(
		run_id,
		status="completed",
		candidates_seen=int(outcome.get("candidates_seen") or 0),
		found=int(outcome.get("found") or 0),
		dropped=int(outcome.get("dropped") or 0),
		dropped_reasons=outcome.get("dropped_reasons") or None,
		finished_at=datetime.now(UTC),
	)


async def _deep_research_manual_competitor(
	workspace_id: uuid.UUID, competitor_id: uuid.UUID
) -> None:
	"""Fill in a manually added competitor's profile from its website.

	Best-effort and silent: this runs after the response has already been sent,
	so there is nobody to return an error to. The row keeps its `unsourced_fields`
	list either way, which is the honest record -- a competitor the agent could
	not research shows up as "not found" per field rather than as a profile of
	blanks that looks researched.
	"""
	try:
		from backend.app.competitor_runner import research_competitor_site

		await research_competitor_site(
			workspace_id=workspace_id, competitor_id=competitor_id
		)
	except Exception:  # noqa: BLE001 -- best effort; the row stands as added
		return
