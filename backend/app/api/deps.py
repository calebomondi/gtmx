"""Auth dependencies: verify the Supabase access token from the Authorization
header (or a `?token=` query param for WebSockets, which cannot send headers).

Supabase owns identity (no local users table): a verified token IS the user.
`require_user` returns a small AuthUser built from the token's claims/metadata;
no database row is created or looked up."""

import uuid
from dataclasses import dataclass
from typing import Annotated, Optional

from fastapi import Depends, HTTPException, WebSocket, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from supabase import acreate_client

from config import Config

_cfg = Config()
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
