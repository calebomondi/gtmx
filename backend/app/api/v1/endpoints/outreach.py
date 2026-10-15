"""A workspace's outreach: agent drafts, user edits, explicit sends."""

import uuid

from fastapi import APIRouter, status
from sqlalchemy import select

from backend.app.api.deps import AuthUser, CurrentUser, DbSession, OwnedWorkspace
from backend.app.database import models
from backend.app.runs import manager as run_manager
from backend.app.runs import background
from backend.app.schemas.outreach import (
    DraftRequest,
    MessageUpdate,
    OutreachListResponse,
    OutreachMessageResponse,
    SyncResponse,
)
from backend.app.services import inbox as inbox_service
from backend.app.schemas.runs import RunResponse
from backend.app.services import outreach as outreach_service
from backend.app.services.errors import ConflictError
from backend.app.services.runs import TERMINAL_STATUSES

router = APIRouter()


def sender_name(user: AuthUser) -> str:
    return outreach_service.sender_name(user.name, user.email)


@router.get("/{workspace_id}/outreach", response_model=OutreachListResponse)
async def list_outreach(workspace: OwnedWorkspace, db: DbSession):
    drafting = await db.scalar(select(models.Run).where(
        models.Run.workspace_id == workspace.id, models.Run.kind.in_(("outreach_drafts", "outreach_reply")),
        models.Run.status.not_in(TERMINAL_STATUSES),
    ))
    messages = await outreach_service.list_for_workspace(db, workspace.id)
    return OutreachListResponse(
        messages=[OutreachMessageResponse.model_validate(m) for m in messages],
        drafting_run=RunResponse.model_validate(drafting) if drafting else None,
    )


@router.post("/{workspace_id}/outreach/drafts", response_model=RunResponse, status_code=status.HTTP_202_ACCEPTED)
async def draft_outreach(workspace: OwnedWorkspace, payload: DraftRequest, user: CurrentUser, db: DbSession):
    """Draft one message per account. Poll GET for the drafts."""
    await outreach_service.accounts_for_drafting(db, workspace.id, payload.account_ids)  # validates ownership
    return await run_manager.start_background(
        "outreach_drafts", workspace.user_id, workspace.id,
        params={"account_ids": [str(a) for a in payload.account_ids], "channel": payload.channel,
                "sender": sender_name(user),
                "recipient": payload.recipient.model_dump() if payload.recipient else None},
    )


@router.patch("/{workspace_id}/outreach/messages/{message_id}", response_model=OutreachMessageResponse)
async def update_message(workspace: OwnedWorkspace, message_id: uuid.UUID, payload: MessageUpdate, db: DbSession):
    message = await outreach_service.get_in_workspace(db, workspace.id, message_id)
    return await outreach_service.update(db, message, payload.model_dump(exclude_unset=True))


@router.post("/{workspace_id}/outreach/messages/{message_id}/send", response_model=OutreachMessageResponse)
async def send_message(workspace: OwnedWorkspace, message_id: uuid.UUID, db: DbSession):
    """Send one approved email through the user's Gmail. Never automatic."""
    message = await outreach_service.get_in_workspace(db, workspace.id, message_id)
    return await outreach_service.send(db, message)


@router.post("/{workspace_id}/outreach/sync", response_model=SyncResponse)
async def sync_inbox(workspace: OwnedWorkspace, db: DbSession):
    """Check the user's Gmail for replies and bounces now (also runs on a schedule)."""
    result = await inbox_service.sync_user(db, workspace.user_id)
    await background.after_inbox_sync(result)
    return SyncResponse(replies=len(result.replies), bounced=len(result.bounced))


@router.post("/{workspace_id}/outreach/messages/{message_id}/read", response_model=OutreachMessageResponse)
async def mark_read(workspace: OwnedWorkspace, message_id: uuid.UUID, db: DbSession):
    return await outreach_service.mark_read(db, await outreach_service.get_in_workspace(db, workspace.id, message_id))


@router.post("/{workspace_id}/outreach/messages/{message_id}/reply-draft", response_model=RunResponse,
             status_code=status.HTTP_202_ACCEPTED)
async def draft_reply(workspace: OwnedWorkspace, message_id: uuid.UUID, user: CurrentUser, db: DbSession):
    """Ask the GTM specialist to draft an answer to a reply. Poll GET for it."""
    reply = await outreach_service.get_in_workspace(db, workspace.id, message_id)
    if reply.direction != "inbound" or reply.status != "received":
        raise ConflictError("Only a reply you received can be answered.")
    return await run_manager.start_background(
        "outreach_reply", workspace.user_id, workspace.id,
        params={"message_id": str(reply.id), "sender": sender_name(user)},
    )


@router.post("/{workspace_id}/outreach/messages/{message_id}/meeting", response_model=OutreachMessageResponse)
async def add_meeting(workspace: OwnedWorkspace, message_id: uuid.UUID, db: DbSession):
    """Add the meeting a reply draft proposes to the user's Google Calendar."""
    return await outreach_service.add_meeting(db, await outreach_service.get_in_workspace(db, workspace.id, message_id))


@router.delete("/{workspace_id}/outreach/messages/{message_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_message(workspace: OwnedWorkspace, message_id: uuid.UUID, db: DbSession):
    await outreach_service.delete(db, await outreach_service.get_in_workspace(db, workspace.id, message_id))
