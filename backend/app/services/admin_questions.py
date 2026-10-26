"""What founders ask their Laces: each `lace_turn` run's message, newest
first. Founders' own words, so this is shown to admins only, behind
require_admin like every admin route."""

import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.database import models
from backend.app.database.lace_models import Lace
from backend.app.schemas.admin import AdminQuestionRow, Page
from backend.app.services.admin_directory import emails_by_id
from backend.app.services.lace_search import MAX_QUERY_LEN, contains


async def list_questions(
    db: AsyncSession, page: int, per_page: int, *, q: str | None = None,
    user_id: uuid.UUID | None = None, lace_id: uuid.UUID | None = None,
) -> Page[AdminQuestionRow]:
    r = models.Run
    text = r.input["text"].astext
    filters = [r.kind == "lace_turn", text.is_not(None)]
    if q and q.strip():
        filters.append(contains(text, q.strip()[:MAX_QUERY_LEN]))
    filters += [col == value for col, value in ((r.user_id, user_id), (r.lace_id, lace_id)) if value is not None]
    total = await db.scalar(select(func.count()).select_from(r).where(*filters))
    rows = (await db.execute(
        select(r.id, r.user_id, r.lace_id, Lace.name, text, r.status, r.created_at)
        .outerjoin(Lace, Lace.id == r.lace_id).where(*filters)
        .order_by(r.created_at.desc()).offset((page - 1) * per_page).limit(per_page)
    )).all()
    emails = await emails_by_id() if rows else {}
    return Page(
        items=[AdminQuestionRow(run_id=run_id, user_id=uid, user_email=emails.get(uid), lace_id=lid, lace_name=name,
                                text=body, status=status, created_at=created)
               for run_id, uid, lid, name, body, status, created in rows],
        total=total or 0, page=page, per_page=per_page,
    )
