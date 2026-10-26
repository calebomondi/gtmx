"""Founders' connected app accounts (Gmail, LinkedIn, Notion...), held by
Composio. Composio is the source of truth: it stores and refreshes the tokens.
The only local state is each account's display label (`ConnectionIdentity`),
read once from the provider so the app can say which account is connected.

Composio holds accounts under an id we choose (an "entity"). A founder's
shared accounts are under their user id, and every Lace may use them. A Lace's
own accounts are under `lace:<lace id>`, for a founder whose startups each have
their own email and socials: where a Lace has its own account for an app, it
uses that one and never the shared one (`for_lace`).

Composio's SDK is synchronous; every call runs in a worker thread.
"""

import asyncio
import re
import uuid
from dataclasses import dataclass
from typing import Literal
from urllib.parse import urlsplit
from datetime import datetime
from functools import lru_cache

from composio import Composio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.database import models
from backend.app.database.lace_models import Lace
from backend.app.services.errors import ConflictError, InvalidInputError, NotFoundError
from config import settings
from utils.log import logger

AppGroup = Literal["channels", "crm", "docs", "team", "meetings"]


@dataclass(frozen=True)
class App:
    """An app the founder can connect: its Composio toolkit, its name, what a
    Lace uses it for, and whether Composio manages its sign-in (the others
    need our own OAuth app, in settings.composio_auth_configs)."""
    platform: str
    toolkit: str
    label: str
    group: AppGroup
    managed: bool


# Every app the founder can connect. Toolkits and managed sign-in verified
# against the live Composio API (2026-10-10; the second wave 2026-10-24).
APPS = (
    App("gmail", "gmail", "Gmail", "channels", True),
    App("outlook", "outlook", "Outlook", "channels", True),
    App("googlecalendar", "googlecalendar", "Google Calendar", "meetings", True),
    App("linkedin", "linkedin", "LinkedIn", "channels", True),
    App("instagram", "instagram", "Instagram", "channels", True),
    App("facebook", "facebook", "Facebook", "channels", True),
    App("tiktok", "tiktok", "TikTok", "channels", False),
    App("x", "twitter", "X", "channels", False),
    App("whatsapp", "whatsapp", "WhatsApp Business", "channels", True),
    # A bot, connected by the token @BotFather gives (an API-key auth config of ours).
    App("telegram", "telegram", "Telegram", "channels", False),
    App("zoho", "zoho", "Zoho CRM", "crm", True),
    App("hubspot", "hubspot", "HubSpot", "crm", True),
    App("googlesheets", "googlesheets", "Google Sheets", "docs", True),
    App("notion", "notion", "Notion", "docs", True),
    App("slack", "slack", "Slack", "team", True),
    App("asana", "asana", "Asana", "team", True),
    App("calendly", "calendly", "Calendly", "meetings", True),
)
TOOLKITS = {app.platform: app.toolkit for app in APPS}
PLATFORM_OF = {app.toolkit: app.platform for app in APPS}
MANAGED = {app.toolkit for app in APPS if app.managed}

_STATUS = {"ACTIVE": "live", "INITIATED": "pending", "INITIALIZING": "pending"}
_LABEL = {app.platform: app.label for app in APPS}
APP_OF = {app.platform: app for app in APPS}


def response_field(data, field: str) -> str | None:
    """A field of a platform API response, which Composio may or may not wrap in `data`."""
    if not isinstance(data, dict):
        return None
    inner = data.get("data") if isinstance(data.get("data"), dict) else data
    return inner.get(field)


_LACE_ENTITY = "lace:"


def founder_entity(user_id: uuid.UUID) -> str:
    """Where the founder's shared accounts are held."""
    return str(user_id)


def lace_entity(lace_id: uuid.UUID) -> str:
    """Where a Lace's own accounts are held."""
    return f"{_LACE_ENTITY}{lace_id}"


def label(platform: str) -> str:
    """The platform's name as the founder knows it: "LinkedIn", "X"."""
    return _LABEL.get(platform, platform.title())


