"""Workspace chat: the conversation, and the workspace context the agent is
grounded in (assembled here because it needs the database)."""

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.database import models
from backend.app.services.errors import ConflictError, InvalidInputError
from backend.app.services.runs import TERMINAL_STATUSES

HISTORY_TURNS = 12  # prior messages the agent sees
MAX_MESSAGE_CHARS = 4000
_LIST_LIMIT = 200


async def list_messages(db: AsyncSession, workspace_id: uuid.UUID) -> list[models.ChatMessage]:
    rows = (await db.execute(
        select(models.ChatMessage)
        .where(models.ChatMessage.workspace_id == workspace_id)
        .order_by(models.ChatMessage.created_at.desc())
        .limit(_LIST_LIMIT)
    )).scalars().all()
    return list(reversed(rows))


async def pending_run(db: AsyncSession, workspace_id: uuid.UUID) -> models.Run | None:
    return await db.scalar(
        select(models.Run).where(
            models.Run.workspace_id == workspace_id,
            models.Run.kind == "chat",
            models.Run.status.not_in(TERMINAL_STATUSES),
        )
    )


async def add_user_message(db: AsyncSession, workspace: models.Workspace, content: str) -> models.ChatMessage:
    content = (content or "").strip()
    if not content:
        raise InvalidInputError("Message cannot be empty.")
    if len(content) > MAX_MESSAGE_CHARS:
        raise InvalidInputError(f"Message is too long (max {MAX_MESSAGE_CHARS} characters).")
    if await pending_run(db, workspace.id) is not None:
        raise ConflictError("The agent is still answering your last message.")
    message = models.ChatMessage(workspace_id=workspace.id, user_id=workspace.user_id, role="user", content=content)
    db.add(message)
    await db.commit()
    return message


async def add_assistant_message(db: AsyncSession, workspace_id: uuid.UUID, user_id: uuid.UUID,
                                run_id: uuid.UUID, content: str, specialist_domain: str) -> models.ChatMessage:
    message = models.ChatMessage(
        workspace_id=workspace_id, user_id=user_id, role="assistant", content=content, run_id=run_id,
        specialist_domain=specialist_domain,
    )
    db.add(message)
    await db.commit()
    return message
