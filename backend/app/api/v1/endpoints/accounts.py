"""Account-discovery agent endpoints.

Mirrors competitors.py on purpose: the agent is triggered by POST, polled for
progress, and the accounts it finds are rows stored against the workspace so a
fresh load or a second browser can see them. The only writable field on an
account is `selected` -- the user's choice to keep it for outreach."""

from datetime import datetime, UTC
from typing import Annotated, Optional
import uuid

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    HTTPException,
    Response,
    status,
)
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.api.deps import AuthUser, require_user
from backend.app.database import models
from backend.app.database.connect import AsyncSessionLocal, get_db

router = APIRouter()

_ACTIVE_STATUSES = ("pending", "running")


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------


class AccountResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    workspace_id: uuid.UUID
    run_id: uuid.UUID | None = None
    name: str
    account_type: str = "company"
    website: str | None = None
    domain: str | None = None
    platform: str | None = None
    venue: str | None = None
    event_date: str | None = None
    member_size: str | None = None
    industry: str | None = None
    size: str | None = None
    geo: str | None = None
    tech_stack: list[str] = []
    recent_news: list[str] = []
    key_contacts: list[dict] = []
    pain_signals: list[str] = []
    hiring_signals: list[str] = []
    sources: list[dict] = []
    source_queries: list[str] = []
    score: float | None = None
    score_breakdown: str | None = None
    why_selected: list[str] = []
    why_reach_out: list[str] = []
    trigger_event: dict | None = None
    selected: bool = False
    created_at: datetime


class AccountListResponse(BaseModel):
    accounts: list[AccountResponse]
    total: int


class AccountUpdateRequest(BaseModel):
    selected: bool | None = None


class AccountRunResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    workspace_id: uuid.UUID
    status: str = Field(description="pending | running | completed | failed")
    error: str | None = None
    candidates_seen: int = 0
    found: int = 0
    started_at: datetime | None = None
    finished_at: datetime | None = None
    created_at: datetime


class AccountRunStartResponse(BaseModel):
    run: AccountRunResponse
    already_tracked: int = 0


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _require_workspace(workspace_id: uuid.UUID, db: AsyncSession) -> models.Workspace:
    result = await db.execute(
        select(models.Workspace).where(models.Workspace.id == workspace_id)
    )
    workspace = result.scalar_one_or_none()
    if workspace is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Workspace not found")
    return workspace


async def _set_run(run_id: uuid.UUID, **fields) -> None:
    async with AsyncSessionLocal() as db:
        async with db.begin():
            run = await db.get(models.AccountRun, run_id)
            if run is None:
                return None
            for field, value in fields.items():
                setattr(run, field, value)
            return run


async def _execute_run(run_id: uuid.UUID, workspace_id: uuid.UUID) -> None:
    if await _set_run(run_id, status="running", started_at=datetime.now(UTC)) is None:
        return
    try:
        from backend.app.account_runner import run_account_discovery_for_workspace

        outcome = await run_account_discovery_for_workspace(
            workspace_id=workspace_id, run_id=run_id
        )
    except Exception as exc:  # noqa: BLE001
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
        finished_at=datetime.now(UTC),
    )


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@router.get("/{workspace_id}/accounts", response_model=AccountListResponse)
async def list_accounts(
    workspace_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    await _require_workspace(workspace_id, db)
    result = await db.execute(
        select(models.Account)
        .where(models.Account.workspace_id == workspace_id)
        .order_by(models.Account.created_at.desc())
    )
    accounts = list(result.scalars().all())
    return AccountListResponse(
        accounts=[AccountResponse.model_validate(a) for a in accounts],
        total=len(accounts),
    )


@router.patch("/{workspace_id}/accounts/{account_id}", response_model=AccountResponse)
async def update_account(
    workspace_id: uuid.UUID,
    account_id: uuid.UUID,
    payload: AccountUpdateRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    await _require_workspace(workspace_id, db)
    account = (
        await db.execute(
            select(models.Account).where(
                models.Account.id == account_id,
                models.Account.workspace_id == workspace_id,
            )
        )
    ).scalar_one_or_none()
    if account is None:
        raise HTTPException(status_code=404, detail="Account not found")
    if payload.selected is not None:
        account.selected = payload.selected
    await db.commit()
    await db.refresh(account)
    return AccountResponse.model_validate(account)


@router.get("/{workspace_id}/accounts/runs", response_model=list[AccountRunResponse])
async def list_account_runs(
    workspace_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    limit: int = 20,
):
    await _require_workspace(workspace_id, db)
    result = await db.execute(
        select(models.AccountRun)
        .where(models.AccountRun.workspace_id == workspace_id)
        .order_by(models.AccountRun.created_at.desc())
        .limit(max(1, min(limit, 100)))
    )
    return [AccountRunResponse.model_validate(r) for r in result.scalars().all()]


@router.post(
    "/{workspace_id}/accounts/runs",
    response_model=AccountRunStartResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def start_account_run(
    workspace_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    background_tasks: BackgroundTasks,
):
    await _require_workspace(workspace_id, db)

    in_flight = await db.execute(
        select(models.AccountRun).where(
            models.AccountRun.workspace_id == workspace_id,
            models.AccountRun.status.in_(_ACTIVE_STATUSES),
        )
    )
    active = in_flight.scalars().first()
    count = await db.scalar(
        select(func.count())
        .select_from(models.Account)
        .where(models.Account.workspace_id == workspace_id)
    )
    if active is not None:
        return AccountRunStartResponse(
            run=AccountRunResponse.model_validate(active),
            already_tracked=int(count or 0),
        )

    profile = (
        await db.execute(
            select(models.ProductProfile).where(
                models.ProductProfile.workspace_id == workspace_id
            )
        )
    ).scalar_one_or_none()
    if profile is None or not profile.insights or not profile.insights.get("icp"):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "This workspace has no ICP yet. Complete the Offer run first -- "
                "the account agent searches for accounts matching it."
            ),
        )

    run = models.AccountRun(workspace_id=workspace_id, status="pending")
    db.add(run)
    await db.commit()
    await db.refresh(run)
    background_tasks.add_task(_execute_run, run.id, workspace_id)
    return AccountRunStartResponse(
        run=AccountRunResponse.model_validate(run),
        already_tracked=int(count or 0),
    )


@router.get(
    "/{workspace_id}/accounts/runs/{run_id}",
    response_model=AccountRunResponse,
)
async def get_account_run(
    workspace_id: uuid.UUID,
    run_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    result = await db.execute(
        select(models.AccountRun).where(
            models.AccountRun.id == run_id,
            models.AccountRun.workspace_id == workspace_id,
        )
    )
    run = result.scalar_one_or_none()
    if run is None:
        raise HTTPException(status_code=404, detail="Account run not found")
    return AccountRunResponse.model_validate(run)
