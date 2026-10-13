"""The public waitlist: join with an email, then optionally add details and
ask for a pilot spot. No account is involved; a private token returned at
signup lets the same browser add the details."""

import hashlib
import secrets
import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.database import models
from backend.app.database.connect import AsyncSessionLocal
from backend.app.schemas.waitlist import PilotSpots, WaitlistDetails, WaitlistSource
from backend.app.services import email, waitlist_emails
from backend.app.services.errors import NotFoundError, RateLimitedError
from config import settings
from utils.log import logger

_RATE_WINDOW = timedelta(hours=1)


def _sha256(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def _ip_hash(ip: str | None) -> str | None:
    return _sha256(f"{settings.waitlist_ip_salt}:{ip}") if ip else None


async def _check_rate(db: AsyncSession, ip_hash: str | None) -> None:
    if ip_hash is None:
        return
    since = datetime.now(UTC) - _RATE_WINDOW
    recent = await db.scalar(
        select(func.count()).select_from(models.WaitlistSignup)
        .where(models.WaitlistSignup.ip_hash == ip_hash, models.WaitlistSignup.updated_at >= since)
    )
    if (recent or 0) >= settings.waitlist_signups_per_ip_per_hour:
        raise RateLimitedError("Too many signups from this network. Try again in an hour.",
                               retry_after_s=int(_RATE_WINDOW.total_seconds()))


async def join(db: AsyncSession, address: str, source: WaitlistSource,
               ip: str | None) -> tuple[models.WaitlistSignup, str, bool]:
    """Add the email to the waitlist, or refresh it if it's already there.
    Returns (signup, token for the details step, whether it is new)."""
    ip_hash = _ip_hash(ip)
    await _check_rate(db, ip_hash)
    token = secrets.token_urlsafe(32)
    now = datetime.now(UTC)
    address = address.strip().lower()
    signup = await db.scalar(select(models.WaitlistSignup).where(models.WaitlistSignup.email == address))
    created = signup is None
    if created:
        signup = models.WaitlistSignup(
            email=address, source=source.model_dump(exclude_none=True), consent_at=now,
            update_token_hash=_sha256(token), ip_hash=ip_hash,
        )
        db.add(signup)
    else:
        # Signing up again is fine: a fresh token for this browser, the first
        # source kept (it is what brought them).
        signup.update_token_hash = _sha256(token)
        signup.consent_at = now
        signup.ip_hash = ip_hash
        signup.updated_at = now
    await db.commit()
    await db.refresh(signup)
    return signup, token, created


async def save_details(db: AsyncSession, token: str, details: WaitlistDetails) -> tuple[models.WaitlistSignup, bool]:
    """Apply the optional details. Returns (signup, whether this just turned
    the pilot on). Unknown token: 404."""
    signup = await db.scalar(
        select(models.WaitlistSignup).where(models.WaitlistSignup.update_token_hash == _sha256(token))
    )
    if signup is None:
        raise NotFoundError("Signup not found")
    was_pilot = signup.wants_pilot
    changes = details.model_dump(exclude_unset=True)
    for field in ("name", "company", "role", "expectations"):
        if field in changes:
            changes[field] = (changes[field] or "").strip() or None
    if "countries" in changes:
        changes["countries"] = [c.strip() for c in changes["countries"] or [] if c and c.strip()]
    for field, value in changes.items():
        setattr(signup, field, value)
    await db.commit()
    await db.refresh(signup)
    return signup, signup.wants_pilot and not was_pilot


async def pilot_spots(db: AsyncSession) -> PilotSpots:
    taken = await db.scalar(
        select(func.count()).select_from(models.WaitlistSignup).where(models.WaitlistSignup.wants_pilot.is_(True))
    ) or 0
    total = settings.waitlist_pilot_spots
    return PilotSpots(total=total, taken=taken, left=max(total - taken, 0))


async def send_joined_email(signup_id: uuid.UUID) -> None:
    """Send "you're on the list" once, after the response has gone out."""
    async with AsyncSessionLocal() as db:
        signup = await db.get(models.WaitlistSignup, signup_id)
        if signup is None or signup.confirmation_sent_at is not None:
            return
        if await _deliver(signup, waitlist_emails.joined()):
            signup.confirmation_sent_at = datetime.now(UTC)
            await db.commit()


async def send_pilot_email(signup_id: uuid.UUID) -> None:
    """Send "you're in line for the pilot" when someone opts in."""
    async with AsyncSessionLocal() as db:
        signup = await db.get(models.WaitlistSignup, signup_id)
        if signup is not None:
            await _deliver(signup, waitlist_emails.pilot())


async def _deliver(signup: models.WaitlistSignup, message: tuple[str, str, str]) -> bool:
    subject, text, html = message
    sent = await email.send(signup.email, subject, text, html)
    if not sent:
        logger.info("Waitlist email %r not delivered to signup %s", subject, signup.id)
    return sent
