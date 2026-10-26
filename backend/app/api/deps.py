"""Auth and ownership dependencies -- the only place either is enforced.

Identity: verify the Supabase access token from the Authorization header.
Supabase owns identity (no local users table): a verified token IS the user.

Access: every Lace-scoped route resolves its Lace through MemberLace, AdminLace or OwnerLace.
Someone else's Lace is a 404, indistinguishable from a missing one."""

import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Annotated, Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app import supabase_admin
from backend.app.database.connect import get_db
from backend.app.database.lace_models import Lace, LaceMember
from backend.app.services import lace_members
from backend.app.services import limits
from backend.app.services import pilot
from utils.log import current_user_id

_bearer = HTTPBearer(auto_error=False)


@dataclass(frozen=True)
class AuthUser:
    id: uuid.UUID
    email: Optional[str]
    name: Optional[str]
    avatar_url: Optional[str]
    # From Supabase app_metadata.role, which only the service key can write.
    is_admin: bool = False
    # When the account was made: ones made before the pilot closed stay in.
    created_at: Optional[datetime] = None


async def user_from_token(token: str) -> Optional[AuthUser]:
    """Resolve a Supabase access token to an AuthUser. None on invalid token."""
    try:
        client = await supabase_admin.get_client()
        response = await client.auth.get_user(token)
    except Exception:
        return None
    suser = getattr(response, "user", None) if response is not None else None
    if suser is None:
        return None

    if supabase_admin.is_suspended(getattr(suser, "banned_until", None)):
        return None  # an access token outlives a ban by up to an hour; refuse it now

    try:
        uid = uuid.UUID(str(suser.id))
    except (ValueError, AttributeError, TypeError):
        return None

    return AuthUser(
        id=uid,
        email=getattr(suser, "email", None),
        name=supabase_admin.name_of(suser),
        avatar_url=supabase_admin.avatar_of(suser),
        is_admin=supabase_admin.is_admin(getattr(suser, "app_metadata", None)),
        created_at=_when(getattr(suser, "created_at", None)),
    )


def _when(value) -> Optional[datetime]:
    """Supabase gives a datetime or an ISO string, depending on the client."""
    if isinstance(value, datetime) or value is None:
        return value
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None


async def require_user(
    credentials: Annotated[Optional[HTTPAuthorizationCredentials], Depends(_bearer)],
) -> AuthUser:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing Authorization bearer token",
        )
    user = await user_from_token(credentials.credentials)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
        )
    current_user_id.set(str(user.id))  # tags this request's log lines
    return user


CurrentUser = Annotated[AuthUser, Depends(require_user)]
DbSession = Annotated[AsyncSession, Depends(get_db)]


async def get_member_lace(lace_id: uuid.UUID, user: CurrentUser, db: DbSession) -> Lace:
    """A Lace the user is on, in any role; 404 otherwise."""
    return (await lace_members.open_lace(db, lace_id, user.id, "member"))[0]


async def get_admin_lace(lace_id: uuid.UUID, user: CurrentUser, db: DbSession) -> Lace:
    """A Lace the user manages (admin or owner); 403 for a member, 404 for anyone else."""
    return (await lace_members.open_lace(db, lace_id, user.id, "admin"))[0]


async def get_owner_lace(lace_id: uuid.UUID, user: CurrentUser, db: DbSession) -> Lace:
    """A Lace the user owns; 403 for its admins and members, 404 for anyone else."""
    return (await lace_members.open_lace(db, lace_id, user.id, "owner"))[0]


async def get_lace_membership(lace_id: uuid.UUID, user: CurrentUser, db: DbSession) -> LaceMember:
    """The user's place on a Lace they are on (their role, their pin); 404 otherwise."""
    return (await lace_members.open_lace(db, lace_id, user.id, "member"))[1]


# Every route under a Lace takes one of these: the only place access to a Lace is decided.
MemberLace = Annotated[Lace, Depends(get_member_lace)]
AdminLace = Annotated[Lace, Depends(get_admin_lace)]
OwnerLace = Annotated[Lace, Depends(get_owner_lace)]
LaceMembership = Annotated[LaceMember, Depends(get_lace_membership)]


async def require_admin(user: CurrentUser) -> AuthUser:
    """Server-side admin gate for /api/v1/admin/*. A UI check alone is never enough."""
    if not user.is_admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin access required")
    return user


AdminUser = Annotated[AuthUser, Depends(require_admin)]


async def in_pilot(user: CurrentUser, db: DbSession) -> AuthUser:
    """Router-level guard on the customer API while the pilot is closed: only
    people let in may use it (services.pilot)."""
    if not await pilot.may_use(db, user.id, user.email, user.created_at, user.is_admin):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                            detail="Thalace is in a closed pilot. You'll hear from us when you're in.")
    return user


async def rate_limited(user: CurrentUser) -> AuthUser:
    """Router-level guard on the REST API: per-user requests per minute."""
    limits.check_request_rate(user.id)
    return user
