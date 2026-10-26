"""The signed-in user's Laces: create one (which starts it reading the site),
list them, read what one knows, read its conversation, and send it a message.
Work happens in runs; follow them at /runs/{run_id}/events."""

import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, File, Header, Query, UploadFile, status

from backend.app.api.deps import AdminLace, CurrentUser, DbSession, LaceMembership, MemberLace, OwnerLace
from backend.app.runs import lace as lace_runs
from backend.app.runs import manager
from backend.app.runs.lace import LaceThread
from backend.app.schemas.laces import (
    ContactDraftRequest,
    MoveResponse,
    DocumentResponse,
    ActivityReadResponse,
    ActivityResponse,
    AccountResponse,
    BriefResponse,
    BriefSettings,
    BriefSettingsUpdate,
    QuietHours,
    ChannelAccount,
    ChannelLinkRequest,
    ChannelResponse,
    AccountUpdateRequest,
    CompetitorResponse,
    AccountApprovalResponse,
    ContactApproval,
    ContactResponse,
    CompetitorUpdateRequest,
    FactCorrection,
    FactResponse,
    FunnelResponse,
    JobStartedResponse,
    FactReview,
    LaceCreateRequest,
    LaceActivityItem,
    LaceCreateResponse,
    LaceListItem,
    LaceSearchHit,
    LaceUpdate,
    LaceMessage,
    LaceMessageRequest,
    LaceResponse,
    LaceTurnResponse,
    OpportunityResponse,
    OpportunityUpdateRequest,
    OutreachResponse,
    OutreachReadRequest,
    AppActionResponse,
    LaceAppResponse,
    LaceAppUpdate,
    MAX_APP_ACTIONS_PER_PAGE,
    OutreachUpdateRequest,
)
# Registers the social actions' runners, which approving app actions runs.
from backend.app.services import (  # noqa: F401 -- registers their runners
    asana_actions, crm_actions, notion_actions, sheet_actions, slack_actions, social_actions, telegram_actions,
)
from backend.app.services import email, inbox, lace_app_actions, lace_app_settings, lace_accounts, lace_briefs, lace_cards, lace_documents, lace_activity, lace_contacts, lace_members, lace_search, lace_channels, lace_competitors, lace_opportunities, lace_outreach
from backend.app.services import connections as connection_service
from backend.app.services import laces as lace_service
from backend.app.services import runs as run_service
from backend.app.schemas.connections import ConnectStartResponse
from agents.lace.store import JobRefused
from backend.app.services.errors import ConflictError
from agents.schemas.lace import AppActionStatus, AccountStatus, CompetitorStatus, FactTopic, InboxPlatform
from backend.app.database.lace_models import Lace, LaceMember
from agents.schemas.opportunities import OpportunityStatus

router = APIRouter()

MAX_LACES_PER_PAGE = 50
MAX_FACTS_PER_PAGE = 200
MAX_MESSAGES_PER_PAGE = 200
MAX_COMPETITORS_PER_PAGE = 100
MAX_ACCOUNTS_PER_PAGE = 100
MAX_OUTREACH_PER_PAGE = 100
MAX_OPPORTUNITIES_PER_PAGE = 100
MAX_ACTIVITY_PER_PAGE = 100
MAX_CONTACTS_PER_PAGE = 500
MAX_SEARCH_PER_KIND = 20
MAX_DOCUMENTS_PER_PAGE = 100
MAX_MOVES_PER_PAGE = 300


def _view(lace: Lace, member: LaceMember) -> LaceResponse:
    """The Lace as one person sees it: with their role and their pin."""
    return LaceResponse.model_validate(lace).model_copy(update={"role": member.role, "pinned": member.pinned})


@router.post("", response_model=LaceCreateResponse, status_code=status.HTTP_201_CREATED)
async def create_lace(payload: LaceCreateRequest, user: CurrentUser, db: DbSession):
    lace = await lace_service.create(db, user.id, payload.name, payload.website, payload.timezone)
    run = await manager.start_lace_onboarding(user.id, lace.id)
    return LaceCreateResponse(lace=LaceResponse.model_validate(lace).model_copy(update={"role": "owner"}),
                              run_id=run.id)


