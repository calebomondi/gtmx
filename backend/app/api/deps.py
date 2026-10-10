"""Auth and ownership dependencies -- the only place either is enforced.

Identity: verify the Supabase access token from the Authorization header (or a
`?token=` query param for WebSockets, which cannot send headers). Supabase owns
identity (no local users table): a verified token IS the user.

Ownership: every workspace- or project-scoped route resolves its resource
through OwnedWorkspace / OwnedProject. Someone else's resource is a 404,
indistinguishable from a missing one."""

import uuid
from dataclasses import dataclass
from typing import Annotated, Optional

from fastapi import Depends, HTTPException, WebSocket, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app import supabase_admin
from backend.app.database import models
from backend.app.database.connect import get_db
from backend.app.services import limits
from backend.app.services import projects as project_service
from backend.app.services import workspaces as workspace_service

_bearer = HTTPBearer(auto_error=False)


@dataclass(frozen=True)
class AuthUser:
    id: uuid.UUID
    email: Optional[str]
    name: Optional[str]
    avatar_url: Optional[str]
    # From Supabase app_metadata.role, which only the service key can write.
    is_admin: bool = False


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

    metadata = getattr(suser, "user_metadata", None) or {}
    return AuthUser(
        id=uid,
        email=getattr(suser, "email", None),
        name=metadata.get("full_name") or metadata.get("name"),
        avatar_url=metadata.get("avatar_url") or metadata.get("picture"),
        is_admin=supabase_admin.is_admin(getattr(suser, "app_metadata", None)),
    )


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
    return user


async def require_matching_user(
    user_id: uuid.UUID,
    current_user: Annotated[AuthUser, Depends(require_user)],
) -> AuthUser:
    """For `/user/{user_id}/...` routes: the caller must BE that user."""
    if current_user.id != user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot access another user's resources",
        )
    return current_user


async def websocket_user(websocket: WebSocket) -> Optional[AuthUser]:
    token = websocket.query_params.get("token")
    if not token:
        return None
    return await user_from_token(token)


CurrentUser = Annotated[AuthUser, Depends(require_user)]
DbSession = Annotated[AsyncSession, Depends(get_db)]


async def get_owned_workspace(workspace_id: uuid.UUID, user: CurrentUser, db: DbSession) -> models.Workspace:
    return await workspace_service.get_owned(db, user.id, workspace_id)


async def get_owned_project(project_id: uuid.UUID, user: CurrentUser, db: DbSession) -> models.Project:
    return await project_service.get_owned(db, user.id, project_id)


OwnedWorkspace = Annotated[models.Workspace, Depends(get_owned_workspace)]
OwnedProject = Annotated[models.Project, Depends(get_owned_project)]
MatchingUser = Annotated[AuthUser, Depends(require_matching_user)]


async def require_admin(user: CurrentUser) -> AuthUser:
    """Server-side admin gate for /api/v1/admin/*. A UI check alone is never enough."""
    if not user.is_admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin access required")
    return user


AdminUser = Annotated[AuthUser, Depends(require_admin)]


async def rate_limited(user: CurrentUser) -> AuthUser:
    """Router-level guard on the REST API: per-user requests per minute."""
    limits.check_request_rate(user.id)
    return user
