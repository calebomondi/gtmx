"""A Lace's people: who is on it, inviting and removing them, roles, and a
person's own invites to answer. Mounted under /laces, before the Lace routes,
so /laces/invites isn't read as a Lace id."""

import uuid
from dataclasses import asdict

from fastapi import APIRouter, Query, status

from backend.app.api.deps import AdminLace, CurrentUser, DbSession, LaceMembership, MemberLace, OwnerLace
from backend.app.schemas.laces import (
    DomainClaim, InviteRequest, InviteResponse, JoinRequest, PersonResponse, RoleUpdate,
)
from backend.app.services import lace_members
from backend.app.services.competitors import checked_website, domain_key

router = APIRouter()


@router.get("/claimed", response_model=DomainClaim)
async def domain_claimed(user: CurrentUser, db: DbSession, website: str = Query(min_length=3, max_length=500)):
    """Whether the startup at this website already has a Lace (one per startup)."""
    domain = domain_key(checked_website(website))
    return DomainClaim(domain=domain, taken=await lace_members.lace_for_domain(db, domain) is not None)


@router.post("/requests", status_code=status.HTTP_204_NO_CONTENT)
async def ask_to_join(payload: JoinRequest, user: CurrentUser, db: DbSession):
    """Ask the people on the Lace of the startup at this website to let you in."""
    await lace_members.request_to_join(db, domain_key(checked_website(payload.website)), user.id,
                                       user.name or user.email or "Someone")


@router.get("/invites", response_model=list[InviteResponse])
async def my_invites(user: CurrentUser, db: DbSession):
    """The Laces the user was invited to and hasn't answered yet."""
    return [InviteResponse(lace_id=i.lace.id, lace_name=i.lace.name, startup_name=i.lace.startup_name,
                           website=i.lace.website, role=i.role, invited_by=i.invited_by, invited_at=i.invited_at)
            for i in await lace_members.invites_for(db, user.id)]


@router.post("/invites/{lace_id}/accept", status_code=status.HTTP_204_NO_CONTENT)
async def accept_invite(lace_id: uuid.UUID, user: CurrentUser, db: DbSession):
    await lace_members.accept(db, lace_id, user.id)


@router.post("/invites/{lace_id}/decline", status_code=status.HTTP_204_NO_CONTENT)
async def decline_invite(lace_id: uuid.UUID, user: CurrentUser, db: DbSession):
    await lace_members.decline(db, lace_id, user.id)


@router.get("/{lace_id}/members", response_model=list[PersonResponse])
async def list_members(lace: MemberLace, db: DbSession):
    """Everyone on the Lace, and the invites still open."""
    return [PersonResponse(**asdict(p)) for p in await lace_members.people(db, lace)]


@router.post("/{lace_id}/members", response_model=PersonResponse, status_code=status.HTTP_201_CREATED)
async def invite_member(lace: AdminLace, me: LaceMembership, payload: InviteRequest, db: DbSession):
    """Invite someone who has signed up, by their email."""
    return PersonResponse(**asdict(await lace_members.invite(db, lace, me, payload.email, payload.role)))


@router.patch("/{lace_id}/members/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def change_role(lace: OwnerLace, user_id: uuid.UUID, payload: RoleUpdate, db: DbSession):
    await lace_members.set_role(db, lace, user_id, payload.role)


@router.post("/{lace_id}/members/{user_id}/approve", status_code=status.HTTP_204_NO_CONTENT)
async def let_in(lace: AdminLace, user_id: uuid.UUID, db: DbSession):
    """Let in someone who asked to join, as a member."""
    await lace_members.let_in(db, lace, user_id)


@router.delete("/{lace_id}/members/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_member(lace: AdminLace, me: LaceMembership, user_id: uuid.UUID, db: DbSession):
    """Take someone off the Lace, withdraw their invite, or turn down their request."""
    await lace_members.remove(db, lace, me, user_id)


@router.post("/{lace_id}/leave", status_code=status.HTTP_204_NO_CONTENT)
async def leave_lace(lace: MemberLace, me: LaceMembership, db: DbSession):
    await lace_members.leave(db, me)