@router.get("", response_model=list[LaceListItem])
async def list_laces(user: CurrentUser, db: DbSession,
                     limit: int = Query(default=20, ge=1, le=MAX_LACES_PER_PAGE)):
    return [LaceListItem(**_view(s.lace, s.member).model_dump(), mood=s.mood, last_active_at=s.last_active_at)
            for s in await lace_service.list_for_user(db, user.id, limit)]


# Declared before /{lace_id}, which would otherwise take "archived" as an id.
@router.get("/archived", response_model=list[LaceResponse])
async def list_archived_laces(user: CurrentUser, db: DbSession,
                              limit: int = Query(default=20, ge=1, le=MAX_LACES_PER_PAGE)):
    return [_view(lace, member) for lace, member in await lace_service.list_archived(db, user.id, limit)]


# Declared before /{lace_id}, which would otherwise take "search" as an id.
@router.get("/search", response_model=list[LaceSearchHit])
async def search_laces(user: CurrentUser, db: DbSession,
                       q: str = Query(min_length=lace_search.MIN_QUERY_LEN, max_length=lace_search.MAX_QUERY_LEN),
                       per_kind: int = Query(default=5, ge=1, le=MAX_SEARCH_PER_KIND)):
    """Search everything in the founder's Laces: the Laces, their facts,
    competitors, accounts, contacts, opportunities and conversations."""
    return await lace_search.search(db, user.id, q, per_kind)


# Declared before /{lace_id}, which would otherwise take "activity" as an id.
@router.get("/activity", response_model=list[LaceActivityItem])
async def list_all_activity(user: CurrentUser, db: DbSession, before: datetime | None = None,
                            limit: int = Query(default=30, ge=1, le=MAX_ACTIVITY_PER_PAGE)):
    """What all the founder's Laces did or found, newest first."""
    rows = await lace_activity.list_for_user(db, user.id, limit, before)
    actors = await lace_members.actors(db, [(a.lace_id, a.actor_id) for a, _ in rows if a.actor_id])
    return [_activity(LaceActivityItem, a, actors, lace_id=lace.id, lace_name=lace.name) for a, lace in rows]


def _activity(shape: type[ActivityResponse], item, actors: dict, **extra) -> ActivityResponse:
    """An activity row as the API shows it, with who did it (lace_members.actors)."""
    return shape(**ActivityResponse.model_validate(item).model_dump(exclude={"actor"}),
                 actor=actors.get((item.lace_id, item.actor_id)), **extra)


@router.get("/{lace_id}", response_model=LaceResponse)
async def get_lace(lace: MemberLace, me: LaceMembership):
    return _view(lace, me)


@router.patch("/{lace_id}", response_model=LaceResponse)
async def update_lace(lace: MemberLace, me: LaceMembership, payload: LaceUpdate, db: DbSession):
    """Pin or unpin the Lace in this person's sidebar."""
    if payload.pinned is not None:
        await lace_service.set_pinned(db, me, payload.pinned)
    return _view(lace, me)


@router.post("/{lace_id}/archive", response_model=LaceResponse)
async def archive_lace(lace: OwnerLace, me: LaceMembership, db: DbSession):
    """Out of the sidebar and the scheduled work, kept whole. 409 while it is working."""
    return _view(await lace_service.archive(db, lace), me)


@router.post("/{lace_id}/restore", response_model=LaceResponse)
async def restore_lace(lace: OwnerLace, me: LaceMembership, user: CurrentUser, db: DbSession):
    lace = await lace_service.restore(db, lace)
    # Updates that came in while it was archived.
    await manager.wake_lace(user.id, lace.id)
    return _view(lace, me)