@dataclass
class ConnectionInfo:
    id: str
    platform: str
    status: str  # live | pending | needs_attention
    display_name: str | None
    created_at: datetime | None
    updated_at: datetime | None
    # Whose account it is: a founder's (shared) or one Lace's own.
    entity: str

    @property
    def own(self) -> bool:
        """One Lace's own account, not the founder's shared one."""
        return self.entity.startswith(_LACE_ENTITY)


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
        entity=str(account.user_id),
    )


def _handle(value) -> str | None:
    return f"@{value}" if value else None


def _linkedin_name(data: dict) -> str | None:
    first = data.get("localizedFirstName") or data.get("firstName")
    last = data.get("localizedLastName") or data.get("lastName")
    name = " ".join(part for part in (first, last) if isinstance(part, str) and part)
    return name or None


# Platform -> (Composio tool that returns the account's own profile, its
# arguments, how to read the label from the response). Response fields were
# checked against each tool's published output schema (2026-10-12).
_IDENTITY = {
    "gmail": ("GMAIL_GET_PROFILE", {"user_id": "me"}, lambda d: d.get("emailAddress")),
    "outlook": ("OUTLOOK_OUTLOOK_GET_PROFILE", {"user_id": "me"},
                lambda d: (d.get("response_data") or {}).get("mail") or (d.get("response_data") or {}).get("userPrincipalName")),
    "googlecalendar": ("GOOGLECALENDAR_GET_CALENDAR_PROFILE", {}, lambda d: d.get("id") or d.get("summary")),
    "linkedin": ("LINKEDIN_GET_MY_INFO", {}, _linkedin_name),
    "instagram": ("INSTAGRAM_GET_USER_INFO", {}, lambda d: _handle(d.get("username"))),
    "facebook": ("FACEBOOK_GET_CURRENT_USER", {}, lambda d: d.get("name")),
    "x": ("TWITTER_USER_LOOKUP_ME", {}, lambda d: _handle((d.get("data") or {}).get("username"))),
    "telegram": ("TELEGRAM_GET_ME", {}, lambda d: _handle((d.get("result") or d).get("username"))),
}
_IDENTITY_TIMEOUT_S = 15.0


def _read_identity(info: ConnectionInfo) -> str | None:
    """The account's label from the provider, or None if it can't be read."""
    tool, arguments, label_of = _IDENTITY[info.platform]
    try:
        result = execute_tool(info.entity, tool, arguments, info.id)
    except Exception:  # noqa: BLE001 -- the label is cosmetic; listing must not fail on it
        logger.exception("Reading the %s identity for connection %s failed", info.platform, info.id)
        return None
    if result["error"] or not isinstance(result["data"], dict):
        logger.info("No %s identity for connection %s: %s", info.platform, info.id, result["error"])
        return None
    label = label_of(result["data"])
    return label.strip()[:255] if isinstance(label, str) and label.strip() else None


async def _with_identities(db: AsyncSession, user_id: uuid.UUID, infos: list[ConnectionInfo]) -> list[ConnectionInfo]:
    """Label each live connection with who it is, reading unknown ones from
    the provider once and remembering them (under the founder, for a Lace's
    own accounts too)."""
    stored = {
        row.connection_id: row.label for row in (await db.execute(
            select(models.ConnectionIdentity).where(models.ConnectionIdentity.user_id == user_id)
        )).scalars()
    }
    missing = [i for i in infos if i.status == "live" and i.id not in stored and i.platform in _IDENTITY]
    if missing:
        labels = await asyncio.gather(*(
            asyncio.wait_for(asyncio.to_thread(_read_identity, i), _IDENTITY_TIMEOUT_S) for i in missing
        ), return_exceptions=True)
        for info, label in zip(missing, labels):
            if isinstance(label, str):
                db.add(models.ConnectionIdentity(connection_id=info.id, user_id=user_id, platform=info.platform, label=label))
                stored[info.id] = label
        await db.commit()
    return [
        ConnectionInfo(**{**i.__dict__, "display_name": stored.get(i.id) or i.display_name}) for i in infos
    ]


