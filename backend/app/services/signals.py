"""Feed signals: emitted by runs, read/pinned/dismissed by their owner."""

import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from backend.app.database import models
from backend.app.services.errors import NotFoundError

FEED_LIMIT = 200
_SUMMARY_CHARS = 400


def _clip(text: str | None, limit: int) -> str:
    text = (text or "").strip()
    return text if len(text) <= limit else text[: limit - 1].rstrip() + "…"


def build(
    *,
    user_id: uuid.UUID,
    workspace_id: uuid.UUID,
    category: str,
    title: str,
    entity: str = "",
    summary: str = "",
    reason: str = "",
    run_id: uuid.UUID | None = None,
    source_url: str | None = None,
    hot: bool = False,
) -> models.Signal:
    return models.Signal(
        user_id=user_id, workspace_id=workspace_id, run_id=run_id, category=category,
        title=_clip(title, 255), entity=_clip(entity, 255), summary=_clip(summary, _SUMMARY_CHARS),
        reason=reason, source_url=source_url, hot=hot,
    )


async def emit(db: AsyncSession, signals: list[models.Signal]) -> None:
    db.add_all(signals)
    await db.commit()


async def list_for_owner(db: AsyncSession, owner_id: uuid.UUID, workspace_id: uuid.UUID | None = None) -> list[models.Signal]:
    """Newest first, dismissed ones excluded; one workspace or all of them."""
    query = (
        select(models.Signal)
        .options(selectinload(models.Signal.workspace))
        .where(models.Signal.user_id == owner_id, models.Signal.dismissed.is_(False))
        .order_by(models.Signal.created_at.desc())
        .limit(FEED_LIMIT)
    )
    if workspace_id is not None:
        query = query.where(models.Signal.workspace_id == workspace_id)
    return list((await db.execute(query)).scalars().all())


async def update_owned(db: AsyncSession, owner_id: uuid.UUID, signal_id: uuid.UUID, changes: dict[str, Any]) -> models.Signal:
    signal = await db.scalar(
        select(models.Signal)
        .options(selectinload(models.Signal.workspace))
        .where(models.Signal.id == signal_id, models.Signal.user_id == owner_id)
    )
    if signal is None:
        raise NotFoundError("Signal not found")
    for field in ("read", "pinned", "dismissed"):
        if changes.get(field) is not None:
            setattr(signal, field, changes[field])
    await db.commit()
    return signal
