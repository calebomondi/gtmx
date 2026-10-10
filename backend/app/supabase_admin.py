"""The one server-side Supabase client, authenticated with the secret key.
Used to verify access tokens and to manage users' app_metadata (admin role).
Never expose this key or client to a browser."""

from supabase import AsyncClient, acreate_client

from config import settings

ADMIN_ROLE = "admin"

_client: AsyncClient | None = None


async def get_client() -> AsyncClient:
    global _client
    if _client is None:
        _client = await acreate_client(settings.supabase_base_url, settings.supabase_secret_key)
    return _client


def is_admin(app_metadata: dict | None) -> bool:
    return (app_metadata or {}).get("role") == ADMIN_ROLE