async def _list(db: AsyncSession, user_id: uuid.UUID, entities: list[str]) -> list[ConnectionInfo]:
    """The accounts held under `entities`, all of them the founder's."""
    def fetch():
        return _client().connected_accounts.list(
            user_ids=entities, toolkit_slugs=list(TOOLKITS.values()),
            statuses=["ACTIVE", "INITIALIZING", "INITIATED", "EXPIRED", "FAILED", "INACTIVE"],
        )
    response = await asyncio.to_thread(fetch)
    infos = [_info(a) for a in getattr(response, "items", []) or []]
    # An abandoned Connect Link stays INITIATED until it expires; only show a
    # pending row when that entity has nothing live for that platform.
    live = {(i.entity, i.platform) for i in infos if i and i.status == "live"}
    shown = [i for i in infos if i and not (i.status == "pending" and (i.entity, i.platform) in live)]
    return await _with_identities(db, user_id, shown)


async def list_for_user(db: AsyncSession, user_id: uuid.UUID) -> list[ConnectionInfo]:
    """The founder's shared accounts."""
    return await _list(db, user_id, [founder_entity(user_id)])


async def list_with_laces(db: AsyncSession, user_id: uuid.UUID) -> list[ConnectionInfo]:
    """The founder's shared accounts and every one of their Laces' own (admin)."""
    laces = (await db.scalars(select(Lace.id).where(Lace.user_id == user_id))).all()
    return await _list(db, user_id, [founder_entity(user_id), *(lace_entity(i) for i in laces)])


async def for_lace(db: AsyncSession, lace: Lace) -> dict[str, ConnectionInfo]:
    """platform -> the account `lace` uses for it: its own when it has one
    (even one needing attention, so it never falls back to sending as another
    startup), else the founder's shared one. A Connect Link left pending
    doesn't count as its own."""
    infos = await _list(db, lace.user_id, [lace_entity(lace.id), founder_entity(lace.user_id)])
    chosen: dict[str, ConnectionInfo] = {}
    for info in sorted(infos, key=lambda i: (i.own and i.status != "pending", i.status == "live")):
        chosen[info.platform] = info
    return chosen


async def connection_for(db: AsyncSession, lace: Lace, platform: str) -> ConnectionInfo | None:
    """The live account `lace` uses for `platform`, or None (see for_lace)."""
    info = (await for_lace(db, lace)).get(platform)
    return info if info is not None and info.status == "live" else None


# Bounds the admin-wide listing: 20 pages x 100 covers far past launch scale.
_LIST_PAGE_SIZE = 100
_LIST_MAX_PAGES = 20
_LIST_TIMEOUT_S = 20.0


async def live_by_user(db: AsyncSession) -> dict[uuid.UUID, set[str]]:
    """Every user's live platforms, shared or a Lace's own, in one paged pass
    (admin metrics)."""
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
    accounts = await asyncio.to_thread(fetch)
    lace_ids = {_lace_id(str(a.user_id)) for a in accounts} - {None}
    owner_of = dict((await db.execute(select(Lace.id, Lace.user_id).where(Lace.id.in_(lace_ids)))).tuples().all()) \
        if lace_ids else {}
    live: dict[uuid.UUID, set[str]] = {}
    for account in accounts:
        platform = PLATFORM_OF.get(account.toolkit.slug)
        entity = str(account.user_id)
        lace_id = _lace_id(entity)
        user_id = owner_of.get(lace_id) if lace_id else _uuid(entity)
        # None: not one of our users (Composio playground, other apps on the key) or a deleted Lace.
        if platform and user_id:
            live.setdefault(user_id, set()).add(platform)
    return live


def _uuid(value: str) -> uuid.UUID | None:
    try:
        return uuid.UUID(value)
    except ValueError:
        return None


def _lace_id(entity: str) -> uuid.UUID | None:
    return _uuid(entity.removeprefix(_LACE_ENTITY)) if entity.startswith(_LACE_ENTITY) else None


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


# Where a connection may return the user: an app path, never another site.
_RETURN_PATH = re.compile(r"^/(?!/)[A-Za-z0-9_\-./]{0,200}$")
_DEFAULT_RETURN = "/accounts"


