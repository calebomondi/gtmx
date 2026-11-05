"""A Lace's view of the founder's social accounts: their posts with how they
did, and what its listen kept from comments and mentions (a lead, a question,
feedback, praise) with where the founder is with each. The listen writes
them; the Social view reads them."""

import hashlib
import uuid
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from agents.schemas.listening import HeardItem, HeardStatus, SocialPlatform
from backend.app.database.lace_models import LaceSocialItem, LaceSocialPost
from backend.app.services.errors import NotFoundError
from backend.app.services.inbox import timestamp

KEY_CHARS = 255
AUTHOR_CHARS = 255


def _when(value) -> datetime | None:
    return timestamp(value) if value else None


def item_key(item: dict) -> str:
    """The platform's id for what was said, else a digest of where, who and what."""
    if item.get("id"):
        return str(item["id"])[:KEY_CHARS]
    said = f"{item.get('url') or ''}|{item.get('author') or ''}|{item.get('text') or ''}"
    return hashlib.sha256(said.encode()).hexdigest()


async def save_posts(db: AsyncSession, lace_id: uuid.UUID, platform: SocialPlatform, posts: list[dict]) -> int:
    """Keep each post with how it did now: a post read again gets its new numbers."""
    for post in posts:
        if not post.get("url"):
            continue
        stmt = insert(LaceSocialPost).values(
            id=uuid.uuid4(), lace_id=lace_id, platform=platform, url=post["url"], text=post.get("text") or "",
            posted_at=_when(post.get("date")), views=post.get("views"), likes=post.get("likes"),
            comments=post.get("replies") if post.get("comments") is None else post.get("comments"),
            shares=post.get("reposts") if post.get("shares") is None else post.get("shares"))
        await db.execute(stmt.on_conflict_do_update(
            constraint="uq_lace_social_posts_lace_id_platform_url",
            set_={c: stmt.excluded[c] for c in ("text", "posted_at", "views", "likes", "comments", "shares")}
            | {"read_at": stmt.excluded.read_at}))
    return len(posts)


async def save_heard(db: AsyncSession, lace_id: uuid.UUID, run_id: uuid.UUID | None,
                     found: list[tuple[dict, HeardItem]]) -> int:
    """Keep what a listen kept, once each: heard again, it stays as it was
    (and where the founder is with it). Returns how many were new."""
    new = 0
    for item, verdict in found:
        stmt = insert(LaceSocialItem).values(
            id=uuid.uuid4(), lace_id=lace_id, platform=item["platform"], key=item_key(item),
            author=(item.get("author") or None) and str(item["author"])[:AUTHOR_CHARS], text=item.get("text") or "",
            url=item.get("url"), said_at=_when(item.get("date")), verdict=verdict.kind, note=verdict.note or "",
            run_id=run_id).on_conflict_do_nothing(constraint="uq_lace_social_items_lace_id_platform_key")
        new += (await db.execute(stmt)).rowcount or 0
    return new


async def posts(db: AsyncSession, lace_id: uuid.UUID, platform: SocialPlatform | None, limit: int) -> list[LaceSocialPost]:
    """Newest first."""
    query = select(LaceSocialPost).where(LaceSocialPost.lace_id == lace_id)
    if platform:
        query = query.where(LaceSocialPost.platform == platform)
    return list((await db.scalars(query.order_by(LaceSocialPost.posted_at.desc().nulls_last()).limit(limit))).all())


async def heard(db: AsyncSession, lace_id: uuid.UUID, platform: SocialPlatform | None, status: HeardStatus | None,
                limit: int) -> list[LaceSocialItem]:
    """What the listens kept, newest first."""
    query = select(LaceSocialItem).where(LaceSocialItem.lace_id == lace_id)
    if platform:
        query = query.where(LaceSocialItem.platform == platform)
    if status:
        query = query.where(LaceSocialItem.status == status)
    order = (LaceSocialItem.said_at.desc().nulls_last(), LaceSocialItem.heard_at.desc())
    return list((await db.scalars(query.order_by(*order).limit(limit))).all())


async def set_status(db: AsyncSession, lace_id: uuid.UUID, item_id: uuid.UUID, status: HeardStatus) -> LaceSocialItem:
    item = await db.scalar(select(LaceSocialItem).where(LaceSocialItem.id == item_id,
                                                        LaceSocialItem.lace_id == lace_id))
    if item is None:
        raise NotFoundError("Not found")
    item.status = status
    await db.commit()
    return item
