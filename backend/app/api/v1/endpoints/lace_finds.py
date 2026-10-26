"""A member's private finds (from their private chat) and the team's review
of the ones they push."""

import uuid
from dataclasses import asdict

from fastapi import APIRouter, Query, status

from agents.schemas.lace import SavedKind
from backend.app.api.deps import CurrentUser, DbSession, LaceMembership, MemberLace
from backend.app.schemas.lace_finds import FindResponse, PushRequest, PushResponse, SendBackRequest
from backend.app.services import lace_finds, lace_members

router = APIRouter()

# Finds listed at once, per kind.
MAX_FINDS = 100


@router.get("/{lace_id}/my-finds", response_model=list[FindResponse])
async def my_finds(lace: MemberLace, user: CurrentUser, db: DbSession,
                   limit: int = Query(default=50, ge=1, le=MAX_FINDS)):
    """What your private chat found and you haven't dismissed: yours alone,
    until you push it to the team."""
    return [FindResponse(**asdict(f)) for f in await lace_finds.mine(db, lace.id, user.id, limit)]


@router.post("/{lace_id}/my-finds/push", response_model=PushResponse)
async def push_finds(lace: MemberLace, user: CurrentUser, payload: PushRequest, db: DbSession):
    """Put your private finds up for the team: another member approves them."""
    items = [(item.kind, item.id) for item in payload.items]
    return PushResponse(pushed=await lace_finds.push(db, lace.id, user.id, items))


@router.get("/{lace_id}/reviews", response_model=list[FindResponse])
async def list_reviews(lace: MemberLace, me: LaceMembership, db: DbSession,
                       limit: int = Query(default=50, ge=1, le=MAX_FINDS)):
    """Finds pushed to the team, waiting for someone to approve them."""
    finds = await lace_finds.to_review(db, lace.id, limit)
    owners = await lace_members.actors(db, [(lace.id, f.owner_id) for f in finds])
    return [FindResponse(**asdict(f), owner=owners.get((lace.id, f.owner_id)),
                         can_review=lace_finds.may_review(f, me.user_id, me.role)) for f in finds]


@router.post("/{lace_id}/reviews/{kind}/{find_id}/approve", status_code=status.HTTP_204_NO_CONTENT)
async def approve_find(lace: MemberLace, me: LaceMembership, kind: SavedKind, find_id: uuid.UUID, db: DbSession):
    """Save a pushed find for the team."""
    await lace_finds.approve(db, lace.id, kind, find_id, me.user_id, me.role)


@router.post("/{lace_id}/reviews/{kind}/{find_id}/send-back", status_code=status.HTTP_204_NO_CONTENT)
async def send_back_find(lace: MemberLace, me: LaceMembership, kind: SavedKind, find_id: uuid.UUID,
                         payload: SendBackRequest, db: DbSession):
    """Return a pushed find to the member who found it, with a note."""
    await lace_finds.send_back(db, lace.id, kind, find_id, me.user_id, me.role, payload.note)
