"""Target accounts found by account discovery. The only user-writable field is
`selected`: the choice to keep an account for outreach."""

import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.database import models
from backend.app.services.runs import TERMINAL_STATUSES
from backend.app.services.errors import ConflictError, NotFoundError



async def list_for_workspace(db: AsyncSession, workspace_id: uuid.UUID) -> list[models.Account]:
    result = await db.execute(
        select(models.Account)
        .where(models.Account.workspace_id == workspace_id)
        .order_by(models.Account.created_at.desc())
    )
    return list(result.scalars().all())


async def count_for_workspace(db: AsyncSession, workspace_id: uuid.UUID) -> int:
    return int(await db.scalar(
        select(func.count()).select_from(models.Account).where(models.Account.workspace_id == workspace_id)
    ) or 0)


async def set_selected(
    db: AsyncSession, workspace_id: uuid.UUID, account_id: uuid.UUID, selected: bool | None
) -> models.Account:
    result = await db.execute(
        select(models.Account).where(
            models.Account.id == account_id,
            models.Account.workspace_id == workspace_id,
        )
    )
    account = result.scalar_one_or_none()
    if account is None:
        raise NotFoundError("Account not found")
    if selected is not None:
        account.selected = selected
        await db.commit()
        await db.refresh(account)
    return account


async def list_runs(db: AsyncSession, workspace_id: uuid.UUID, limit: int) -> list[models.Run]:
    result = await db.execute(
        select(models.Run)
        .where(models.Run.workspace_id == workspace_id, models.Run.kind == "accounts")
        .order_by(models.Run.created_at.desc())
        .limit(max(1, min(limit, 100)))
    )
    return list(result.scalars().all())


async def get_run(db: AsyncSession, workspace_id: uuid.UUID, run_id: uuid.UUID) -> models.Run:
    run = await db.scalar(
        select(models.Run).where(
            models.Run.id == run_id, models.Run.workspace_id == workspace_id, models.Run.kind == "accounts",
        )
    )
    if run is None:
        raise NotFoundError("Account run not found")
    return run


async def active_run(db: AsyncSession, workspace_id: uuid.UUID) -> models.Run | None:
    """The run in flight, if any -- one per workspace, because concurrent runs
    would race on the same upserts."""
    result = await db.execute(
        select(models.Run).where(
            models.Run.workspace_id == workspace_id,
            models.Run.kind == "accounts",
            models.Run.status.not_in(TERMINAL_STATUSES),
        )
    )
    return result.scalars().first()


async def require_icp(db: AsyncSession, workspace_id: uuid.UUID) -> None:
    """Account discovery searches against the ICP a finished discovery run
    produces; starting before that is a conflict."""
    insights = await db.scalar(
        select(models.ProductProfile.insights).where(models.ProductProfile.workspace_id == workspace_id)
    )
    if not (insights or {}).get("icp"):
        raise ConflictError(
            "This workspace has no ICP yet. Complete the Offer run first -- "
            "the account agent searches for accounts matching it."
        )
