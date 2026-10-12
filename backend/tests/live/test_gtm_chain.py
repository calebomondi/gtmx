"""The whole GTM chain, live: real LLM, Exa, Bright Data and site scrapes.

Each offer goes through the app's own path -- the run manager, the runners,
persistence and mappers, on the test database -- exactly as a user's
workspace would: discovery (answering the intake questions like a user),
competitors, monitoring, accounts, outreach drafts, replies and chat. Every
stage's output is written to `_out/<offer>/` and scored against the offer's
ground truth (offers.py); the test fails on any critical finding.

Opt-in and paid: `uv run pytest -m live backend/tests/live -s`. A full offer
takes 30-40 minutes; intake-only offers about two.
"""

import asyncio
import json
import time
import uuid
from datetime import UTC, datetime
from pathlib import Path

import pytest
from sqlalchemy import select

from agents.pipelines.outreach import gtm_specialist
from backend.app import agents_runtime
from backend.app.database import models
from backend.app.database.connect import AsyncSessionLocal
from backend.app.runs import background, manager
from backend.app.schemas.agents import DiscoveryRequest
from backend.app.services import chat as chat_service
from backend.app.services.runs import TERMINAL_STATUSES
from backend.tests.live import checks
from backend.tests.live.offers import GEO, OFFERS, Offer
from config import settings

pytestmark = pytest.mark.live

OUT = Path(__file__).resolve().parent / "_out"
SENDER = "Wanjiku"
STAGE_TIMEOUT_S = 2400
SLOTS = ["Tue 14 Oct, 10:00-10:30 (Africa/Nairobi)", "Wed 15 Oct, 14:00-14:30 (Africa/Nairobi)",
         "Thu 16 Oct, 11:00-11:30 (Africa/Nairobi)"]
REPLIES = {
    "question": "Thanks for this. How does it compare on cost with what we run today, and what would a pilot need from our side?",
    "meeting": "Interesting timing. Can we find 30 minutes next week to talk it through?",
    "unsubscribe": "Please take me off your list, we're not interested.",
    "ooo": "I'm out of the office until 20 October with limited access to email. For urgent matters contact my assistant.",
}


def _chat_questions(offer: Offer) -> list[tuple[str, set[str]]]:
    own = {"product", "service"}
    return [
        (f"What exactly does {offer.name} do, and what makes it different from the alternatives?", own),
        (f"How big is the opportunity for {offer.name} in Nigeria and South Africa, and what will buyers pay?", {"market"}),
        ("Which competitor is the biggest threat to us in Kenya, and where are they weakest?", {"competition"}),
        ("Which target accounts should we contact first, and through which channel?", {"gtm"}),
        ("Write our positioning against the strongest competitor for South African buyers, including a launch price.",
         {"competition", "gtm", "market"}),
    ]


async def _wait(run_id: uuid.UUID, statuses: set[str], timeout: float = STAGE_TIMEOUT_S) -> models.Run:
    async with asyncio.timeout(timeout):
        while True:
            async with AsyncSessionLocal() as db:
                run = await db.get(models.Run, run_id)
            if run.status in statuses:
                return run
            await asyncio.sleep(2)


async def _run(kind: str, user_id: uuid.UUID, workspace_id: uuid.UUID, params: dict | None = None) -> models.Run:
    run = await manager.start_background(kind, user_id, workspace_id, params=params)
    done = await _wait(run.id, set(TERMINAL_STATUSES))
    if done.status != "completed":
        raise AssertionError(f"{kind} run {done.status}: {done.error}")
    return done


def _answer(card: checks.Scorecard, offer: Offer, question: dict) -> str:
    """Answer an intake question the way a user who knows their offer would."""
    kind = question.get("interrupt_type")
    if kind == "offer_name_mismatch":
        candidates = question.get("product_candidates") or []
        key = offer.name.lower().split()[0]
        pick = next((i for i, c in enumerate(candidates, 1) if key in c.lower()), None)
        card.check("intake", pick is not None, "the named offer is among the offers found on the site", "critical",
                   f"candidates={candidates}")
        return str(pick) if pick else offer.name
    if kind == "product_service_description_confirmation":
        before = len(card.failures("critical"))
        checks.check_description(card, offer, question.get("draft") or "", "intake")
        if len(card.failures("critical")) > before:
            return f"Not quite. {offer.truth}"
        return "yes"
    if kind == "url_unscrappable":
        card.check("intake", False, "the website could be read", "critical", question.get("url") or "")
        return "continue"
    return "yes"


async def _discover(card: checks.Scorecard, offer: Offer, user_id: uuid.UUID) -> models.Run:
    run = await manager.start_discovery(user_id, DiscoveryRequest(
        product_name=offer.name, product_url=offer.url, offer_type=offer.offer_type, target_geo=GEO,
    ))
    while True:
        run = await _wait(run.id, {"awaiting_input", *TERMINAL_STATUSES})
        if run.status != "awaiting_input":
            break
        question = (run.progress or {}).get("interrupt") or {}
        answer = _answer(card, offer, question)
        card.intake.append({"question": question, "answer": answer})
        print(f"  [{offer.key}] {question.get('interrupt_type')} -> {answer[:60]!r}")
        intake_done = question.get("interrupt_type") == "product_service_description_confirmation" and answer == "yes"
        await manager.answer(user_id, run.id, answer)
        if offer.depth == "intake" and intake_done:
            await _wait(run.id, {"running", *TERMINAL_STATUSES}, 60)
            return await manager.cancel(user_id, run.id)
    if run.status != "completed":
        raise AssertionError(f"discovery {run.status}: {run.error}")
    return run


