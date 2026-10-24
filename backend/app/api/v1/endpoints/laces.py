"""The signed-in user's Laces: create one (which starts it reading the site),
list them, read what one knows, read its conversation, and send it a message.
Work happens in runs; follow them at /runs/{run_id}/events."""

import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, File, Query, UploadFile, status

from backend.app.api.deps import CurrentUser, DbSession, OwnedLace
from backend.app.runs import lace as lace_runs
from backend.app.runs import manager
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
    MAX_APP_ACTIONS_PER_PAGE,
    OutreachUpdateRequest,
)
from backend.app.services import email, inbox, lace_app_actions, lace_accounts, lace_briefs, lace_cards, lace_documents, lace_activity, lace_contacts, lace_search, lace_channels, lace_competitors, lace_opportunities, lace_outreach
from backend.app.services import laces as lace_service
from agents.lace.store import JobRefused
from backend.app.services.errors import ConflictError
from agents.schemas.lace import AppActionStatus, AccountStatus, CompetitorStatus, FactTopic, InboxPlatform
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


@router.post("", response_model=LaceCreateResponse, status_code=status.HTTP_201_CREATED)
async def create_lace(payload: LaceCreateRequest, user: CurrentUser, db: DbSession):
    lace = await lace_service.create(db, user.id, payload.name, payload.website, payload.timezone)
    run = await manager.start_lace_onboarding(user.id, lace.id)
    return LaceCreateResponse(lace=LaceResponse.model_validate(lace), run_id=run.id)


@router.get("", response_model=list[LaceListItem])
async def list_laces(user: CurrentUser, db: DbSession,
                     limit: int = Query(default=20, ge=1, le=MAX_LACES_PER_PAGE)):
    return [LaceListItem(**LaceResponse.model_validate(s.lace).model_dump(), mood=s.mood, last_active_at=s.last_active_at)
            for s in await lace_service.list_for_user(db, user.id, limit)]


# Declared before /{lace_id}, which would otherwise take "archived" as an id.
@router.get("/archived", response_model=list[LaceResponse])
async def list_archived_laces(user: CurrentUser, db: DbSession,
                              limit: int = Query(default=20, ge=1, le=MAX_LACES_PER_PAGE)):
    return await lace_service.list_archived(db, user.id, limit)


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
    return [LaceActivityItem(**ActivityResponse.model_validate(a).model_dump(), lace_id=lace.id, lace_name=lace.name)
            for a, lace in await lace_activity.list_for_user(db, user.id, limit, before)]


@router.get("/{lace_id}", response_model=LaceResponse)
async def get_lace(lace: OwnedLace):
    return lace


@router.patch("/{lace_id}", response_model=LaceResponse)
async def update_lace(lace: OwnedLace, payload: LaceUpdate, db: DbSession):
    """Pin or unpin the Lace in the founder's sidebar."""
    if payload.pinned is not None:
        lace = await lace_service.set_pinned(db, lace, payload.pinned)
    return lace


@router.post("/{lace_id}/archive", response_model=LaceResponse)
async def archive_lace(lace: OwnedLace, db: DbSession):
    """Out of the sidebar and the scheduled work, kept whole. 409 while it is working."""
    return await lace_service.archive(db, lace)


@router.post("/{lace_id}/restore", response_model=LaceResponse)
async def restore_lace(lace: OwnedLace, user: CurrentUser, db: DbSession):
    lace = await lace_service.restore(db, lace)
    # Updates that came in while it was archived.
    await manager.wake_lace(user.id, lace.id)
    return lace


