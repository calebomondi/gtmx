import uuid
from typing import Annotated

from fastapi import APIRouter, Depends

from backend.app.api.deps import AuthUser, require_user
from backend.app.schemas.users import UserResponse

router = APIRouter()


@router.get(
    "/me",
    response_model=UserResponse,
)
async def get_current_user(
    current_user: Annotated[AuthUser, Depends(require_user)],
):
    """The verified Supabase user — no local users table; identity comes from Supabase."""
    return UserResponse(
        id=current_user.id,
        name=current_user.name,
        email=current_user.email,
        avatar_url=current_user.avatar_url,
    )
