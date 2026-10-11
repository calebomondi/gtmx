"""Search Anything over the signed-in user's own data."""

from typing import Annotated

from fastapi import APIRouter, Query

from backend.app.api.deps import CurrentUser, DbSession
from backend.app.schemas.search import SearchResponse
from backend.app.services import search as search_service

router = APIRouter()

MAX_PER_KIND = 10


@router.get("", response_model=SearchResponse)
async def search(
    user: CurrentUser,
    db: DbSession,
    q: Annotated[str, Query(max_length=search_service.MAX_QUERY_LEN)],
    limit: Annotated[int, Query(ge=1, le=MAX_PER_KIND)] = 5,
):
    """Workspaces, projects, competitors, accounts and feed signals whose name
    matches `q`. Shorter than two characters matches nothing."""
    return SearchResponse(hits=await search_service.search(db, user.id, q, limit))
