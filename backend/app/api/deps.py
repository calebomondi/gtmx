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
from supabase import acreate_client

from backend.app.database import models
from backend.app.database.connect import get_db
from backend.app.services import projects as project_service
from backend.app.services import workspaces as workspace_service

from config import get_settings

_cfg = get_settings()
_bearer = HTTPBearer(auto_error=False)

_client = None


@dataclass(frozen=True)
class AuthUser:
    id: uuid.UUID
    email: Optional[str]
    name: Optional[str]
    avatar_url: Optional[str]


async def _get_client():
    global _client
    if _client is None:
        _client = await acreate_client(_cfg.supabase_base_url, _cfg.supabase_secret_key)
    return _client


async def user_from_token(token: str) -> Optional[AuthUser]:
    """Resolve a Supabase access token to an AuthUser. None on invalid token."""
    try:
        client = await _get_client()
        response = await client.auth.get_user(token)
    except Exception:
        return None
    suser = getattr(response, "user", None) if response is not None else None
    if suser is None:
        return None

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
