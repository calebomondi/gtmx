"""Per-user usage limits: what one account may run, and how often it may call
the API. Agent runs cost real LLM and search money, and at launch every user
shares one provider quota, so one account must not be able to drain it.

The request limiter is in-memory, which is correct for the single-instance
launch; a multi-instance deployment needs a shared store (Redis) instead.
"""

import time
import uuid
from collections import defaultdict, deque
from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.database import models
from backend.app.services.errors import RateLimitedError
from backend.app.services.runs import TERMINAL_STATUSES
from config import settings

_DAY = timedelta(days=1)


async def _runs_today(db: AsyncSession, user_id: uuid.UUID, kind: str) -> int:
    since = datetime.now(UTC) - _DAY
    return int(await db.scalar(
        select(func.count()).select_from(models.Run).where(
            models.Run.user_id == user_id, models.Run.kind == kind, models.Run.created_at >= since,
        )
    ) or 0)


def default_daily_cap(kind: str) -> int:
    return {
        "discovery": settings.max_discovery_runs_per_day,
        "competitors": settings.max_competitor_runs_per_day,
        "accounts": settings.max_account_runs_per_day,
        # Manual-competitor research is bounded by how many rivals a user adds.
        "competitor_research": settings.max_competitor_runs_per_day * 5,
        "chat": settings.max_chat_messages_per_day,
        "outreach_drafts": settings.max_account_runs_per_day,
        # One per reply received: bounded by what the user sends.
        "outreach_reply": settings.max_outreach_sends_per_day,
        "monitor": settings.max_monitor_runs_per_day,
        # Fit is assessed for accounts discovery found: bounded by those runs.
        "account_fit": settings.max_account_runs_per_day * 5,
        "lace_onboarding": settings.max_lace_onboardings_per_day,
        "lace_turn": settings.max_lace_turns_per_day,
        "lace_competitors": settings.max_competitor_runs_per_day,
        "lace_monitor": settings.max_monitor_runs_per_day,
        "lace_accounts": settings.max_account_runs_per_day,
        "lace_contacts": settings.max_account_runs_per_day,
        "lace_drafts": settings.max_account_runs_per_day,
        # One per sync that brought replies: bounded by what the user sends.
        "lace_reply": settings.max_outreach_sends_per_day,
        "lace_opportunities": settings.max_account_runs_per_day,
    }[kind]


async def daily_cap(db: AsyncSession, user_id: uuid.UUID, kind: str) -> int:
    """The admin's override for this user, else the default."""
    override = await db.scalar(select(models.UserQuota.daily_cap).where(
        models.UserQuota.user_id == user_id, models.UserQuota.kind == kind,
    ))
    return default_daily_cap(kind) if override is None else override


async def ensure_can_start(db: AsyncSession, user_id: uuid.UUID, kind: str) -> None:
    """Raise RateLimitedError if this user may not start another `kind` run."""
    if kind == "discovery":
        active = await db.scalar(
            select(func.count()).select_from(models.Run).where(
                models.Run.user_id == user_id,
                models.Run.kind == "discovery",
                models.Run.status.not_in(TERMINAL_STATUSES),
            )
        )
        if active and active >= settings.max_active_discovery_runs:
            raise RateLimitedError(
                "You already have a discovery run in progress. Let it finish (or cancel it) before starting another."
            )
    cap = await daily_cap(db, user_id, kind)
    if await _runs_today(db, user_id, kind) >= cap:
        raise RateLimitedError(
            f"You've reached today's limit of {cap} {kind} runs. It resets on a rolling 24-hour window.",
            retry_after_s=3600,
        )


_requests: dict[uuid.UUID, deque[float]] = defaultdict(deque)


def check_request_rate(user_id: uuid.UUID) -> None:
    """Sliding one-minute window of API requests per user."""
    now = time.monotonic()
    window = _requests[user_id]
    while window and now - window[0] > 60:
        window.popleft()
    if len(window) >= settings.max_requests_per_minute:
        retry = int(60 - (now - window[0])) + 1
        raise RateLimitedError("Too many requests. Please slow down for a moment.", retry_after_s=retry)
    window.append(now)
