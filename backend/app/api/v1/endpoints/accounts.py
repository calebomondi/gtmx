"""Target accounts for a workspace, and the account-discovery runs that find
them. Mirrors competitors.py: POST a run (202), poll it, read the rows."""

import uuid

from fastapi import APIRouter, status

from backend.app.api.deps import DbSession, OwnedWorkspace
from backend.app.runs import manager as run_manager
from backend.app.schemas.accounts import (
    AccountListResponse,
    AccountResponse,
    AccountRunResponse,
    AccountRunStartResponse,
    AccountUpdateRequest,
)
from backend.app.services import accounts as account_service

router = APIRouter()


@router.get("/{workspace_id}/accounts", response_model=AccountListResponse)
async def list_accounts(workspace: OwnedWorkspace, db: DbSession):
    accounts = await account_service.list_for_workspace(db, workspace.id)
    return AccountListResponse(
        accounts=[AccountResponse.model_validate(a) for a in accounts],
        total=len(accounts),
    )


@router.patch("/{workspace_id}/accounts/{account_id}", response_model=AccountResponse)
async def update_account(workspace: OwnedWorkspace, account_id: uuid.UUID, payload: AccountUpdateRequest, db: DbSession):
    """Keep (or drop) an account for outreach."""
    account = await account_service.set_selected(db, workspace.id, account_id, payload.selected)
    return AccountResponse.model_validate(account)


@router.get("/{workspace_id}/accounts/runs", response_model=list[AccountRunResponse])
async def list_account_runs(workspace: OwnedWorkspace, db: DbSession, limit: int = 20):
    runs = await account_service.list_runs(db, workspace.id, limit)
    return [AccountRunResponse.from_run(r) for r in runs]


@router.post(
    "/{workspace_id}/accounts/runs",
    response_model=AccountRunStartResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def start_account_run(workspace: OwnedWorkspace, db: DbSession):
    """Start a run (or return the one already in flight) for polling."""
    run = await account_service.active_run(db, workspace.id)
    if run is None:
        await account_service.require_icp(db, workspace.id)
        run = await run_manager.start_background("accounts", workspace.user_id, workspace.id)
    return AccountRunStartResponse(
        run=AccountRunResponse.from_run(run),
        already_tracked=await account_service.count_for_workspace(db, workspace.id),
    )


@router.get("/{workspace_id}/accounts/runs/{run_id}", response_model=AccountRunResponse)
async def get_account_run(workspace: OwnedWorkspace, run_id: uuid.UUID, db: DbSession):
    return AccountRunResponse.from_run(await account_service.get_run(db, workspace.id, run_id))
