"""Users' connected channel accounts (Gmail, LinkedIn, Instagram, TikTok, X),
held by Composio under the user's id. Composio is the source of truth: it
stores and refreshes the tokens, so there is no local table to drift.

Composio's SDK is synchronous; every call runs in a worker thread.
"""

import asyncio
import uuid
from dataclasses import dataclass
from datetime import datetime
from functools import lru_cache

from composio import Composio

from backend.app.services.errors import ConflictError, NotFoundError
from config import settings

# App platform -> Composio toolkit slug (verified against the live API).
TOOLKITS = {
    "gmail": "gmail",
    "linkedin": "linkedin",
    "instagram": "instagram",
    "tiktok": "tiktok",
    "x": "twitter",
}
PLATFORM_OF = {toolkit: platform for platform, toolkit in TOOLKITS.items()}
# Toolkits Composio manages auth for (verified 2026-10-10). The others need an
# auth config backed by our own OAuth app (settings.composio_auth_configs).
MANAGED = {"gmail", "linkedin", "instagram"}

_STATUS = {"ACTIVE": "live", "INITIATED": "pending", "INITIALIZING": "pending"}


@dataclass
class ConnectionInfo:
    id: str
    platform: str
    status: str  # live | pending | needs_attention
    display_name: str | None
    created_at: datetime | None
    updated_at: datetime | None


@lru_cache(maxsize=1)
def _client() -> Composio:
    return Composio(api_key=settings.composio_api_key)


def available(platform: str) -> bool:
    toolkit = TOOLKITS[platform]
    return toolkit in MANAGED or toolkit in settings.composio_auth_configs


def _auth_configs() -> dict[str, str]:
    return {t: c for t, c in settings.composio_auth_configs.items() if t in PLATFORM_OF}


def _info(account) -> ConnectionInfo | None:
    platform = PLATFORM_OF.get(account.toolkit.slug)
    if platform is None:
        return None
    state = (account.model_dump().get("state") or {}).get("val") or {}
    return ConnectionInfo(
        id=account.id,
        platform=platform,
        status=_STATUS.get(account.status, "needs_attention"),
        display_name=state.get("displayName") or None,
        created_at=account.created_at,
        updated_at=account.updated_at,
    )


async def list_for_user(user_id: uuid.UUID) -> list[ConnectionInfo]:
    def fetch():
        return _client().connected_accounts.list(
            user_ids=[str(user_id)], toolkit_slugs=list(TOOLKITS.values()),
            statuses=["ACTIVE", "INITIALIZING", "INITIATED", "EXPIRED", "FAILED", "INACTIVE"],
        )
    response = await asyncio.to_thread(fetch)
    infos = [_info(a) for a in getattr(response, "items", []) or []]
    # An abandoned Connect Link stays INITIATED until it expires; only show a
    # pending row when the user has nothing live for that platform.
    live = {i.platform for i in infos if i and i.status == "live"}
    return [i for i in infos if i and not (i.status == "pending" and i.platform in live)]


async def start(user_id: uuid.UUID, platform: str) -> str:
    """Begin connecting `platform` for the user; returns the Connect Link URL.
    Composio redirects back to the accounts page, which then re-lists from
    Composio -- the callback's query parameters are never trusted."""
    if platform not in TOOLKITS:
        raise NotFoundError("Unknown channel")
    if not available(platform):
        raise ConflictError(
            f"{platform} needs an app-level OAuth setup before users can connect it."
        )

    def authorize() -> str:
        session = _client().create(
            user_id=str(user_id), manage_connections=False, auth_configs=_auth_configs(),
        )
        request = session.authorize(
            TOOLKITS[platform], callback_url=f"{settings.frontend_base_url}/accounts?connected={platform}",
        )
        return request.redirect_url
    return await asyncio.to_thread(authorize)


async def disconnect(user_id: uuid.UUID, connection_id: str) -> None:
    """Delete the connection (revoking the provider token) if it is the user's."""
    def remove():
        client = _client()
        try:
            account = client.connected_accounts.get(connection_id)
        except Exception:  # noqa: BLE001 -- unknown id and someone else's look the same
            account = None
        if account is None or account.user_id != str(user_id):
            raise NotFoundError("Connection not found")
        client.connected_accounts.delete(connection_id, revoke_on_delete=True)
    await asyncio.to_thread(remove)
