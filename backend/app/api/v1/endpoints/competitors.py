"""Tracked competitors for a workspace, and the competitor-agent runs that fill
them. Runs are jobs: POST records one and returns 202; clients poll it."""

import uuid

from fastapi import APIRouter, Response, status

from backend.app.api.deps import DbSession, OwnedWorkspace
from backend.app.runs import manager as run_manager
from backend.app.schemas.competitors import (
    CompetitorCreateRequest,
    CompetitorListResponse,
    CompetitorResponse,
    CompetitorRunResponse,
    CompetitorRunStartResponse,
    CompetitorUpdateRequest,
)
from backend.app.services import competitors as competitor_service
from backend.app.schemas.runs import RunResponse
from backend.app.services.errors import ConflictError, RateLimitedError

router = APIRouter()


@router.get("/{workspace_id}/competitors", response_model=CompetitorListResponse)
async def list_competitors(workspace: OwnedWorkspace, db: DbSession):
    """The growing watch list, newest first."""
    competitors = await competitor_service.list_for_workspace(db, workspace.id)
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
    workspace: OwnedWorkspace,
    payload: CompetitorCreateRequest,
    response: Response,
    db: DbSession,
):
    """Track a rival by URL; the agent derives the rest in the background.

    Idempotent: re-adding a tracked host returns the existing row with 200
    (nothing was created) rather than 409 or a duplicate.
    """
    competitor, created = await competitor_service.add_manual(db, workspace.id, payload.website, payload.name)
    if not created:
        response.status_code = status.HTTP_200_OK
    if payload.deep_research:
        try:
            await run_manager.start_background(
                "competitor_research", workspace.user_id, workspace.id,
                params={"competitor_id": str(competitor.id)},
            )
        except RateLimitedError:
            pass  # still tracked; it stays marked "not researched yet"
    return CompetitorResponse.model_validate(competitor)


@router.get("/{workspace_id}/competitors/runs", response_model=list[CompetitorRunResponse])
async def list_competitor_runs(workspace: OwnedWorkspace, db: DbSession, limit: int = 20):
    """Recent runs, newest first. The counts say how much the agent screened
    away -- the difference between "found 3" and "screened 40, kept 3"."""
    runs = await competitor_service.list_runs(db, workspace.id, limit)
    return [CompetitorRunResponse.from_run(r) for r in runs]


@router.post(
    "/{workspace_id}/competitors/runs",
    response_model=CompetitorRunStartResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def start_competitor_run(workspace: OwnedWorkspace, db: DbSession):
    """Start a run (or return the one already in flight) for polling."""
    run = await competitor_service.active_run(db, workspace.id)
    if run is None:
        profile = await competitor_service.require_ideal_profile(db, workspace.id)
        run = await run_manager.start_background(
            "competitors", workspace.user_id, workspace.id,
            progress={
                "profile_confidence": profile.get("confidence"),
                "archetypes_targeted": len(profile.get("archetypes") or []),
            },
        )
    return CompetitorRunStartResponse(
        run=CompetitorRunResponse.from_run(run),
        already_tracked=await competitor_service.count_for_workspace(db, workspace.id),
    )


@router.post("/{workspace_id}/competitors/monitor", response_model=RunResponse, status_code=status.HTTP_202_ACCEPTED)
async def check_competitors_now(workspace: OwnedWorkspace, db: DbSession):
    """Re-check every tracked competitor now; changes arrive as feed signals."""
    if await competitor_service.count_for_workspace(db, workspace.id) == 0:
        raise ConflictError("Track at least one competitor before monitoring.")
    active = await competitor_service.active_monitor_run(db, workspace.id)
    return active or await run_manager.start_background("monitor", workspace.user_id, workspace.id)


@router.get("/{workspace_id}/competitors/runs/{run_id}", response_model=CompetitorRunResponse)
async def get_competitor_run(workspace: OwnedWorkspace, run_id: uuid.UUID, db: DbSession):
    return CompetitorRunResponse.from_run(await competitor_service.get_run(db, workspace.id, run_id))


@router.patch("/{workspace_id}/competitors/{competitor_id}", response_model=CompetitorResponse)
async def update_competitor(
    workspace: OwnedWorkspace, competitor_id: uuid.UUID, payload: CompetitorUpdateRequest, db: DbSession
):
    """Edit the user-owned fields (name, website, notes) of a tracked rival."""
    competitor = await competitor_service.get_in_workspace(db, workspace.id, competitor_id)
    updated = await competitor_service.update(db, competitor, payload.model_dump(exclude_unset=True))
    return CompetitorResponse.model_validate(updated)


@router.delete("/{workspace_id}/competitors/{competitor_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_competitor(workspace: OwnedWorkspace, competitor_id: uuid.UUID, db: DbSession):
    competitor = await competitor_service.get_in_workspace(db, workspace.id, competitor_id)
    await competitor_service.delete(db, competitor)
