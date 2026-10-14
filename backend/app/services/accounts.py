"""Target accounts found by account discovery, and the clients of tracked
competitors suggested alongside them. The user writes two fields: `selected`
(keep an account for outreach) and `review_status` (accept or dismiss a
suggestion)."""

import uuid
from urllib.parse import urlsplit

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.database import models
from backend.app.runs.kinds import RunKind
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


async def update(
    db: AsyncSession, workspace_id: uuid.UUID, account_id: uuid.UUID,
    selected: bool | None = None, review_status: str | None = None,
) -> models.Account:
    """The user's choices on an account: keep it for outreach, and accept or
    dismiss a suggested one."""
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
    if review_status is not None:
        account.review_status = review_status
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


async def active_run(db: AsyncSession, workspace_id: uuid.UUID, kind: RunKind = "accounts") -> models.Run | None:
    """The run of `kind` in flight, if any -- one per workspace, because
    concurrent runs would race on the same rows."""
    result = await db.execute(
        select(models.Run).where(
            models.Run.workspace_id == workspace_id,
            models.Run.kind == kind,
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


FIT_BATCH = 40  # accounts one fit run assesses; the rest wait for the next


async def without_fit(db: AsyncSession, workspace_id: uuid.UUID) -> list[models.Account]:
    """Accounts whose fit hasn't been assessed, best first."""
    return list((await db.execute(
        select(models.Account)
        .where(models.Account.workspace_id == workspace_id, models.Account.fit.is_(None),
               models.Account.review_status != "dismissed")
        .order_by(models.Account.score.desc().nulls_last())
        .limit(FIT_BATCH)
    )).scalars().all())


async def save_fits(db: AsyncSession, fits: dict[uuid.UUID, dict]) -> None:
    for account_id, fit in fits.items():
        account = await db.get(models.Account, account_id)
        if account is not None:
            account.fit = fit
    await db.commit()


MAX_SUGGESTED_REASONS = 3  # the competitor's weaknesses carried onto each client


def _host(url: str | None) -> str:
    return (urlsplit(url or "").hostname or "").removeprefix("www.").lower()


async def suggest_clients(
    db: AsyncSession, workspace_id: uuid.UUID, run_id: uuid.UUID | None,
    competitor: models.Competitor, clients: list[dict],
) -> int:
    """Add a competitor's named clients as suggested accounts. An account the
    workspace already has (by name or website) is left as it is. Returns how
    many were added."""
    existing = (await db.execute(
        select(func.lower(models.Account.name), models.Account.domain).where(models.Account.workspace_id == workspace_id)
    )).all()
    names = {name for name, _ in existing}
    domains = {domain for _, domain in existing if domain}
    rivals = set((await db.execute(
        select(models.Competitor.domain_key).where(models.Competitor.workspace_id == workspace_id)
    )).scalars().all())
    reasons = [
        f"{competitor.name}'s weakness: {w['text'] if isinstance(w, dict) else w}"
        for w in (competitor.weaknesses or [])[:MAX_SUGGESTED_REASONS]
    ]
    added = 0
    for client in clients:
        domain = _host(client.get("website"))
        if client["name"].strip().lower() in names or (domain and (domain in domains or domain in rivals)):
            continue
        db.add(models.Account(
            workspace_id=workspace_id, run_id=run_id, name=client["name"].strip(), account_type="company",
            website=client.get("website"), domain=domain or None, geo=client.get("country"),
            summary=f"Named as a client of {competitor.name}.",
            trigger_event={
                "event": f'Uses {competitor.name}: "{client["evidence"]}"',
                "signal_type": "competitor_review_mention", "source": client["source_url"],
            },
            sources=[{"title": f"{competitor.name}: {client.get('relationship', 'profile')}",
                      "url": client["source_url"], "snippet": client["evidence"]}],
            why_reach_out=reasons, review_status="suggested", via_competitor_id=competitor.id,
        ))
        names.add(client["name"].strip().lower())
        if domain:
            domains.add(domain)
        added += 1
    await db.commit()
    return added
