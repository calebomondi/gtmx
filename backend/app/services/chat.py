"""Workspace chat: the conversation, and the workspace context the agent is
grounded in (assembled here because it needs the database)."""

import json
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.database import models
from backend.app.services.errors import ConflictError, InvalidInputError
from backend.app.services.runs import TERMINAL_STATUSES

HISTORY_TURNS = 12  # prior messages the agent sees
MAX_MESSAGE_CHARS = 4000
_LIST_LIMIT = 200
_CONTEXT_CHARS = 14_000  # a budget, not a hope: each block is clipped to it


async def list_messages(db: AsyncSession, workspace_id: uuid.UUID) -> list[models.ChatMessage]:
    rows = (await db.execute(
        select(models.ChatMessage)
        .where(models.ChatMessage.workspace_id == workspace_id)
        .order_by(models.ChatMessage.created_at.desc())
        .limit(_LIST_LIMIT)
    )).scalars().all()
    return list(reversed(rows))


async def pending_run(db: AsyncSession, workspace_id: uuid.UUID) -> models.Run | None:
    return await db.scalar(
        select(models.Run).where(
            models.Run.workspace_id == workspace_id,
            models.Run.kind == "chat",
            models.Run.status.not_in(TERMINAL_STATUSES),
        )
    )


async def add_user_message(db: AsyncSession, workspace: models.Workspace, content: str) -> models.ChatMessage:
    content = (content or "").strip()
    if not content:
        raise InvalidInputError("Message cannot be empty.")
    if len(content) > MAX_MESSAGE_CHARS:
        raise InvalidInputError(f"Message is too long (max {MAX_MESSAGE_CHARS} characters).")
    if await pending_run(db, workspace.id) is not None:
        raise ConflictError("The agent is still answering your last message.")
    message = models.ChatMessage(workspace_id=workspace.id, user_id=workspace.user_id, role="user", content=content)
    db.add(message)
    await db.commit()
    return message


async def add_assistant_message(db: AsyncSession, workspace_id: uuid.UUID, user_id: uuid.UUID,
                                run_id: uuid.UUID, content: str) -> models.ChatMessage:
    message = models.ChatMessage(
        workspace_id=workspace_id, user_id=user_id, role="assistant", content=content, run_id=run_id,
    )
    db.add(message)
    await db.commit()
    return message


def _block(title: str, value) -> str:
    if not value:
        return ""
    text = value if isinstance(value, str) else json.dumps(value, ensure_ascii=False)
    return f"### {title}\n{text[:_CONTEXT_CHARS // 6]}\n"


async def workspace_context(db: AsyncSession, workspace_id: uuid.UUID) -> tuple[str, str]:
    """(context text, offer name): the research the agent answers from."""
    insights = await db.scalar(
        select(models.ProductProfile.insights).where(models.ProductProfile.workspace_id == workspace_id)
    ) or {}
    offer = insights.get("offer_snapshot") or {}
    competitors = (await db.execute(
        select(models.Competitor).where(models.Competitor.workspace_id == workspace_id)
        .order_by(models.Competitor.first_seen_at.desc()).limit(15)
    )).scalars().all()
    accounts = (await db.execute(
        select(models.Account).where(models.Account.workspace_id == workspace_id)
        .order_by(models.Account.selected.desc(), models.Account.score.desc().nulls_last()).limit(10)
    )).scalars().all()
    parts = [
        _block("OFFER", {k: offer.get(k) for k in ("offer_name", "offer_description", "problem_solved", "how_it_works", "target_geo")}),
        _block("DOMAIN UNDERSTANDING", insights.get("domain_understanding")),
        _block("MARKET", {"fit": insights.get("market_fit_understanding"), "data": insights.get("market_data")}),
        _block("COMPETITION (offer vs standard)", insights.get("competition_data")),
        _block("IDEAL COMPETITOR PROFILE (archetypes, names no companies)", insights.get("ideal_competitor_profile")),
        _block("ICP", insights.get("icp")),
        _block("TRACKED COMPETITORS", [
            {"name": c.name, "website": c.website, "positioning": c.positioning, "weaknesses": (c.weaknesses or [])[:3]}
            for c in competitors
        ]),
        _block("TARGET ACCOUNTS", [
            {"name": a.name, "industry": a.industry, "selected": a.selected, "why_reach_out": (a.why_reach_out or [])[:2]}
            for a in accounts
        ]),
    ]
    context = "\n".join(p for p in parts if p) or "(This workspace has no research yet.)"
    return context[:_CONTEXT_CHARS], offer.get("offer_name") or ""
