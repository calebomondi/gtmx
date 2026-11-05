"""The founder's social posts with how they did, and what a Lace's listen
kept from comments and mentions, for the Social view."""

import uuid

from fastapi import APIRouter, Query

from agents.schemas.listening import HeardStatus, SocialPlatform
from backend.app.api.deps import DbSession, MemberLace
from backend.app.schemas.lace_social import SocialItemResponse, SocialItemUpdate, SocialPostResponse
from backend.app.services import lace_social

router = APIRouter()

MAX_SOCIAL_PER_PAGE = 100


@router.get("/{lace_id}/social/posts", response_model=list[SocialPostResponse])
async def list_social_posts(lace: MemberLace, db: DbSession, platform: SocialPlatform | None = None,
                            limit: int = Query(default=30, ge=1, le=MAX_SOCIAL_PER_PAGE)):
    return await lace_social.posts(db, lace.id, platform, limit)


@router.get("/{lace_id}/social/heard", response_model=list[SocialItemResponse])
async def list_social_heard(lace: MemberLace, db: DbSession, platform: SocialPlatform | None = None,
                            status: HeardStatus | None = None,
                            limit: int = Query(default=50, ge=1, le=MAX_SOCIAL_PER_PAGE)):
    return await lace_social.heard(db, lace.id, platform, status, limit)


@router.patch("/{lace_id}/social/heard/{item_id}", response_model=SocialItemResponse)
async def update_social_heard(lace: MemberLace, item_id: uuid.UUID, payload: SocialItemUpdate, db: DbSession):
    """Mark something heard as acted on (done) or set aside (dismissed), or bring it back (new)."""
    return await lace_social.set_status(db, lace.id, item_id, payload.status)
