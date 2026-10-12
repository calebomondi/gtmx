"""Users' connected channel accounts (Gmail, LinkedIn, Instagram, TikTok, X),
held by Composio under the user's id. Composio is the source of truth: it
stores and refreshes the tokens, so there is no local table to drift.

Composio's SDK is synchronous; every call runs in a worker thread.
"""

import asyncio
import uuid
from dataclasses import dataclass
from urllib.parse import urlsplit
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


# Bounds the admin-wide listing: 20 pages x 100 covers far past launch scale.
_LIST_PAGE_SIZE = 100
_LIST_MAX_PAGES = 20
_LIST_TIMEOUT_S = 20.0


async def live_by_user() -> dict[uuid.UUID, set[str]]:
    """Every user's live platforms, in one paged pass (admin metrics)."""
    def fetch() -> list:
        items, cursor = [], None
        for _ in range(_LIST_MAX_PAGES):
            response = _client().connected_accounts.list(
                toolkit_slugs=list(TOOLKITS.values()), statuses=["ACTIVE"], limit=_LIST_PAGE_SIZE,
                timeout=_LIST_TIMEOUT_S, **({"cursor": cursor} if cursor else {}),
            )
            items.extend(getattr(response, "items", []) or [])
            cursor = getattr(response, "next_cursor", None)
            if not cursor:
                break
        return items
    live: dict[uuid.UUID, set[str]] = {}
    for account in await asyncio.to_thread(fetch):
        platform = PLATFORM_OF.get(account.toolkit.slug)
        try:
            user_id = uuid.UUID(str(account.user_id))
        except ValueError:
            continue  # not one of our users (Composio playground, other apps on the key)
        if platform:
            live.setdefault(user_id, set()).add(platform)
    return live


_LOOPBACK = {"localhost", "127.0.0.1"}


def _same_site(origin: str, allowed: str) -> bool:
    """Exact match, or the same loopback port under its other name: the
    browser keeps localhost and 127.0.0.1 sessions apart, so returning a user
    to the wrong one signs them out."""
    a, b = urlsplit(origin), urlsplit(allowed.rstrip("/"))
    if (a.scheme, a.netloc) == (b.scheme, b.netloc):
        return True
    return (a.scheme == b.scheme and a.port == b.port
            and a.hostname in _LOOPBACK and b.hostname in _LOOPBACK)


def return_base(origin: str | None) -> str:
    """Where Composio sends the user back: the app origin they started from
    when it is one we serve, else the configured frontend."""
    if origin and any(_same_site(origin, a) for a in [settings.frontend_base_url, *settings.allowed_origins]):
        return origin.rstrip("/")
    return settings.frontend_base_url.rstrip("/")


async def start(user_id: uuid.UUID, platform: str, origin: str | None = None) -> str:
    """Begin connecting `platform` for the user; returns the Connect Link URL.
    Composio redirects back to the accounts page, which then re-lists from
    Composio -- the callback's query parameters are never trusted."""
    if platform not in TOOLKITS:
        raise NotFoundError("Unknown channel")
    if not available(platform):
        raise ConflictError(
            f"{platform} needs an app-level OAuth setup before users can connect it."
        )

    base = return_base(origin)

    def authorize() -> str:
        session = _client().create(
            user_id=str(user_id), manage_connections=False, auth_configs=_auth_configs(),
        )
        request = session.authorize(
            TOOLKITS[platform], callback_url=f"{base}/accounts?connected={platform}",
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


def execute_tool(user_id: uuid.UUID, tool_slug: str, arguments: dict, connected_account_id: str) -> dict:
    """Run one Composio tool as the user through a specific connected account.
    Synchronous: call it in a worker thread. Returns {data, error, log_id}."""
    session = _client().create(user_id=str(user_id), manage_connections=False, auth_configs=_auth_configs())
    response = session.execute(tool_slug, arguments=arguments, account=connected_account_id)
    return {"data": response.data, "error": response.error, "log_id": response.log_id}
