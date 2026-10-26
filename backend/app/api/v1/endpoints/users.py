from typing import Annotated

from fastapi import APIRouter, Depends

from backend.app.api.deps import AuthUser, DbSession, require_user
from backend.app.schemas.users import UserResponse
from backend.app.services import pilot

router = APIRouter()


@router.get(
    "/me",
    response_model=UserResponse,
)
async def get_current_user(
    current_user: Annotated[AuthUser, Depends(require_user)], db: DbSession,
):
    """The verified Supabase user — no local users table; identity comes from
    Supabase — and whether they may use the app while the pilot is closed."""
    return UserResponse(
        id=current_user.id,
        name=current_user.name,
        email=current_user.email,
        avatar_url=current_user.avatar_url,
        in_pilot=await pilot.may_use(db, current_user.id, current_user.email, current_user.created_at,
                                     current_user.is_admin),
    )
