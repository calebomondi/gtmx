"""Moving v1 pilot workspaces into Laces (docs/lace-ui-plan.md, PR I).

One Lace per founder per startup website: workspaces of the same user with
the same product site become one Lace. What carries over: the offer profile
and its features as facts, competitors (saved, with their monitoring
baseline), accounts (as they were reviewed) with their people as contacts
(unapproved: outreach waits for the founder's approval), and outreach that
went out or came in, threads kept. Drafts, v1 chat and signals stay behind,
and so do accounts without a trigger (v2 keeps none; their messages move,
unlinked).

Idempotent: a Lace, competitor, account or contact already there is kept as
it is, and a fact or message already copied is not copied again. `plan`
only reads; `apply` writes, one workspace per transaction.
"""

import uuid
from dataclasses import dataclass, field

from sqlalchemy import exists, null, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from agents.schemas.accounts import AccountRecord
from backend.app.database import models
from backend.app.database.lace_models import Lace, LaceAccount, LaceCompetitor, LaceFact, LaceOutreach
from backend.app.services import lace_contacts
from backend.app.services.competitors import domain_key, normalize_website
from backend.app.services.lace_accounts import account_key

# A v1 workspace's name becomes its Lace's, cut to fit.
LACE_NAME_CHARS = 60
# Outreach that happened; drafts stay behind so they get the founder's approval again.
_CARRIED_STATUSES = ("sending", "sent", "failed", "bounced", "received")
_RECORD_FIELDS = tuple(AccountRecord.model_fields)


@dataclass
class WorkspacePlan:
    workspace_id: uuid.UUID
    user_id: uuid.UUID
    name: str
    website: str | None
    competitors: int
    accounts: int
    # v2 keeps an account only with a current trigger; these stay behind.
    accounts_without_trigger: int
    contacts: int
    messages: int
    facts: int
    lace_exists: bool

    @property
    def movable(self) -> bool:
        return self.website is not None


@dataclass
class MigrationPlan:
    workspaces: list[WorkspacePlan] = field(default_factory=list)

    @property
    def laces(self) -> int:
        """Laces that would be created: one per founder per website."""
        return len({(w.user_id, domain_key(w.website)) for w in self.workspaces if w.movable and not w.lace_exists})

    @property
    def skipped(self) -> list[WorkspacePlan]:
        return [w for w in self.workspaces if not w.movable]


def _website(workspace: models.Workspace) -> str | None:
    """The startup's site, if the workspace has one that looks like a site."""
    url = (workspace.product_profile.product_url if workspace.product_profile else None) or ""
    if not url.strip():
        return None
    website = normalize_website(url)
    return website if "." in domain_key(website) else None


def _facts(profile: models.ProductProfile | None) -> list[tuple[str, str]]:
    """(topic, claim) from the offer profile the founder confirmed in v1."""
    if profile is None:
        return []
    facts = [("offer", text.strip()) for text in (profile.product_description, profile.how_it_works) if text and text.strip()]
    if profile.problem_solved and profile.problem_solved.strip():
        facts.append(("positioning", f"It solves: {profile.problem_solved.strip()}"))
    for feature in profile.features:
        line = f"Feature: {feature.name}" + (f": {feature.description.strip()}" if feature.description else "")
        facts.append(("offer", line))
    if profile.target_geo:
        facts.append(("market", "It sells in " + ", ".join(profile.target_geo) + "."))
    return facts


async def _workspaces(db: AsyncSession, user_id: uuid.UUID | None) -> list[models.Workspace]:
    query = (select(models.Workspace).where(models.Workspace.archived.is_(False))
             .options(selectinload(models.Workspace.product_profile).selectinload(models.ProductProfile.features))
             .order_by(models.Workspace.user_id, models.Workspace.date_created))
    if user_id:
        query = query.where(models.Workspace.user_id == user_id)
    return list((await db.scalars(query)).all())


async def _existing_lace(db: AsyncSession, user_id: uuid.UUID, website: str) -> Lace | None:
    """The founder's Lace for this site, however its address is written
    (www or not, a trailing slash)."""
    site = domain_key(website)
    return next((lace for lace in (await db.scalars(select(Lace).where(Lace.user_id == user_id))).all()
                 if domain_key(lace.website) == site), None)


async def plan(db: AsyncSession, user_id: uuid.UUID | None = None) -> MigrationPlan:
    """What a migration would move, per workspace. Reads only."""
    out = MigrationPlan()
    for ws in await _workspaces(db, user_id):
        website = _website(ws)
        accounts = list((await db.scalars(select(models.Account).where(models.Account.workspace_id == ws.id))).all())
        out.workspaces.append(WorkspacePlan(
            workspace_id=ws.id, user_id=ws.user_id, name=ws.name or (ws.product_name or "Untitled"), website=website,
            competitors=len((await db.scalars(select(models.Competitor.id).where(models.Competitor.workspace_id == ws.id))).all()),
            accounts=sum(a.trigger_event is not None for a in accounts),
            accounts_without_trigger=sum(a.trigger_event is None for a in accounts),
            contacts=sum(len(a.key_contacts or []) for a in accounts if a.trigger_event is not None),
            messages=len((await db.scalars(select(models.OutreachMessage.id).where(
                models.OutreachMessage.workspace_id == ws.id,
                models.OutreachMessage.status.in_(_CARRIED_STATUSES)))).all()),
            facts=len(_facts(ws.product_profile)),
            lace_exists=bool(website and await _existing_lace(db, ws.user_id, website)),
        ))
    return out


def _json(value):
    """SQL NULL for nothing: a bare None in a JSON column stores JSON null."""
    return value if value else null()