def _row(obj, *fields: str) -> dict:
    return {f: getattr(obj, f) for f in fields}


async def _chain(offer: Offer) -> dict:
    """Run every stage; an error ends the chain as a critical finding, keeping
    whatever the earlier stages produced for the report."""
    card = checks.Scorecard(offer.key)
    artifacts: dict = {"offer": offer.name, "geo": GEO, "timings_s": {}}
    try:
        await _stages(offer, card, artifacts)
    except Exception as exc:  # noqa: BLE001 -- reported, not swallowed: it fails the test
        card.check("chain", False, "every stage ran", "critical", f"{type(exc).__name__}: {exc}")
    return {"card": card, "artifacts": artifacts}


async def _stages(offer: Offer, card: checks.Scorecard, artifacts: dict) -> None:
    user_id = uuid.uuid4()
    clock = time.perf_counter()

    def lap(stage: str) -> None:
        nonlocal clock
        now = time.perf_counter()
        artifacts["timings_s"][stage] = round(now - clock, 1)
        clock = now

    run = await _discover(card, offer, user_id)
    lap("discovery")
    if offer.depth == "intake":
        return

    async with AsyncSessionLocal() as db:
        workspace = await db.get(models.Workspace, run.workspace_id)
        profile = (await db.execute(select(models.ProductProfile).where(
            models.ProductProfile.workspace_id == workspace.id))).scalar_one()
    insights = profile.insights or {}
    artifacts["insights"] = insights
    checks.check_discovery(card, offer, insights, workspace)

    await _run("competitors", user_id, workspace.id)
    lap("competitors")
    await _run("monitor", user_id, workspace.id)
    lap("monitor")
    async with AsyncSessionLocal() as db:
        competitors = (await db.execute(select(models.Competitor).where(
            models.Competitor.workspace_id == workspace.id))).scalars().all()
        signals = (await db.execute(select(models.Signal).where(
            models.Signal.workspace_id == workspace.id))).scalars().all()
    artifacts["competitors"] = [_row(c, "name", "website", "description", "offering", "positioning", "pricing",
                                     "target_customers", "headquarters", "strengths", "weaknesses",
                                     "tracking_sources", "unsourced_fields") for c in competitors]
    artifacts["signals"] = [_row(s, "category", "title", "summary", "source_url") for s in signals]
    checks.check_competitors(card, offer, competitors)
    checks.check_monitor(card, competitors, signals)

    await _run("accounts", user_id, workspace.id)
    lap("accounts")
    async with AsyncSessionLocal() as db:
        accounts = (await db.execute(select(models.Account).where(models.Account.workspace_id == workspace.id)
                                     .order_by(models.Account.score.desc().nulls_last()))).scalars().all()
    artifacts["accounts"] = [_row(a, "name", "account_type", "website", "geo", "summary", "industry", "size",
                                  "key_contacts", "socials", "trigger_event", "score") for a in accounts]
    checks.check_accounts(card, offer, accounts, competitors)

    drafts = await _outreach(card, offer, user_id, workspace.id, accounts, json.dumps(artifacts, default=str))
    artifacts["outreach"] = [_row(d, "channel", "recipient_name", "recipient_company", "recipient_address",
                                  "subject", "body") for d in drafts]
    lap("outreach")

    artifacts["replies"] = await _replies(card, user_id, workspace.id, drafts)
    lap("replies")

    artifacts["chat"] = await _chat(card, offer, user_id, workspace)
    lap("chat")


async def _outreach(card, offer, user_id, workspace_id, accounts, sources: str) -> list[models.OutreachMessage]:
    reachable = [a for a in accounts if any(c.get("email") or c.get("linkedin") for c in a.key_contacts or [])][:2]
    card.check("outreach", len(reachable) == 2, "two reachable accounts to write to", "major", f"{len(reachable)}")
    for account in reachable:
        channel = "email" if any(c.get("email") for c in account.key_contacts) else "linkedin"
        await _run("outreach_drafts", user_id, workspace_id,
                   {"account_ids": [str(account.id)], "channel": channel, "sender": SENDER})
    async with AsyncSessionLocal() as db:
        drafts = (await db.execute(select(models.OutreachMessage).where(
            models.OutreachMessage.workspace_id == workspace_id))).scalars().all()
    for draft in drafts:
        account = next(a for a in reachable if a.id == draft.account_id)
        brief = gtm_specialist.OutreachBrief(channel=draft.channel, sender_name=SENDER, offer="", account="")
        problems = [p for p in gtm_specialist.lint(brief, gtm_specialist.OutreachDraft(
            subject=draft.subject or "", body=draft.body), sources) if "appears in none of your sources" not in p]
        checks.check_outreach(card, offer, draft, account, problems, sources)
    return drafts


