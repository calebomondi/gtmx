"""Emailing a Lace's brief to its founder, when they asked for it and not in
their quiet hours. The brief in the conversation is the record; the email is
a courtesy copy, retried for a day and then let go."""

import re
import uuid
from datetime import datetime, timedelta
from html import escape

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app import supabase_admin
from backend.app.database.connect import AsyncSessionLocal
from backend.app.database.lace_models import Lace, LaceBrief
from backend.app.services import email
from backend.app.services.lace_briefs import zone
from config import settings
from utils.log import logger

# A brief not emailed within this long (quiet hours, Resend down) is not sent late.
EMAIL_MAX_AGE = timedelta(hours=24)

_LINK = re.compile(r"\[([^\]]+)\]\((https?://[^)\s]+)\)")
_BOLD = re.compile(r"\*\*(.+?)\*\*")
_BULLET = re.compile(r"^\s*[-*]\s+(.*)$")
_NUMBERED = re.compile(r"^\s*\d+[.)]\s+(.*)$")
_HEADING = re.compile(r"^\s*#{1,6}\s+(.*)$")
_P = '<p style="margin:0 0 12px;line-height:1.6">'


def in_quiet_hours(lace: Lace, now: datetime) -> bool:
    """Inside the founder's local [quiet_start, quiet_end) window, which may
    wrap midnight (22 to 7)."""
    if lace.quiet_start is None or lace.quiet_end is None:
        return False
    hour = now.astimezone(zone(lace.timezone)).hour
    if lace.quiet_start < lace.quiet_end:
        return lace.quiet_start <= hour < lace.quiet_end
    return hour >= lace.quiet_start or hour < lace.quiet_end


def _inline(text: str) -> str:
    html = escape(text, quote=True)
    html = _LINK.sub(lambda m: f'<a href="{m[2]}" style="color:#b45309">{m[1]}</a>', html)
    return _BOLD.sub(r"<strong>\1</strong>", html)


def to_html(markdown: str) -> str:
    """The brief's markdown as email HTML: paragraphs, bold, links, bullet
    and numbered lists, headings as bold lines. Everything else is text."""
    out: list[str] = []
    open_list: str | None = None
    for line in markdown.splitlines():
        bullet, numbered = _BULLET.match(line), _NUMBERED.match(line)
        item = bullet or numbered
        kind = "ul" if bullet else "ol" if numbered else None
        if open_list and kind != open_list:
            out.append(f"</{open_list}>")
            open_list = None
        if item:
            if open_list is None:
                out.append(f'<{kind} style="margin:0 0 12px;padding-left:20px;line-height:1.6">')
                open_list = kind
            out.append(f"<li>{_inline(item[1])}</li>")
        elif heading := _HEADING.match(line):
            out.append(f"{_P}<strong>{_inline(heading[1])}</strong></p>")
        elif line.strip():
            out.append(f"{_P}{_inline(line.strip())}</p>")
    if open_list:
        out.append(f"</{open_list}>")
    return "".join(out)


def render(lace: Lace, brief: LaceBrief) -> tuple[str, str, str]:
    """(subject, text, html) for one brief."""
    day = brief.created_at.astimezone(zone(lace.timezone)).strftime("%a %d %b")
    link = f"{settings.frontend_base_url.rstrip('/')}/lace/{lace.id}"
    subject = f"{lace.name}'s brief, {day}"
    footer = "You get this because brief emails are on for this Lace. Turn them off in the Lace's Brief settings."
    text = f"{brief.body}\n\nOpen {lace.name}: {link}\n\n{footer}"
    html = to_html(brief.body or "") + f'{_P}<a href="{escape(link)}" style="color:#b45309">Open {escape(lace.name)}</a></p>'
    return subject, text, email.branded_html(html, footer)


async def _founder_email(user_id: uuid.UUID) -> str | None:
    try:
        user = await supabase_admin.get_user(user_id)
    except Exception:  # noqa: BLE001 -- the email is retried at the next sweep
        logger.exception("Looking up the founder %s for the brief email failed", user_id)
        return None
    return getattr(user, "email", None) or None


async def deliver(db: AsyncSession, brief: LaceBrief, lace: Lace, now: datetime) -> bool:
    """Email one posted brief if the founder wants it, it is not their quiet
    hours, and it is fresh. True when sent; the caller commits."""
    if not (lace.brief_email and brief.body and brief.posted_at) or brief.emailed_at is not None:
        return False
    if now - brief.created_at > EMAIL_MAX_AGE or in_quiet_hours(lace, now):
        return False
    to = await _founder_email(lace.user_id)
    if to is None:
        return False
    if not await email.send(to, *render(lace, brief)):
        return False
    brief.emailed_at = now
    return True


async def email_brief(brief_id: uuid.UUID, now: datetime) -> None:
    """Email a brief just posted. Never raises: the brief is already in the
    conversation, and a missed email is retried by the sweep."""
    if not email.configured():
        return
    try:
        async with AsyncSessionLocal() as db, db.begin():
            row = (await db.execute(select(LaceBrief, Lace).join(Lace, Lace.id == LaceBrief.lace_id)
                                    .where(LaceBrief.id == brief_id))).first()
            if row is not None:
                await deliver(db, row[0], row[1], now)
    except Exception:  # noqa: BLE001 -- see docstring
        logger.exception("Emailing brief %s failed", brief_id)


async def email_waiting(now: datetime) -> int:
    """Email posted briefs held back by quiet hours or a failed send. Returns
    how many were sent."""
    if not email.configured():
        return 0
    sent = 0
    async with AsyncSessionLocal() as db:
        rows = (await db.execute(select(LaceBrief, Lace).join(Lace, Lace.id == LaceBrief.lace_id).where(
            Lace.brief_email.is_(True), LaceBrief.posted_at.is_not(None), LaceBrief.emailed_at.is_(None),
            LaceBrief.created_at >= now - EMAIL_MAX_AGE))).all()
        for brief, lace in rows:
            # Committed one by one, so a later failure never re-sends an earlier email.
            if await deliver(db, brief, lace, now):
                await db.commit()
                sent += 1
    return sent
