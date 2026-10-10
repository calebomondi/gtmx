"""A workspace's conversation with its agent team."""

from fastapi import APIRouter, status
from sqlalchemy import select

from backend.app.api.deps import DbSession, OwnedWorkspace
from backend.app.database import models
from backend.app.runs import manager as run_manager
from backend.app.schemas.chat import ChatMessageResponse, ChatSendRequest, ChatSendResponse, ChatThreadResponse
from backend.app.schemas.runs import RunResponse
from backend.app.services import chat as chat_service

router = APIRouter()


@router.get("/{workspace_id}/chat", response_model=ChatThreadResponse)
async def get_chat(workspace: OwnedWorkspace, db: DbSession):
    messages = await chat_service.list_messages(db, workspace.id)
    reply_run = await chat_service.pending_run(db, workspace.id)
    if reply_run is None:
        # Surface a failed last reply (no assistant message came after it).
        last = await db.scalar(
            select(models.Run)
            .where(models.Run.workspace_id == workspace.id, models.Run.kind == "chat")
            .order_by(models.Run.created_at.desc())
        )
        if last is not None and last.status == "failed" and (not messages or messages[-1].role == "user"):
            reply_run = last
    return ChatThreadResponse(
        messages=[ChatMessageResponse.model_validate(m) for m in messages],
        reply_run=RunResponse.model_validate(reply_run) if reply_run else None,
    )


@router.post("/{workspace_id}/chat", response_model=ChatSendResponse, status_code=status.HTTP_202_ACCEPTED)
async def send_chat(workspace: OwnedWorkspace, payload: ChatSendRequest, db: DbSession):
    """Store the message and start the reply; poll GET for the answer."""
    message = await chat_service.add_user_message(db, workspace, payload.message)
    run = await run_manager.start_background("chat", workspace.user_id, workspace.id)
    return ChatSendResponse(
        message=ChatMessageResponse.model_validate(message),
        reply_run=RunResponse.model_validate(run),
    )