@router.delete("/{lace_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_lace(lace: OwnedLace, db: DbSession):
    """The Lace and everything it found or wrote, for good. 409 while it is working."""
    lace_id = lace.id
    await lace_service.delete_lace(db, lace)
    await lace_runs.forget_thread(lace_id)


@router.post("/{lace_id}/onboarding", response_model=LaceTurnResponse, status_code=status.HTTP_202_ACCEPTED)
async def retry_onboarding(lace: OwnedLace, user: CurrentUser, db: DbSession):
    """Read the site again after an onboarding that failed."""
    await lace_service.prepare_onboarding_retry(db, lace)
    await lace_runs.forget_thread(lace.id)
    run = await manager.start_lace_onboarding(user.id, lace.id)
    return LaceTurnResponse(run_id=run.id)


@router.get("/{lace_id}/facts", response_model=list[FactResponse])
async def list_facts(lace: OwnedLace, db: DbSession, topic: FactTopic | None = None,
                     limit: int = Query(default=100, ge=1, le=MAX_FACTS_PER_PAGE)):
    return await lace_service.list_facts(db, lace.id, topic, limit)


@router.patch("/{lace_id}/facts/{fact_id}", response_model=FactResponse)
async def review_fact(lace: OwnedLace, fact_id: uuid.UUID, payload: FactReview, db: DbSession):
    """Confirm a fact, or retract it as wrong: it leaves what the Lace knows."""
    return await lace_service.review_fact(db, lace.id, fact_id, payload.verdict)


@router.post("/{lace_id}/facts/{fact_id}/correction", response_model=FactResponse,
             status_code=status.HTTP_201_CREATED)
async def correct_fact(lace: OwnedLace, fact_id: uuid.UUID, payload: FactCorrection, db: DbSession):
    """Rewrite a fact in the founder's words; the original is superseded."""
    return await lace_service.correct_fact(db, lace.id, fact_id, payload.claim)


@router.get("/{lace_id}/activity", response_model=list[ActivityResponse])
async def list_activity(lace: OwnedLace, db: DbSession, before: datetime | None = None,
                        limit: int = Query(default=30, ge=1, le=MAX_ACTIVITY_PER_PAGE)):
    """What the Lace did or found, newest first; `before` pages back."""
    return await lace_activity.list_for_lace(db, lace.id, limit, before)


@router.post("/{lace_id}/activity/read", response_model=ActivityReadResponse)
async def mark_activity_read(lace: OwnedLace, db: DbSession):
    """The founder has seen the Feed."""
    return ActivityReadResponse(marked=await lace_activity.mark_all_read(db, lace.id))


@router.get("/{lace_id}/funnel", response_model=FunnelResponse)
async def get_funnel(lace: OwnedLace, db: DbSession):
    """How far the target accounts have come: on file, contacted, replied, interested."""
    return FunnelResponse(**await lace_outreach.funnel(db, lace.id))


@router.get("/{lace_id}/contacts", response_model=list[ContactResponse])
async def list_contacts(lace: OwnedLace, db: DbSession,
                        limit: int = Query(default=200, ge=1, le=MAX_CONTACTS_PER_PAGE)):
    """The people found at the Lace's target accounts, by account."""
    return [_contact(c, a.name) for c, a in await lace_contacts.list_for_lace(db, lace.id, limit)]


def _contact(c, account_name: str) -> ContactResponse:
    return ContactResponse(id=c.id, account_id=c.account_id, account_name=account_name, name=c.name, title=c.title,
                           email=c.email, linkedin=c.linkedin, x=c.x, instagram=c.instagram, facebook=c.facebook,
                           tiktok=c.tiktok, source=c.source, approved_at=c.approved_at,
                           first_seen_at=c.first_seen_at)


@router.patch("/{lace_id}/contacts/{contact_id}", response_model=ContactResponse)
async def approve_contact(lace: OwnedLace, contact_id: uuid.UUID, payload: ContactApproval, db: DbSession):
    """Clear one person for outreach (or take it back): drafts go only to them."""
    contact = await lace_contacts.set_approved(db, lace.id, contact_id, payload.approved)
    account = await lace_accounts.get_in_lace(db, lace.id, contact.account_id)
    return _contact(contact, account.name)


@router.post("/{lace_id}/contacts/{contact_id}/draft", response_model=JobStartedResponse,
             status_code=status.HTTP_202_ACCEPTED)
async def draft_to_contact(lace: OwnedLace, contact_id: uuid.UUID, payload: ContactDraftRequest, user: CurrentUser,
                           db: DbSession):
    """Ask the Lace to draft a first message to one person, by email or on
    one of their social accounts, with the founder's note. Approves them. The draft lands in
    Messaging for the founder to edit and send."""
    account_id, person = await lace_contacts.person_to_draft(db, lace.id, contact_id, payload.channel)
    try:
        run = await manager.start_lace_job("lace_drafts", user.id, lace.id, {
            "account_ids": [str(account_id)], "person": person, "note": payload.note})
    except JobRefused as exc:
        raise ConflictError(str(exc)) from None
    return JobStartedResponse(run_id=run.id)


@router.post("/{lace_id}/accounts/{account_id}/contacts/approve", response_model=AccountApprovalResponse)
async def approve_account_contacts(lace: OwnedLace, account_id: uuid.UUID, db: DbSession):
    """Clear everyone found at one account for outreach, in one click."""
    await lace_accounts.get_in_lace(db, lace.id, account_id)
    return AccountApprovalResponse(approved=await lace_contacts.approve_account(db, lace.id, account_id))


@router.get("/{lace_id}/messages", response_model=list[LaceMessage], response_model_exclude_none=True)
async def list_messages(lace: OwnedLace, db: DbSession,
                        limit: int = Query(default=100, ge=1, le=MAX_MESSAGES_PER_PAGE)):
    """The conversation, each card marked with its item's status now."""
    return await lace_cards.with_status(db, lace.id, await lace_runs.history(lace.id, limit))


@router.post("/{lace_id}/messages", response_model=LaceTurnResponse, status_code=status.HTTP_202_ACCEPTED)
async def send_message(lace: OwnedLace, payload: LaceMessageRequest, user: CurrentUser, db: DbSession):
    """A message to the Lace, with documents uploaded to it first attached,
    and about one of its unsent drafts when `draft_id` is given; or the
    founder's answer to a question under its latest reply."""
    if payload.answer is not None:
        return LaceTurnResponse(run_id=(await manager.start_lace_answer(user.id, lace.id, payload.answer)).id)
    docs = await lace_documents.attachments(db, lace.id, payload.document_ids)
    attached = [{"id": str(d.id), "filename": d.filename} for d in docs]
    draft = await lace_outreach.unsent_draft(db, lace.id, payload.draft_id) if payload.draft_id else None
    run = await manager.start_lace_turn(user.id, lace.id, payload.text, attached, draft)
    return LaceTurnResponse(run_id=run.id)


@router.post("/{lace_id}/documents", response_model=DocumentResponse, status_code=status.HTTP_201_CREATED)
async def upload_document(lace: OwnedLace, db: DbSession, file: UploadFile = File(...)):
    """Share a document with the Lace: its text is extracted and kept (PDF,
    Word, PowerPoint, text, Markdown, CSV, JSON)."""
    # One byte over the cap is enough to refuse it without reading the rest.
    data = await file.read(lace_documents.max_bytes() + 1)
    return await lace_documents.add(db, lace.id, file.filename or "document", file.content_type, data)


@router.get("/{lace_id}/documents", response_model=list[DocumentResponse])
async def list_documents(lace: OwnedLace, db: DbSession,
                         limit: int = Query(default=50, ge=1, le=MAX_DOCUMENTS_PER_PAGE)):
    return await lace_documents.list_for_lace(db, lace.id, limit)


@router.delete("/{lace_id}/documents/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_document(lace: OwnedLace, document_id: uuid.UUID, db: DbSession):
    await lace_documents.delete(db, lace.id, document_id)


@router.get("/{lace_id}/competitors", response_model=list[CompetitorResponse])
async def list_competitors(lace: OwnedLace, db: DbSession,
                           shown: CompetitorStatus = Query(default="tracked", alias="status"),
                           limit: int = Query(default=50, ge=1, le=MAX_COMPETITORS_PER_PAGE)):
    return await lace_competitors.list_for_lace(db, lace.id, shown, limit)


@router.get("/{lace_id}/moves", response_model=list[MoveResponse])
async def list_moves(lace: OwnedLace, db: DbSession, limit: int = Query(default=100, ge=1, le=MAX_MOVES_PER_PAGE)):
    """What the tracked competitors did, newest first, each with its sources."""
    return [MoveResponse(**{c.name: getattr(move, c.name) for c in move.__table__.columns
                            if c.name in MoveResponse.model_fields}, competitor_name=name)
            for move, name in await lace_competitors.list_moves(db, lace.id, limit)]


@router.patch("/{lace_id}/competitors/{competitor_id}", response_model=CompetitorResponse)
async def update_competitor(lace: OwnedLace, competitor_id: uuid.UUID, payload: CompetitorUpdateRequest, db: DbSession):
    return await lace_competitors.set_status(db, lace.id, competitor_id, payload.status)


@router.get("/{lace_id}/accounts", response_model=list[AccountResponse])
async def list_accounts(lace: OwnedLace, db: DbSession, shown: AccountStatus = Query(default="target", alias="status"),
                        limit: int = Query(default=50, ge=1, le=MAX_ACCOUNTS_PER_PAGE)):
    return [lace_accounts.response(r) for r in await lace_accounts.list_for_lace(db, lace.id, shown, limit)]


@router.patch("/{lace_id}/accounts/{account_id}", response_model=AccountResponse)
async def update_account(lace: OwnedLace, account_id: uuid.UUID, payload: AccountUpdateRequest, db: DbSession):
    return lace_accounts.response(await lace_accounts.set_status(db, lace.id, account_id, payload.status))


@router.post("/{lace_id}/accounts/{account_id}/find-contacts", response_model=JobStartedResponse,
             status_code=status.HTTP_202_ACCEPTED)
async def find_account_contacts(lace: OwnedLace, account_id: uuid.UUID, user: CurrentUser, db: DbSession):
    """Look for the people to contact at one account, from a card in the
    chat. The Lace reports back when it is done."""
    await lace_accounts.get_in_lace(db, lace.id, account_id)
    try:
        run = await manager.start_lace_job("lace_contacts", user.id, lace.id, {"account_ids": [str(account_id)]})
    except JobRefused as exc:
        raise ConflictError(str(exc)) from None
    return JobStartedResponse(run_id=run.id)


@router.get("/{lace_id}/outreach", response_model=list[OutreachResponse])
async def list_outreach(lace: OwnedLace, db: DbSession, limit: int = Query(default=50, ge=1, le=MAX_OUTREACH_PER_PAGE)):
    return await lace_outreach.list_for_lace(db, lace.id, limit)


@router.patch("/{lace_id}/outreach/{message_id}", response_model=OutreachResponse)
async def update_outreach(lace: OwnedLace, message_id: uuid.UUID, payload: OutreachUpdateRequest, db: DbSession):
    message = await lace_outreach.get_in_lace(db, lace.id, message_id)
    return await lace_outreach.update(db, message, payload.model_dump(exclude_unset=True))


@router.delete("/{lace_id}/outreach/{message_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_outreach(lace: OwnedLace, message_id: uuid.UUID, db: DbSession):
    await lace_outreach.delete(db, await lace_outreach.get_in_lace(db, lace.id, message_id))


@router.post("/{lace_id}/outreach/{message_id}/send", response_model=OutreachResponse)
async def send_outreach(lace: OwnedLace, message_id: uuid.UUID, db: DbSession):
    """Send an email draft through your Gmail. The Lace never sends: this
    request, made by you, is the approval."""
    return await lace_outreach.send(db, await lace_outreach.get_in_lace(db, lace.id, message_id))


@router.post("/{lace_id}/outreach/{message_id}/mark-sent", response_model=OutreachResponse)
async def mark_outreach_sent(lace: OwnedLace, message_id: uuid.UUID, db: DbSession):
    """Record a LinkedIn message you sent by hand."""
    return await lace_outreach.mark_sent(db, await lace_outreach.get_in_lace(db, lace.id, message_id))


@router.post("/{lace_id}/outreach/read", response_model=ActivityReadResponse)
async def mark_outreach_read(lace: OwnedLace, payload: OutreachReadRequest, db: DbSession):
    """The founder opened these replies."""
    return ActivityReadResponse(marked=await lace_outreach.mark_read(db, lace.id, payload.ids))


@router.get("/{lace_id}/app-actions", response_model=list[AppActionResponse])
async def list_app_actions(lace: OwnedLace, db: DbSession, status: AppActionStatus | None = None,
                           limit: int = Query(default=50, ge=1, le=MAX_APP_ACTIONS_PER_PAGE)):
    """What the Lace proposed doing in the founder's apps, newest first."""
    return await lace_app_actions.list_for_lace(db, lace.id, limit, status)


@router.post("/{lace_id}/app-actions/{action_id}/approve", response_model=AppActionResponse)
async def approve_app_action(lace: OwnedLace, action_id: uuid.UUID, user: CurrentUser, db: DbSession):
    """Run a proposed action as the founder. This request, made by them, is the approval."""
    row = await lace_app_actions.approve(db, await lace_app_actions.get_in_lace(db, lace.id, action_id), user.id)
    await manager.wake_lace(user.id, lace.id)
    return row


@router.post("/{lace_id}/app-actions/{action_id}/decline", response_model=AppActionResponse)
async def decline_app_action(lace: OwnedLace, action_id: uuid.UUID, db: DbSession):
    return await lace_app_actions.decline(db, await lace_app_actions.get_in_lace(db, lace.id, action_id))


@router.get("/{lace_id}/channels", response_model=list[ChannelResponse])
async def list_channels(lace: OwnedLace, db: DbSession):
    """The Instagram and Facebook accounts whose DMs this Lace reads."""
    return await lace_channels.list_for_lace(db, lace.id)


@router.get("/{lace_id}/channels/available", response_model=list[ChannelAccount])
async def available_channels(lace: OwnedLace, platform: InboxPlatform, user: CurrentUser, db: DbSession):
    """The accounts your connected Instagram or Facebook manages, to link one."""
    return await lace_channels.available(db, user.id, platform)


@router.post("/{lace_id}/channels", response_model=ChannelResponse, status_code=status.HTTP_201_CREATED)
async def link_channel(lace: OwnedLace, payload: ChannelLinkRequest, user: CurrentUser, db: DbSession):
    return await lace_channels.link(db, lace.id, user.id, payload.platform, payload.account_id)


@router.delete("/{lace_id}/channels/{channel_id}", status_code=status.HTTP_204_NO_CONTENT)
async def unlink_channel(lace: OwnedLace, channel_id: uuid.UUID, db: DbSession):
    await lace_channels.unlink(db, lace.id, channel_id)


@router.get("/{lace_id}/opportunities", response_model=list[OpportunityResponse])
async def list_opportunities(lace: OwnedLace, db: DbSession,
                             shown: OpportunityStatus = Query(default="open", alias="status"),
                             limit: int = Query(default=50, ge=1, le=MAX_OPPORTUNITIES_PER_PAGE)):
    """Open ones exclude anything whose deadline or date has passed."""
    return await lace_opportunities.list_for_lace(db, lace.id, shown, limit)


@router.patch("/{lace_id}/opportunities/{opportunity_id}", response_model=OpportunityResponse)
async def update_opportunity(lace: OwnedLace, opportunity_id: uuid.UUID, payload: OpportunityUpdateRequest,
                             db: DbSession):
    return await lace_opportunities.set_status(db, lace.id, opportunity_id, payload.status)


def _brief_settings(lace) -> BriefSettings:
    quiet = None if lace.quiet_start is None else QuietHours(start=lace.quiet_start, end=lace.quiet_end)
    return BriefSettings.model_validate(lace).model_copy(update={
        "quiet_hours": quiet, "email_available": email.configured(),
        "reply_check_minutes": inbox.check_minutes()})


@router.get("/{lace_id}/brief", response_model=BriefSettings)
async def get_brief_settings(lace: OwnedLace):
    """The Lace's schedule: when it posts its brief (how often, at what local
    hour), whether it is emailed too, the quiet hours in which nothing is
    emailed, and how often it keeps watch."""
    return _brief_settings(lace)


@router.get("/{lace_id}/briefs/latest", response_model=BriefResponse | None)
async def latest_brief(lace: OwnedLace, db: DbSession):
    """The Lace's latest brief: being written, written, or missed; null when
    it has posted none yet."""
    brief = await lace_briefs.latest(db, lace.id)
    if brief is None:
        return None
    return BriefResponse(id=brief.id, created_at=brief.created_at, posted_at=brief.posted_at, body=brief.body,
                         state=lace_briefs.state(brief, datetime.now(UTC)))


@router.patch("/{lace_id}/brief", response_model=BriefSettings)
async def update_brief_settings(lace: OwnedLace, payload: BriefSettingsUpdate, db: DbSession):
    return _brief_settings(await lace_service.update_brief_settings(db, lace, payload.model_dump(exclude_unset=True)))
