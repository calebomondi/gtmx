from fastapi import APIRouter

from backend.app.api.deps import AdminUser
from backend.app.schemas.users import UserResponse

router = APIRouter()


@router.get("/me", response_model=UserResponse)
async def admin_me(user: AdminUser):
    """The signed-in admin. The dashboard calls this to gate its login: a
    non-admin gets 403 here before any admin data is requested."""
    return UserResponse(id=user.id, name=user.name, email=user.email, avatar_url=user.avatar_url)
