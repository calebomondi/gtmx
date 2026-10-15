"""Transactional email (Thalace's own messages, never a user's outreach) via
Resend's HTTP API. Users' outreach goes through their own Gmail instead."""

import httpx

from config import settings
from utils.log import logger

_RESEND_URL = "https://api.resend.com/emails"


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
