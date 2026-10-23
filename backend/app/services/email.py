"""Transactional email (Thalace's own messages, never a user's outreach) via
Resend's HTTP API. Users' outreach goes through their own Gmail instead."""

from html import escape

import httpx

from config import settings
from utils.log import logger

_RESEND_URL = "https://api.resend.com/emails"
_SITE = "https://thalace.com"
# Lace's small face beside the wordmark: an orange square with two dark square
# eyes, drawn with inline blocks because email clients drop SVG and positioning.
_EYE = '<span style="display:inline-block;width:6px;height:6px;background:#1F1F1F"></span>'
_MARK = (
    '<div style="display:flex;align-items:center;gap:8px;margin-bottom:24px">'
    '<span style="display:inline-block;box-sizing:border-box;width:20px;height:20px;padding:5px 0 0 3px;'
    f'background:#FEA853;border-radius:2px;font-size:0;line-height:0">{_EYE}'
    f'{_EYE.replace("display:inline-block;", "display:inline-block;margin-left:2px;")}</span>'
    '<span style="font-size:20px;letter-spacing:-.01em;color:#1c1917">Thalace</span></div>'
)


def branded_html(body: str, footer: str) -> str:
    """`body` (already-escaped HTML) under the brand mark, with a small footer
    line (plain text) after the site link."""
    return (
        '<div style="font-family:-apple-system,Segoe UI,Helvetica,Arial,sans-serif;font-size:15px;'
        f'color:#292524;max-width:520px;margin:0 auto;padding:24px">{_MARK}{body}'
        f'<p style="margin:24px 0 0;font-size:12px;color:#78716c">Thalace · <a href="{_SITE}" style="color:#b45309">thalace.com</a>'
        f" · {escape(footer)}</p></div>"
    )


def configured() -> bool:
    return bool(settings.resend_api_key and settings.waitlist_from_email)


async def send(to: str, subject: str, text: str, html: str) -> bool:
    """Send one email. False when email isn't configured or Resend refuses;
    the cause is logged. Callers treat email as a courtesy, not a step that
    can fail the request."""
    if not configured():
        logger.info("Email not sent to %s: Resend key or sender address not configured", to)
        return False
    try:
        async with httpx.AsyncClient(timeout=settings.resend_timeout_s) as client:
            response = await client.post(
                _RESEND_URL,
                headers={"Authorization": f"Bearer {settings.resend_api_key}"},
                json={"from": settings.waitlist_from_email, "to": [to], "subject": subject, "text": text, "html": html},
            )
    except httpx.HTTPError:
        logger.exception("Resend request failed for %s", to)
        return False
    if response.status_code >= 400:
        logger.warning("Resend refused the email to %s: %s %s", to, response.status_code, response.text[:300])
        return False
    return True
