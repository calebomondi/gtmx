"""The one server-side Supabase client, authenticated with the secret key.
Used to verify access tokens and to manage users' app_metadata (admin role).
Never expose this key or client to a browser."""

from datetime import UTC, datetime

from supabase import AsyncClient, acreate_client

from config import settings

ADMIN_ROLE = "admin"

_client: AsyncClient | None = None


async def get_client() -> AsyncClient:
    global _client
    if _client is None:
        _client = await acreate_client(settings.supabase_base_url, settings.supabase_secret_key)
    return _client


async def get_user(user_id) -> object:
    """The Supabase user, outside a request (no access token to read it from)."""
    client = await get_client()
    return (await client.auth.admin.get_user_by_id(str(user_id))).user


def name_of(user) -> str | None:
    """The name a user gave (or their sign-in provider did), if any."""
    metadata = getattr(user, "user_metadata", None) or {}
    return metadata.get("full_name") or metadata.get("name")


def avatar_of(user) -> str | None:
    metadata = getattr(user, "user_metadata", None) or {}
    return metadata.get("avatar_url") or metadata.get("picture")


def is_admin(app_metadata: dict | None) -> bool:
    return (app_metadata or {}).get("role") == ADMIN_ROLE


def is_suspended(banned_until) -> bool:
    """Suspension is a Supabase ban; `banned_until` arrives as str or datetime."""
    if isinstance(banned_until, str):
        banned_until = datetime.fromisoformat(banned_until.replace("Z", "+00:00"))
    return banned_until is not None and banned_until > datetime.now(UTC)
