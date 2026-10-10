"""Target accounts found by account discovery. The only user-writable field is
`selected`: the choice to keep an account for outreach."""

import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.database import models
from backend.app.services.errors import ConflictError, NotFoundError

ACTIVE_RUN_STATUSES = ("pending", "running")


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


async def list_runs(db: AsyncSession, workspace_id: uuid.UUID, limit: int) -> list[models.AccountRun]:
    result = await db.execute(
        select(models.AccountRun)
        .where(models.AccountRun.workspace_id == workspace_id)
        .order_by(models.AccountRun.created_at.desc())
        .limit(max(1, min(limit, 100)))
    )
    return list(result.scalars().all())


async def get_run(db: AsyncSession, workspace_id: uuid.UUID, run_id: uuid.UUID) -> models.AccountRun:
    result = await db.execute(
        select(models.AccountRun).where(
            models.AccountRun.id == run_id,
            models.AccountRun.workspace_id == workspace_id,
        )
    )
    run = result.scalar_one_or_none()
    if run is None:
        raise NotFoundError("Account run not found")
    return run


async def active_run(db: AsyncSession, workspace_id: uuid.UUID) -> models.AccountRun | None:
    result = await db.execute(
        select(models.AccountRun).where(
            models.AccountRun.workspace_id == workspace_id,
            models.AccountRun.status.in_(ACTIVE_RUN_STATUSES),
        )
    )
    return result.scalars().first()


async def create_run(db: AsyncSession, workspace_id: uuid.UUID) -> models.AccountRun:
    """Record a pending run. Requires the ICP from a finished discovery run,
    which is what the account agent searches against."""
    insights = await db.scalar(
        select(models.ProductProfile.insights).where(models.ProductProfile.workspace_id == workspace_id)
    )
    if not (insights or {}).get("icp"):
        raise ConflictError(
            "This workspace has no ICP yet. Complete the Offer run first -- "
            "the account agent searches for accounts matching it."
        )
    run = models.AccountRun(workspace_id=workspace_id, status="pending")
    db.add(run)
    await db.commit()
    await db.refresh(run)
    return run