async def _lace_for(db: AsyncSession, ws: models.Workspace, website: str) -> Lace:
    lace = await _existing_lace(db, ws.user_id, website)
    if lace is None:
        profile = ws.product_profile
        name = (ws.name or (profile.product_name if profile else None) or domain_key(website))[:LACE_NAME_CHARS]
        lace = Lace(user_id=ws.user_id, name=name, website=website, status="active",
                    startup_name=(profile.product_name if profile else None))
        db.add(lace)
        await db.flush()
    return lace


async def _copy_facts(db: AsyncSession, lace: Lace, ws: models.Workspace, website: str) -> None:
    confirmed = bool(ws.product_profile and ws.product_profile.confirmed)
    for topic, claim in _facts(ws.product_profile):
        if await db.scalar(select(exists().where(LaceFact.lace_id == lace.id, LaceFact.claim == claim))):
            continue
        db.add(LaceFact(lace_id=lace.id, topic=topic, claim=claim, source_url=website,
                        confidence="high" if confirmed else "medium", origin="crawl"))


async def _copy_competitors(db: AsyncSession, lace: Lace, ws_id: uuid.UUID) -> None:
    for c in (await db.scalars(select(models.Competitor).where(models.Competitor.workspace_id == ws_id))).all():
        website = normalize_website(c.website)
        await db.execute(insert(LaceCompetitor).values(
            id=uuid.uuid4(), lace_id=lace.id, name=c.name[:255], website=website, domain_key=domain_key(website)[:255],
            summary=c.description, origin="founder" if c.source == "user" else "found", status="tracked",
            monitor_state=_json(c.monitor_state), last_checked_at=c.last_checked_at,
            first_seen_at=c.first_seen_at, last_seen_at=c.last_seen_at,
        ).on_conflict_do_nothing(constraint="uq_lace_competitors_lace_id_owner_id_domain_key"))


async def _copy_accounts(db: AsyncSession, lace: Lace, ws_id: uuid.UUID) -> dict[uuid.UUID, uuid.UUID]:
    """Returns v1 account id -> Lace account id, for the outreach that follows.
    An account with no trigger stays behind: v2 never invents one."""
    ids: dict[uuid.UUID, uuid.UUID] = {}
    for a in (await db.scalars(select(models.Account).where(
            models.Account.workspace_id == ws_id, models.Account.trigger_event.is_not(None)))).all():
        record = AccountRecord.model_validate({f: getattr(a, f) for f in _RECORD_FIELDS if hasattr(a, f)})
        key = account_key(record)
        await db.execute(insert(LaceAccount).values(
            id=uuid.uuid4(), lace_id=lace.id, key=key, name=record.name[:255], account_type=record.account_type,
            website=record.website, geo=(record.geo or None) and record.geo[:120], score=record.score,
            fit_strength=(a.fit or {}).get("strength"), status=a.review_status, do_not_contact=a.do_not_contact,
            record=record.model_dump(mode="json"), fit=_json(a.fit), first_seen_at=a.created_at, last_seen_at=a.created_at,
        ).on_conflict_do_nothing(constraint="uq_lace_accounts_lace_id_owner_id_key"))
        account_id = await db.scalar(select(LaceAccount.id).where(LaceAccount.lace_id == lace.id, LaceAccount.team(),
                                                                   LaceAccount.key == key))
        ids[a.id] = account_id
        await lace_contacts.sync(db, lace.id, account_id, record.key_contacts, "discovery")
    return ids


async def _copy_outreach(db: AsyncSession, lace: Lace, ws_id: uuid.UUID, accounts: dict[uuid.UUID, uuid.UUID]) -> None:
    for m in (await db.scalars(select(models.OutreachMessage).where(
            models.OutreachMessage.workspace_id == ws_id, models.OutreachMessage.status.in_(_CARRIED_STATUSES)))).all():
        copied = exists().where(LaceOutreach.lace_id == lace.id, LaceOutreach.created_at == m.created_at,
                                LaceOutreach.body == m.body)
        if await db.scalar(select(copied)):
            continue
        db.add(LaceOutreach(
            lace_id=lace.id, user_id=m.user_id, account_id=accounts.get(m.account_id) if m.account_id else None,
            channel=m.channel, direction=m.direction, thread_id=m.thread_id, provider_message_id=m.provider_message_id,
            provider_log_id=m.provider_log_id, recipient_name=m.recipient_name, recipient_company=m.recipient_company,
            recipient_address=m.recipient_address, subject=m.subject, body=m.body, status=m.status, intent=m.intent,
            error=m.error, sent_at=m.sent_at, created_at=m.created_at,
        ))


async def apply(sessions, user_id: uuid.UUID | None = None) -> list[uuid.UUID]:
    """Move every movable workspace (of one user, or all). Each workspace is
    its own transaction, so a failure leaves the others moved. Returns the
    ids of the Laces written to."""
    async with sessions() as db:
        workspace_ids = [(ws.id, _website(ws)) for ws in await _workspaces(db, user_id)]
    laces: list[uuid.UUID] = []
    for ws_id, website in workspace_ids:
        if website is None:
            continue
        async with sessions() as db, db.begin():
            ws = await db.scalar(select(models.Workspace).where(models.Workspace.id == ws_id).options(
                selectinload(models.Workspace.product_profile).selectinload(models.ProductProfile.features)))
            lace = await _lace_for(db, ws, website)
            await _copy_facts(db, lace, ws, website)
            await _copy_competitors(db, lace, ws_id)
            await _copy_outreach(db, lace, ws_id, await _copy_accounts(db, lace, ws_id))
            laces.append(lace.id)
    return list(dict.fromkeys(laces))
