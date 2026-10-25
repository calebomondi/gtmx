"""Which of its founder's connected apps a Lace may use, and each app's
settings for that Lace.

The default, when the founder hasn't chosen: channels (email, socials) are on
for every Lace, as a founder's identity for outreach; work apps (CRM, sheets,
team, meetings) are on only where the founder switches them on, or when they
have just one Lace, so one startup's Lace never writes into another's CRM.
"""

import uuid

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.database.lace_models import Lace, LaceApp
from backend.app.services import connections as connection_service
from functools import partial

from agents.lace.notion_tools import page_id
from agents.lace.slack_tools import channel_name
from backend.app.services.errors import InvalidInputError, NotFoundError
from data_sources.socials.profiles import profile_handle

# The settings each app takes, and how each value is read (None: not a valid one).
SETTINGS = {
    "slack": {"brief_channel": channel_name},
    "notion": {"brief_page": page_id},
    # The founder's own public account, read by handle with nothing connected.
    "x": {"handle": partial(profile_handle, "x")},
    "tiktok": {"handle": partial(profile_handle, "tiktok")},
}
_INVALID = {"brief_channel": "That isn't a Slack channel name, e.g. #sales.",
            "brief_page": "That isn't a Notion page link.",
            "handle": "That isn't a handle or a profile link, e.g. @acme."}


def _app(platform: str) -> connection_service.App:
    app = connection_service.APP_OF.get(platform)
    if app is None:
        raise NotFoundError("No such app")
    return app


async def _one_lace(db: AsyncSession, user_id: uuid.UUID) -> bool:
    count = await db.scalar(select(func.count()).select_from(Lace).where(
        Lace.user_id == user_id, Lace.status != "archived"))
    return (count or 0) <= 1


async def enabled(db: AsyncSession, lace: Lace, platform: str) -> bool:
    row = await db.scalar(select(LaceApp).where(LaceApp.lace_id == lace.id, LaceApp.platform == platform))
    if row is not None:
        return row.enabled
    return await enabled_default(db, lace, platform)


async def list_for_lace(db: AsyncSession, lace: Lace) -> list[dict]:
    """Every app, with the account this Lace uses for it (its own, or the
    founder's shared one), whether this Lace may use it, and its settings
    for this Lace."""
    rows = {r.platform: r for r in (await db.scalars(select(LaceApp).where(LaceApp.lace_id == lace.id))).all()}
    connected = await connection_service.for_lace(db, lace)
    one_lace = await _one_lace(db, lace.user_id)
    out = []
    for app in connection_service.APPS:
        row, live = rows.get(app.platform), connected.get(app.platform)
        out.append({
            "platform": app.platform, "label": app.label, "group": app.group,
            "connected": live is not None and live.status == "live", "status": live.status if live else None,
            "account": None if live is None else "own" if live.own else "shared",
            "account_name": live.display_name if live else None, "connection_id": live.id if live else None,
            "enabled": row.enabled if row else (app.group == "channels" or one_lace),
            "settings": dict(row.settings) if row else {},
        })
    return out


async def update(db: AsyncSession, lace: Lace, platform: str, enabled: bool | None,
                 settings: dict[str, str] | None) -> None:
    """Switch an app on or off for this Lace and/or replace its settings.
    InvalidInputError for a setting the app doesn't take or a value that
    can't be one; an empty value clears it."""
    _app(platform)
    if settings is not None:
        settings = _checked(platform, settings)
    values: dict = {}
    if enabled is not None:
        values["enabled"] = enabled
    if settings is not None:
        values["settings"] = settings
    if not values:
        return
    default_on = await enabled_default(db, lace, platform)
    stmt = insert(LaceApp).values(id=uuid.uuid4(), lace_id=lace.id, platform=platform,
                                  **{"enabled": default_on, "settings": {}, **values})
    await db.execute(stmt.on_conflict_do_update(constraint="uq_lace_apps_lace_id_platform", set_=values))
    await db.commit()


def _checked(platform: str, settings: dict[str, str]) -> dict[str, str]:
    known = SETTINGS.get(platform, {})
    checked = {}
    for key, value in settings.items():
        if key not in known:
            raise InvalidInputError(f"{connection_service.label(platform)} has no setting {key!r}.")
        if not value.strip():
            continue
        if (read := known[key](value)) is None:
            raise InvalidInputError(_INVALID[key])
        checked[key] = read
    return checked


async def enabled_default(db: AsyncSession, lace: Lace, platform: str) -> bool:
    return _app(platform).group == "channels" or await _one_lace(db, lace.user_id)