@router.delete("/{lace_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_lace(lace: OwnerLace, db: DbSession):
    """The Lace and everything it found or wrote, for good. 409 while it is working."""
    lace_id = lace.id
    people = await lace_members.everyone(db, lace_id)
    await lace_service.delete_lace(db, lace)
    await lace_runs.forget_thread(LaceThread(lace_id))
    for person in people:
        await lace_runs.forget_thread(LaceThread(lace_id, person))


@router.post("/{lace_id}/onboarding", response_model=LaceTurnResponse, status_code=status.HTTP_202_ACCEPTED)
async def retry_onboarding(lace: MemberLace, user: CurrentUser, db: DbSession):
    """Read the site again after an onboarding that failed."""
    await lace_service.prepare_onboarding_retry(db, lace)
    await lace_runs.forget_thread(LaceThread(lace.id))
    run = await manager.start_lace_onboarding(user.id, lace.id)
    return LaceTurnResponse(run_id=run.id)


@router.get("/{lace_id}/facts", response_model=list[FactResponse])
async def list_facts(lace: MemberLace, db: DbSession, topic: FactTopic | None = None,
                     limit: int = Query(default=100, ge=1, le=MAX_FACTS_PER_PAGE)):
    return await lace_service.list_facts(db, lace.id, topic, limit)


@router.patch("/{lace_id}/facts/{fact_id}", response_model=FactResponse)
async def review_fact(lace: MemberLace, fact_id: uuid.UUID, payload: FactReview, db: DbSession):
    """Confirm a fact, or retract it as wrong: it leaves what the Lace knows."""
    return await lace_service.review_fact(db, lace.id, fact_id, payload.verdict)


@router.post("/{lace_id}/facts/{fact_id}/correction", response_model=FactResponse,
             status_code=status.HTTP_201_CREATED)
async def correct_fact(lace: MemberLace, fact_id: uuid.UUID, payload: FactCorrection, db: DbSession):
    """Rewrite a fact in the founder's words; the original is superseded."""
    return await lace_service.correct_fact(db, lace.id, fact_id, payload.claim)


@router.get("/{lace_id}/activity", response_model=list[ActivityResponse])
async def list_activity(lace: MemberLace, db: DbSession, before: datetime | None = None,
                        limit: int = Query(default=30, ge=1, le=MAX_ACTIVITY_PER_PAGE)):
    """What the Lace did or found, newest first; `before` pages back. Each
    item names who on the team did it or asked for it, on a Lace with a team."""
    rows = await lace_activity.list_for_lace(db, lace.id, limit, before)
    actors = await lace_members.actors(db, [(a.lace_id, a.actor_id) for a in rows if a.actor_id])
    return [_activity(ActivityResponse, a, actors) for a in rows]


@router.post("/{lace_id}/activity/read", response_model=ActivityReadResponse)
async def mark_activity_read(lace: MemberLace, db: DbSession):
    """The founder has seen the Feed."""
    return ActivityReadResponse(marked=await lace_activity.mark_all_read(db, lace.id))


@router.get("/{lace_id}/funnel", response_model=FunnelResponse)
async def get_funnel(lace: MemberLace, db: DbSession):
    """How far the target accounts have come: on file, contacted, replied, interested."""
    return FunnelResponse(**await lace_outreach.funnel(db, lace.id))


@router.get("/{lace_id}/contacts", response_model=list[ContactResponse])
async def list_contacts(lace: MemberLace, db: DbSession,
                        limit: int = Query(default=200, ge=1, le=MAX_CONTACTS_PER_PAGE)):
    """The people found at the Lace's target accounts, by account."""
    return [_contact(c, a.name) for c, a in await lace_contacts.list_for_lace(db, lace.id, limit)]


def _contact(c, account_name: str) -> ContactResponse:
    return ContactResponse(id=c.id, account_id=c.account_id, account_name=account_name, name=c.name, title=c.title,
                           email=c.email, linkedin=c.linkedin, x=c.x, instagram=c.instagram, facebook=c.facebook,
                           tiktok=c.tiktok, source=c.source, approved_at=c.approved_at,
                           first_seen_at=c.first_seen_at)


@router.patch("/{lace_id}/contacts/{contact_id}", response_model=ContactResponse)
async def approve_contact(lace: MemberLace, contact_id: uuid.UUID, payload: ContactApproval, db: DbSession):
    """Clear one person for outreach (or take it back): drafts go only to them."""
    contact = await lace_contacts.set_approved(db, lace.id, contact_id, payload.approved)
    account = await lace_accounts.get_in_lace(db, lace.id, contact.account_id)
    return _contact(contact, account.name)


@router.post("/{lace_id}/contacts/{contact_id}/draft", response_model=JobStartedResponse,
             status_code=status.HTTP_202_ACCEPTED)
async def draft_to_contact(lace: MemberLace, contact_id: uuid.UUID, payload: ContactDraftRequest, user: CurrentUser,
                           db: DbSession):
    """Ask the Lace to draft a first message to one person, by email or on
    one of their social accounts, with the founder's note. Approves them. The draft lands in
    Messaging for the founder to edit and send."""
    account_id, person = await lace_contacts.person_to_draft(db, lace.id, contact_id, payload.channel)
    try:
        run = await manager.start_lace_job("lace_drafts", user.id, lace.id, {
            "account_ids": [str(account_id)], "person": person, "note": payload.note, "actor_id": str(user.id)})
    except JobRefused as exc:
        raise ConflictError(str(exc)) from None
    return JobStartedResponse(run_id=run.id)


@router.post("/{lace_id}/accounts/{account_id}/contacts/approve", response_model=AccountApprovalResponse)
async def approve_account_contacts(lace: MemberLace, account_id: uuid.UUID, db: DbSession):
    """Clear everyone found at one account for outreach, in one click."""
    await lace_accounts.get_in_lace(db, lace.id, account_id)
    return AccountApprovalResponse(approved=await lace_contacts.approve_account(db, lace.id, account_id))


@router.get("/{lace_id}/messages", response_model=list[LaceMessage], response_model_exclude_none=True)
async def list_messages(lace: MemberLace, db: DbSession,
                        limit: int = Query(default=100, ge=1, le=MAX_MESSAGES_PER_PAGE)):
    """The conversation, each card marked with its item's status now, then
    the messages still waiting for the Lace to be free."""
    shown = await lace_cards.with_status(db, lace.id, await lace_runs.history(LaceThread(lace.id), limit))
    return [*shown, *await run_service.waiting_messages(db, lace.id)]


@router.post("/{lace_id}/messages", response_model=LaceTurnResponse, status_code=status.HTTP_202_ACCEPTED)
async def send_message(lace: MemberLace, payload: LaceMessageRequest, user: CurrentUser, db: DbSession):
    """A message to the Lace, with documents uploaded to it first attached,
    and about one of its unsent drafts when `draft_id` is given; or the
    founder's answer to a question under its latest reply."""
    return await _send(db, LaceThread(lace.id), payload, user)


@router.get("/{lace_id}/private/messages", response_model=list[LaceMessage], response_model_exclude_none=True)
async def list_private_messages(lace: MemberLace, user: CurrentUser, db: DbSession,
                                limit: int = Query(default=100, ge=1, le=MAX_MESSAGES_PER_PAGE)):
    """Your private chat with the Lace, which nobody else on the team sees."""
    await lace_members.ensure_team(db, lace.id)
    return await lace_cards.with_status(db, lace.id, await lace_runs.history(LaceThread(lace.id, user.id), limit))


@router.post("/{lace_id}/private/messages", response_model=LaceTurnResponse, status_code=status.HTTP_202_ACCEPTED)
async def send_private_message(lace: MemberLace, payload: LaceMessageRequest, user: CurrentUser, db: DbSession):
    """A message in your private chat: what the Lace finds there is yours
    until you push it to the team. 409 while it is still answering you."""
    await lace_members.ensure_team(db, lace.id)
    return await _send(db, LaceThread(lace.id, user.id), payload, user)


async def _send(db: DbSession, thread: LaceThread, payload: LaceMessageRequest, user: CurrentUser) -> LaceTurnResponse:
    author = {"id": str(user.id), "name": user.name or user.email, "avatar_url": user.avatar_url}
    # With a team on the Lace, it reads each message as from its sender.
    name_for_lace = author["name"] if await lace_members.team_size(db, thread.lace_id) > 1 else None
    if payload.answer is not None:
        run, queued = await manager.start_lace_answer(user.id, thread, payload.answer, author, name_for_lace)
        return LaceTurnResponse(run_id=run.id, queued=queued)
    docs = await lace_documents.attachments(db, thread.lace_id, payload.document_ids)
    attached = [{"id": str(d.id), "filename": d.filename} for d in docs]
    draft = await lace_outreach.unsent_draft(db, thread.lace_id, payload.draft_id) if payload.draft_id else None
    run, queued = await manager.start_lace_turn(user.id, thread, payload.text, author, name_for_lace, attached, draft)
    return LaceTurnResponse(run_id=run.id, queued=queued)


@router.post("/{lace_id}/documents", response_model=DocumentResponse, status_code=status.HTTP_201_CREATED)
async def upload_document(lace: MemberLace, db: DbSession, file: UploadFile = File(...)):
    """Share a document with the Lace: its text is extracted and kept (PDF,
    Word, PowerPoint, text, Markdown, CSV, JSON)."""
    # One byte over the cap is enough to refuse it without reading the rest.
    data = await file.read(lace_documents.max_bytes() + 1)
    return await lace_documents.add(db, lace.id, file.filename or "document", file.content_type, data)


@router.get("/{lace_id}/documents", response_model=list[DocumentResponse])
async def list_documents(lace: MemberLace, db: DbSession,
                         limit: int = Query(default=50, ge=1, le=MAX_DOCUMENTS_PER_PAGE)):
    return await lace_documents.list_for_lace(db, lace.id, limit)


@router.delete("/{lace_id}/documents/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_document(lace: MemberLace, document_id: uuid.UUID, db: DbSession):
    await lace_documents.delete(db, lace.id, document_id)


@router.get("/{lace_id}/competitors", response_model=list[CompetitorResponse])
async def list_competitors(lace: MemberLace, db: DbSession,
                           shown: CompetitorStatus = Query(default="tracked", alias="status"),
                           limit: int = Query(default=50, ge=1, le=MAX_COMPETITORS_PER_PAGE)):
    return await lace_competitors.list_for_lace(db, lace.id, shown, limit)


@router.get("/{lace_id}/moves", response_model=list[MoveResponse])
async def list_moves(lace: MemberLace, db: DbSession, limit: int = Query(default=100, ge=1, le=MAX_MOVES_PER_PAGE)):
    """What the tracked competitors did, newest first, each with its sources."""
    return [MoveResponse(**{c.name: getattr(move, c.name) for c in move.__table__.columns
                            if c.name in MoveResponse.model_fields}, competitor_name=name)
            for move, name in await lace_competitors.list_moves(db, lace.id, limit)]


@router.patch("/{lace_id}/competitors/{competitor_id}", response_model=CompetitorResponse)
async def update_competitor(lace: MemberLace, competitor_id: uuid.UUID, payload: CompetitorUpdateRequest,
                            user: CurrentUser, db: DbSession):
    return await lace_competitors.set_status(db, lace.id, competitor_id, payload.status, user.id, user.id)


@router.get("/{lace_id}/accounts", response_model=list[AccountResponse])
async def list_accounts(lace: MemberLace, db: DbSession, shown: AccountStatus = Query(default="target", alias="status"),
                        limit: int = Query(default=50, ge=1, le=MAX_ACCOUNTS_PER_PAGE)):
    return [lace_accounts.response(r) for r in await lace_accounts.list_for_lace(db, lace.id, shown, limit)]


@router.patch("/{lace_id}/accounts/{account_id}", response_model=AccountResponse)
async def update_account(lace: MemberLace, account_id: uuid.UUID, payload: AccountUpdateRequest,
                         user: CurrentUser, db: DbSession):
    return lace_accounts.response(await lace_accounts.set_status(db, lace.id, account_id, payload.status, user.id,
                                                                 user.id))


@router.post("/{lace_id}/accounts/{account_id}/find-contacts", response_model=JobStartedResponse,
             status_code=status.HTTP_202_ACCEPTED)
async def find_account_contacts(lace: MemberLace, account_id: uuid.UUID, user: CurrentUser, db: DbSession):
    """Look for the people to contact at one account, from a card in the
    chat. The Lace reports back when it is done."""
    account = await lace_accounts.get_in_lace(db, lace.id, account_id, user.id)
    # One of your private accounts is searched in your private chat.
    private = {"private_to": str(account.owner_id)} if account.owner_id else {}
    try:
        run = await manager.start_lace_job("lace_contacts", user.id, lace.id, {"account_ids": [str(account_id)],
                                                                             "actor_id": str(user.id), **private})
    except JobRefused as exc:
        raise ConflictError(str(exc)) from None
    return JobStartedResponse(run_id=run.id)


@router.get("/{lace_id}/outreach", response_model=list[OutreachResponse])
async def list_outreach(lace: MemberLace, db: DbSession, limit: int = Query(default=50, ge=1, le=MAX_OUTREACH_PER_PAGE)):
    return await lace_outreach.list_for_lace(db, lace.id, limit)


@router.patch("/{lace_id}/outreach/{message_id}", response_model=OutreachResponse)
async def update_outreach(lace: MemberLace, message_id: uuid.UUID, payload: OutreachUpdateRequest, db: DbSession):
    message = await lace_outreach.get_in_lace(db, lace.id, message_id)
    return await lace_outreach.update(db, message, payload.model_dump(exclude_unset=True))


@router.delete("/{lace_id}/outreach/{message_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_outreach(lace: MemberLace, message_id: uuid.UUID, db: DbSession):
    await lace_outreach.delete(db, await lace_outreach.get_in_lace(db, lace.id, message_id))


@router.post("/{lace_id}/outreach/{message_id}/send", response_model=OutreachResponse)
async def send_outreach(lace: MemberLace, message_id: uuid.UUID, user: CurrentUser, db: DbSession):
    """Send an email draft through your Gmail. The Lace never sends: this
    request, made by you, is the approval."""
    return await lace_outreach.send(db, await lace_outreach.get_in_lace(db, lace.id, message_id), user.id)


@router.post("/{lace_id}/outreach/{message_id}/mark-sent", response_model=OutreachResponse)
async def mark_outreach_sent(lace: MemberLace, message_id: uuid.UUID, user: CurrentUser, db: DbSession):
    """Record a LinkedIn message you sent by hand."""
    return await lace_outreach.mark_sent(db, await lace_outreach.get_in_lace(db, lace.id, message_id), user.id)


@router.post("/{lace_id}/outreach/read", response_model=ActivityReadResponse)
async def mark_outreach_read(lace: MemberLace, payload: OutreachReadRequest, db: DbSession):
    """The founder opened these replies."""
    return ActivityReadResponse(marked=await lace_outreach.mark_read(db, lace.id, payload.ids))


@router.get("/{lace_id}/apps", response_model=list[LaceAppResponse])
async def list_lace_apps(lace: MemberLace, db: DbSession):
    """Every app: connected or not, and whether this Lace may use it."""
    return await lace_app_settings.list_for_lace(db, lace)


@router.put("/{lace_id}/apps/{platform}", response_model=LaceAppResponse)
async def update_lace_app(lace: AdminLace, platform: str, payload: LaceAppUpdate, db: DbSession):
    """Switch an app on or off for this Lace, or change its settings here."""
    await lace_app_settings.update(db, lace, platform, payload.enabled, payload.settings)
    return next(a for a in await lace_app_settings.list_for_lace(db, lace) if a["platform"] == platform)


@router.post("/{lace_id}/connections/{platform}", response_model=ConnectStartResponse)
async def start_lace_connection(lace: AdminLace, platform: str, origin: str | None = Header(default=None),
                                return_to: str | None = Query(default=None, max_length=200)):
    """A Connect Link for an account of the Lace's own, which it then uses
    instead of the founder's shared one for that app."""
    return ConnectStartResponse(redirect_url=await connection_service.start(
        connection_service.lace_entity(lace.id), platform, origin, return_to))


@router.delete("/{lace_id}/connections/{connection_id}", status_code=status.HTTP_204_NO_CONTENT)
async def disconnect_lace_connection(lace: AdminLace, connection_id: str, db: DbSession):
    """Disconnect the Lace's own account; it goes back to the shared one."""
    await connection_service.disconnect(db, connection_service.lace_entity(lace.id), connection_id)


@router.get("/{lace_id}/app-actions", response_model=list[AppActionResponse])
async def list_app_actions(lace: MemberLace, db: DbSession, status: AppActionStatus | None = None,
                           limit: int = Query(default=50, ge=1, le=MAX_APP_ACTIONS_PER_PAGE)):
    """What the Lace proposed doing in the founder's apps, newest first."""
    return await lace_app_actions.list_for_lace(db, lace.id, limit, status)


@router.post("/{lace_id}/app-actions/{action_id}/approve", response_model=AppActionResponse)
async def approve_app_action(lace: MemberLace, action_id: uuid.UUID, user: CurrentUser, db: DbSession):
    """Run a proposed action from the Lace's account. This request, made by the founder, is the approval."""
    row = await lace_app_actions.approve(db, await lace_app_actions.get_in_lace(db, lace.id, action_id), user.id)
    await manager.wake_lace(user.id, lace.id)
    return row


@router.post("/{lace_id}/app-actions/{action_id}/decline", response_model=AppActionResponse)
async def decline_app_action(lace: MemberLace, action_id: uuid.UUID, db: DbSession):
    return await lace_app_actions.decline(db, await lace_app_actions.get_in_lace(db, lace.id, action_id))


@router.get("/{lace_id}/channels", response_model=list[ChannelResponse])
async def list_channels(lace: MemberLace, db: DbSession):
    """The Instagram and Facebook accounts whose DMs this Lace reads."""
    return await lace_channels.list_for_lace(db, lace.id)


@router.get("/{lace_id}/channels/available", response_model=list[ChannelAccount])
async def available_channels(lace: MemberLace, platform: InboxPlatform, db: DbSession):
    """The accounts the Lace's connected Instagram or Facebook manages, to link one."""
    return await lace_channels.available(db, lace, platform)


@router.post("/{lace_id}/channels", response_model=ChannelResponse, status_code=status.HTTP_201_CREATED)
async def link_channel(lace: AdminLace, payload: ChannelLinkRequest, db: DbSession):
    return await lace_channels.link(db, lace, payload.platform, payload.account_id)


@router.delete("/{lace_id}/channels/{channel_id}", status_code=status.HTTP_204_NO_CONTENT)
async def unlink_channel(lace: AdminLace, channel_id: uuid.UUID, db: DbSession):
    await lace_channels.unlink(db, lace.id, channel_id)


@router.get("/{lace_id}/opportunities", response_model=list[OpportunityResponse])
async def list_opportunities(lace: MemberLace, db: DbSession,
                             shown: OpportunityStatus = Query(default="open", alias="status"),
                             limit: int = Query(default=50, ge=1, le=MAX_OPPORTUNITIES_PER_PAGE)):
    """Open ones exclude anything whose deadline or date has passed."""
    return await lace_opportunities.list_for_lace(db, lace.id, shown, limit)


@router.patch("/{lace_id}/opportunities/{opportunity_id}", response_model=OpportunityResponse)
async def update_opportunity(lace: MemberLace, opportunity_id: uuid.UUID, payload: OpportunityUpdateRequest,
                             user: CurrentUser, db: DbSession):
    return await lace_opportunities.set_status(db, lace.id, opportunity_id, payload.status, user.id, user.id)


def _brief_settings(lace) -> BriefSettings:
    quiet = None if lace.quiet_start is None else QuietHours(start=lace.quiet_start, end=lace.quiet_end)
    return BriefSettings.model_validate(lace).model_copy(update={
        "quiet_hours": quiet, "email_available": email.configured(),
        "reply_check_minutes": inbox.check_minutes()})


@router.get("/{lace_id}/brief", response_model=BriefSettings)
async def get_brief_settings(lace: MemberLace):
    """The Lace's schedule: when it posts its brief (how often, at what local
    hour), whether it is emailed too, the quiet hours in which nothing is
    emailed, and how often it keeps watch."""
    return _brief_settings(lace)


@router.get("/{lace_id}/briefs/latest", response_model=BriefResponse | None)
async def latest_brief(lace: MemberLace, db: DbSession):
    """The Lace's latest brief: being written, written, or missed; null when
    it has posted none yet."""
    brief = await lace_briefs.latest(db, lace.id)
    if brief is None:
        return None
    return BriefResponse(id=brief.id, created_at=brief.created_at, posted_at=brief.posted_at, body=brief.body,
                         state=lace_briefs.state(brief, datetime.now(UTC)))


@router.patch("/{lace_id}/brief", response_model=BriefSettings)
async def update_brief_settings(lace: AdminLace, payload: BriefSettingsUpdate, db: DbSession):
    return _brief_settings(await lace_service.update_brief_settings(db, lace, payload.model_dump(exclude_unset=True)))