def return_path(path: str | None) -> str:
    """`path` when it is a plain path within the app (e.g. a Lace's
    Messaging), else the accounts page. InvalidInputError for anything that
    could leave the app."""
    if not path:
        return _DEFAULT_RETURN
    if not _RETURN_PATH.match(path) or ".." in path:
        raise InvalidInputError("That isn't a page in the app.")
    return path


async def start(entity: str, platform: str, origin: str | None = None, return_to: str | None = None) -> str:
    """Begin connecting `platform` under `entity` (the founder's shared
    accounts, or one Lace's own); returns the Connect Link URL.
    Composio redirects back to `return_to` (an app path; the accounts page by
    default) with ?connected=<platform>, and that page re-lists from Composio
    -- the callback's query parameters are never trusted."""
    path = return_path(return_to)
    if platform not in TOOLKITS:
        raise NotFoundError("Unknown channel")
    if not available(platform):
        raise ConflictError(
            f"{platform} needs an app-level OAuth setup before users can connect it."
        )

    base = return_base(origin)

    def authorize() -> str:
        # One connection per app: tools can't choose between two (see execute_tool).
        live = _client().connected_accounts.list(
            user_ids=[entity], toolkit_slugs=[TOOLKITS[platform]], statuses=["ACTIVE"],
        )
        if getattr(live, "items", None):
            raise ConflictError(
                f"A {_LABEL[platform]} account is already connected here. Disconnect it first to connect a different one."
            )
        session = _client().create(
            user_id=entity, manage_connections=False, auth_configs=_auth_configs(),
        )
        request = session.authorize(
            TOOLKITS[platform], callback_url=f"{base}{path}?connected={platform}",
        )
        return request.redirect_url
    return await asyncio.to_thread(authorize)


async def disconnect(db: AsyncSession, entity: str, connection_id: str) -> None:
    """Delete the connection (revoking the provider token) if it is held
    under `entity`."""
    def remove():
        client = _client()
        try:
            account = client.connected_accounts.get(connection_id)
        except Exception:  # noqa: BLE001 -- unknown id and someone else's look the same
            account = None
        if account is None or account.user_id != entity:
            raise NotFoundError("Connection not found")
        client.connected_accounts.delete(connection_id, revoke_on_delete=True)
    await asyncio.to_thread(remove)
    identity = await db.get(models.ConnectionIdentity, connection_id)
    if identity is not None:
        await db.delete(identity)
        await db.commit()


async def remove_all(entity: str) -> None:
    """Delete every account held under `entity` (a deleted Lace's own),
    revoking their tokens. Failures are logged, not raised: the Lace is
    already gone, and an account left behind is never used again."""
    def remove():
        client = _client()
        for account in getattr(client.connected_accounts.list(user_ids=[entity]), "items", []) or []:
            try:
                client.connected_accounts.delete(account.id, revoke_on_delete=True)
            except Exception:  # noqa: BLE001 -- the SDK raises many types
                logger.exception("Removing connection %s of %s failed", account.id, entity)
    try:
        await asyncio.to_thread(remove)
    except Exception:  # noqa: BLE001 -- listing them failed (Composio down)
        logger.exception("Listing the connections of %s to remove them failed", entity)


def execute_tool(entity: str, tool_slug: str, arguments: dict, connected_account_id: str) -> dict:
    """Run one Composio tool as `entity` (a founder, or one of their Laces).
    Synchronous: call it in a worker thread. Returns {data, error, log_id}.

    Composio picks the entity's connection for the tool's app itself: our
    project has no multi-account selection (naming an account is rejected),
    and `start` allows one connection per app per entity, so that pick is the
    connection the caller checked is live. Its id is only kept for the log."""
    session = _client().create(user_id=entity, manage_connections=False, auth_configs=_auth_configs())
    response = session.execute(tool_slug, arguments=arguments)
    if response.error:
        logger.info("Composio %s via connection %s failed: %s", tool_slug, connected_account_id, response.error)
    return {"data": response.data, "error": response.error, "log_id": response.log_id}
