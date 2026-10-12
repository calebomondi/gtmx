"""Live intake paths other than "a website that reads fine": an offer described
only in words, and a website that can't be read. Each runs discovery until the
description is settled: up for confirmation (then it stops), or taken from
the user's own words.

    uv run pytest -m live backend/tests/live/test_intake_paths.py
"""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy import select

from backend.app import agents_runtime
from backend.app.database import models
from backend.app.database.connect import AsyncSessionLocal
from backend.app.runs import manager
from backend.app.schemas.agents import DiscoveryRequest
from backend.app.services.runs import TERMINAL_STATUSES
from backend.tests.live import checks
from backend.tests.live.offers import ENGINEERING_CONSULTANCY, GEO
from backend.tests.live.test_gtm_chain import _answer, _wait
from config import settings

pytestmark = pytest.mark.live

OFFER = ENGINEERING_CONSULTANCY
DESCRIPTION = (
    "Shanga Labs' Engineering and Innovation Consultancy takes hardware and software products from "
    "concept to mass manufacturing: R&D, electronics and firmware design, prototyping, and "
    "manufacturing support for companies in East Africa."
)
DEAD_URL = "https://shangalabs-unreachable.example/"
INTAKE_TIMEOUT_S = 600


async def _intake(request: DiscoveryRequest, replies: dict[str, list[str]]) -> tuple[list[dict], str, str]:
    """Run discovery until the description is up for confirmation, or to the
    end when nothing needs confirming. `replies` are scripted answers per
    interrupt type, used in order. Returns the interrupts seen, the
    description, and how the run ended ("confirming" or its final status)."""
    await agents_runtime.start_agent_runtime(settings.database_url)
    seen: list[dict] = []
    try:
        user_id = uuid.uuid4()
        run = await manager.start_discovery(user_id, request)
        while True:
            run = await _wait(run.id, {"awaiting_input", *TERMINAL_STATUSES}, INTAKE_TIMEOUT_S)
            if run.status != "awaiting_input":
                return seen, await _saved_description(run.workspace_id), run.status
            question = (run.progress or {}).get("interrupt") or {}
            kind = question.get("interrupt_type") or ""
            seen.append(question)
            if kind == "product_service_description_confirmation":
                await manager.cancel(user_id, run.id)
                return seen, question.get("draft") or "", "confirming"
            # Anything not scripted is answered as a user who knows the offer would.
            scripted = replies.get(kind) or []
            reply = scripted.pop(0) if scripted else _answer(checks.Scorecard(OFFER.key), OFFER, question)
            await manager.answer(user_id, run.id, reply)
    finally:
        await manager.shutdown()
        await agents_runtime.stop_agent_runtime()


async def _saved_description(workspace_id: uuid.UUID | None) -> str:
    if workspace_id is None:
        return ""
    async with AsyncSessionLocal() as db:
        profile = (await db.execute(select(models.ProductProfile).where(
            models.ProductProfile.workspace_id == workspace_id))).scalars().first()
    return (profile.product_description or "") if profile else ""


def _kinds(seen: list[dict]) -> list[str]:
    return [q.get("interrupt_type") or "" for q in seen]


def _describes_the_offer(draft: str) -> None:
    card = checks.Scorecard(OFFER.key)
    checks.check_description(card, OFFER, draft, "intake")
    failed = card.failures("critical") + card.failures("major")
    assert not failed, [f"{c['check']}: {c['detail']}" for c in failed]


def test_an_offer_described_in_words_is_used_as_written(client):
    request = DiscoveryRequest(product_name=OFFER.name, product_url="", offer_description=DESCRIPTION,
                               source="manual", offer_type=OFFER.offer_type, target_geo=GEO)
    seen, draft, status = client.portal.call(_intake, request, {})
    # The user's words need no confirming; a follow-up for missing details is fine.
    assert status == "completed", (status, _kinds(seen))
    assert not {"url_unscrappable", "product_service_description_confirmation"} & set(_kinds(seen)), _kinds(seen)
    _describes_the_offer(draft)


def test_an_unreadable_website_asks_for_a_description_and_uses_it(client):
    request = DiscoveryRequest(product_name=OFFER.name, product_url=DEAD_URL, offer_type=OFFER.offer_type,
                               target_geo=GEO)
    seen, draft, status = client.portal.call(_intake, request, {"url_unscrappable": ["continue", DESCRIPTION]})
    assert _kinds(seen) == ["url_unscrappable", "url_unscrappable"], _kinds(seen)
    assert "won't guess" in (seen[1].get("question") or "")
    assert status == "completed", (status, _kinds(seen))
    _describes_the_offer(draft)


def test_an_unreadable_website_can_be_corrected_in_place(client):
    request = DiscoveryRequest(product_name=OFFER.name, product_url=DEAD_URL, offer_type=OFFER.offer_type,
                               target_geo=GEO)
    replies = {"url_unscrappable": [OFFER.url]}
    seen, draft, status = client.portal.call(_intake, request, replies)
    assert _kinds(seen)[:1] == ["url_unscrappable"], _kinds(seen)
    assert status == "confirming", (status, _kinds(seen))
    _describes_the_offer(draft)
