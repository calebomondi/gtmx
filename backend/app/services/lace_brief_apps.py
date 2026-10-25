"""A Lace's brief, also posted to the Slack channel, saved under the Notion
page and sent to the Telegram chat the founder chose in its settings: their setting is the approval, as
"Email me the brief" is for email. Each delivery is recorded as an app action
(so it shows in what the Lace did, failures too) and never made twice."""

import uuid

from sqlalchemy import select

from backend.app.database.connect import AsyncSessionLocal
from backend.app.database.lace_models import Lace, LaceApp, LaceAppAction, LaceBrief
from backend.app.services import lace_app_actions
from backend.app.services import notion_actions, slack_actions, telegram_actions  # noqa: F401 -- registers the runners used here
from backend.app.services.lace_briefs import zone
from utils.log import logger

# Each app's limit for one message; a longer brief is cut, with a pointer to the rest.
SLACK_CHARS = 4000
TELEGRAM_CHARS = 4096
_CUT = "\n\n…the rest is in Thalace."


def _fitted(text: str, limit: int) -> str:
    return text if len(text) <= limit else text[:limit - len(_CUT)].rstrip() + _CUT


def _slack_text(lace: Lace, body: str) -> str:
    return _fitted(f"*{lace.name}'s brief*\n\n{body.strip()}", SLACK_CHARS)


def _telegram_text(lace: Lace, body: str) -> str:
    """Plain text: Telegram's markdown modes reject unescaped characters a
    brief is full of."""
    return _fitted(f"{lace.name}'s brief\n\n{body.strip()}", TELEGRAM_CHARS)


async def _delivered(db, brief_id: uuid.UUID, app: str) -> bool:
    return await db.scalar(select(LaceAppAction.id).where(
        LaceAppAction.app == app, LaceAppAction.arguments["brief_id"].as_string() == str(brief_id)).limit(1)) is not None


async def deliver(brief_id: uuid.UUID) -> None:
    """Post a brief just written wherever its Lace's settings say. Never
    raises: the brief is already in the conversation."""
    try:
        async with AsyncSessionLocal() as db:
            brief = await db.get(LaceBrief, brief_id)
            lace = await db.get(Lace, brief.lace_id) if brief else None
            if lace is None or not (brief.body or "").strip():
                return
            settings = {row.platform: row.settings for row in (await db.scalars(select(LaceApp).where(
                LaceApp.lace_id == lace.id, LaceApp.platform.in_(("slack", "notion", "telegram"))))).all()}
            day = brief.created_at.astimezone(zone(lace.timezone)).strftime("%a %d %b %Y")
            channel = (settings.get("slack") or {}).get("brief_channel")
            if channel and not await _delivered(db, brief_id, "slack"):
                await lace_app_actions.run_standing(
                    db, lace, "slack", "post_message", f"Brief posted in #{channel}", brief.body[:600],
                    {"channel": channel, "text": _slack_text(lace, brief.body), "brief_id": str(brief_id)})
            page = (settings.get("notion") or {}).get("brief_page")
            if page and not await _delivered(db, brief_id, "notion"):
                title = f"{lace.name}'s brief, {day}"
                await lace_app_actions.run_standing(
                    db, lace, "notion", "create_page", f"Brief saved in Notion: {title}", brief.body[:600],
                    {"parent_id": page, "title": title, "content": brief.body, "brief_id": str(brief_id)})
            chat = (settings.get("telegram") or {}).get("brief_chat")
            if chat and not await _delivered(db, brief_id, "telegram"):
                await lace_app_actions.run_standing(
                    db, lace, "telegram", "send_message", f"Brief sent to {chat} on Telegram", brief.body[:600],
                    {"chat_id": chat, "text": _telegram_text(lace, brief.body), "brief_id": str(brief_id)})
    except Exception:  # noqa: BLE001 -- see docstring
        logger.exception("Delivering brief %s to the founder's apps failed", brief_id)
