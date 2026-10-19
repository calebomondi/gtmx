"""The signed-in user's Laces: create one (which starts it reading the site),
list them, read what one knows, read its conversation, and send it a message.
Work happens in runs; follow them at /runs/{run_id}/events."""

import uuid

from fastapi import APIRouter, Query, status

from backend.app.api.deps import CurrentUser, DbSession, OwnedLace
from backend.app.runs import lace as lace_runs
from backend.app.runs import manager
from backend.app.schemas.laces import (
    AccountResponse,
    BriefSettings,
    BriefSettingsUpdate,
    QuietHours,
    ChannelAccount,
    ChannelLinkRequest,
    ChannelResponse,
    AccountUpdateRequest,
    CompetitorResponse,
    CompetitorUpdateRequest,
    FactResponse,
    LaceCreateRequest,
    LaceCreateResponse,
    LaceListItem,
    LaceUpdate,
    LaceMessage,
    LaceMessageRequest,
    LaceResponse,
    LaceTurnResponse,
    OpportunityResponse,
    OpportunityUpdateRequest,
    OutreachResponse,
    OutreachUpdateRequest,
)
from backend.app.services import email, lace_accounts, lace_channels, lace_competitors, lace_opportunities, lace_outreach
from backend.app.services import laces as lace_service
from agents.schemas.lace import AccountStatus, CompetitorStatus, FactTopic, InboxPlatform
from agents.schemas.opportunities import OpportunityStatus

router = APIRouter()

MAX_LACES_PER_PAGE = 50
MAX_FACTS_PER_PAGE = 200
MAX_MESSAGES_PER_PAGE = 200
MAX_COMPETITORS_PER_PAGE = 100
MAX_ACCOUNTS_PER_PAGE = 100
MAX_OUTREACH_PER_PAGE = 100
MAX_OPPORTUNITIES_PER_PAGE = 100


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


@router.get("/{lace_id}", response_model=LaceResponse)
async def get_lace(lace: OwnedLace):
    return lace


@router.patch("/{lace_id}", response_model=LaceResponse)
async def update_lace(lace: OwnedLace, payload: LaceUpdate, db: DbSession):
    """Pin or unpin the Lace in the founder's sidebar."""
    if payload.pinned is not None:
        lace = await lace_service.set_pinned(db, lace, payload.pinned)
    return lace


@router.get("/{lace_id}/facts", response_model=list[FactResponse])
async def list_facts(lace: OwnedLace, db: DbSession, topic: FactTopic | None = None,
                     limit: int = Query(default=100, ge=1, le=MAX_FACTS_PER_PAGE)):
    return await lace_service.list_facts(db, lace.id, topic, limit)


@router.get("/{lace_id}/messages", response_model=list[LaceMessage])
async def list_messages(lace: OwnedLace, limit: int = Query(default=100, ge=1, le=MAX_MESSAGES_PER_PAGE)):
    return await lace_runs.history(lace.id, limit)


@router.post("/{lace_id}/messages", response_model=LaceTurnResponse, status_code=status.HTTP_202_ACCEPTED)
async def send_message(lace: OwnedLace, payload: LaceMessageRequest, user: CurrentUser):
    run = await manager.start_lace_turn(user.id, lace.id, payload.text)
    return LaceTurnResponse(run_id=run.id)


@router.get("/{lace_id}/competitors", response_model=list[CompetitorResponse])
async def list_competitors(lace: OwnedLace, db: DbSession,
                           shown: CompetitorStatus = Query(default="tracked", alias="status"),
                           limit: int = Query(default=50, ge=1, le=MAX_COMPETITORS_PER_PAGE)):
    return await lace_competitors.list_for_lace(db, lace.id, shown, limit)


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
    return BriefSettings.model_validate(lace).model_copy(update={"quiet_hours": quiet,
                                                                  "email_available": email.configured()})


@router.get("/{lace_id}/brief", response_model=BriefSettings)
async def get_brief_settings(lace: OwnedLace):
    """When the Lace posts its brief (how often, at what local hour), whether
    it is emailed too, and the quiet hours in which nothing is emailed."""
    return _brief_settings(lace)


@router.patch("/{lace_id}/brief", response_model=BriefSettings)
async def update_brief_settings(lace: OwnedLace, payload: BriefSettingsUpdate, db: DbSession):
    return _brief_settings(await lace_service.update_brief_settings(db, lace, payload.model_dump(exclude_unset=True)))