async def _replies(card, user_id, workspace_id, drafts) -> list[dict]:
    """Pretend the first draft was sent, then answer four kinds of reply to it."""
    sent = next((d for d in drafts if d.channel == "email"), drafts[0] if drafts else None)
    if sent is None:
        card.check("replies", False, "a sent email to reply to", "critical")
        return []
    results = []
    for kind, text in REPLIES.items():
        thread = f"live-{kind}-{uuid.uuid4().hex[:6]}"
        async with AsyncSessionLocal() as db:
            db.add(models.OutreachMessage(
                workspace_id=workspace_id, user_id=user_id, account_id=sent.account_id, channel="email",
                recipient_name=sent.recipient_name, recipient_company=sent.recipient_company,
                recipient_address=sent.recipient_address or "contact@example.com", subject=sent.subject,
                body=sent.body, status="sent", thread_id=thread, sent_at=datetime.now(UTC),
            ))
            reply = models.OutreachMessage(
                workspace_id=workspace_id, user_id=user_id, account_id=sent.account_id, channel="email",
                direction="inbound", status="received", thread_id=thread, recipient_name=sent.recipient_name,
                recipient_company=sent.recipient_company, recipient_address=sent.recipient_address, body=text,
                sent_at=datetime.now(UTC),
            )
            db.add(reply)
            await db.commit()
            reply_id = reply.id
        await _run("outreach_reply", user_id, workspace_id, {"message_id": str(reply_id), "sender": SENDER})
        async with AsyncSessionLocal() as db:
            reply = await db.get(models.OutreachMessage, reply_id)
            answer = (await db.execute(select(models.OutreachMessage).where(
                models.OutreachMessage.thread_id == thread, models.OutreachMessage.status == "draft"))).scalar_one_or_none()
            account = await db.get(models.Account, reply.account_id) if reply.account_id else None
        checks.check_reply(card, kind, reply, answer, SLOTS, SENDER, account)
        results.append({"kind": kind, "reply": text, "intent": reply.intent,
                        "answer": answer.body if answer else None, "meeting": answer.meeting if answer else None})
    return results


async def _chat(card, offer, user_id, workspace) -> list[dict]:
    results = []
    for question, expected in _chat_questions(offer):
        async with AsyncSessionLocal() as db:
            await chat_service.add_user_message(db, workspace, question)
        await _run("chat", user_id, workspace.id)
        async with AsyncSessionLocal() as db:
            message = (await chat_service.list_messages(db, workspace.id))[-1]
        checks.check_chat(card, question, expected, message)
        results.append({"question": question, "specialist": message.specialist_domain, "answer": message.content})
    return results


def _report(offer: Offer, card: checks.Scorecard, artifacts: dict) -> Path:
    folder = OUT / offer.key
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "artifacts.json").write_text(json.dumps(artifacts, indent=2, default=str))
    (folder / "checks.json").write_text(json.dumps(card.checks, indent=2))
    artifacts["intake"] = card.intake
    (folder / "artifacts.json").write_text(json.dumps(artifacts, indent=2, default=str))
    lines = [f"# {offer.name} — live chain ({datetime.now(UTC):%Y-%m-%d %H:%M} UTC)", "",
             f"Timings (s): {artifacts['timings_s']}", "",
             f"Checks: {sum(c['ok'] for c in card.checks)}/{len(card.checks)} passed; "
             f"critical failures: {len(card.failures('critical'))}, major: {len(card.failures('major'))}, "
             f"minor: {len(card.failures('minor'))}", "", "## Failures", ""]
    lines += [f"- **{c['severity']}** [{c['stage']}] {c['check']} — {c['detail']}" for c in card.failures()] or ["- none"]
    (folder / "report.md").write_text("\n".join(lines) + "\n")
    return folder


@pytest.fixture(autouse=True)
def live_doubles(monkeypatch):
    """The only stand-ins: a calendar (no Google account in tests) and the
    sender's name (no Supabase user)."""
    async def slots(db, user_id):
        return SLOTS, "Africa/Nairobi"

    async def sender(user_id):
        return SENDER
    monkeypatch.setattr(background.calendar_service, "free_slots", slots)
    monkeypatch.setattr(background.outreach_service, "sender_for_user", sender)


async def _with_runtime(offer: Offer) -> dict:
    """The discovery agent's checkpointer runtime, which app startup opens."""
    await agents_runtime.start_agent_runtime(settings.database_url)
    try:
        return await _chain(offer)
    finally:
        await manager.shutdown()
        await agents_runtime.stop_agent_runtime()


@pytest.mark.parametrize("offer", OFFERS, ids=[o.key for o in OFFERS])
def test_gtm_chain(client, offer: Offer):
    result = client.portal.call(_with_runtime, offer)
    folder = _report(offer, result["card"], result["artifacts"])
    critical = result["card"].failures("critical")
    print(f"\n{offer.name}: report in {folder}/report.md")
    assert not critical, "\n".join(f"[{c['stage']}] {c['check']}: {c['detail']}" for c in critical)
