"""A Lace's people: who is on it, inviting and removing them, roles, and a
person's own invites to answer. Mounted under /laces, before the Lace routes,
so /laces/invites isn't read as a Lace id."""

import uuid
from dataclasses import asdict

from fastapi import APIRouter, status

from backend.app.api.deps import AdminLace, CurrentUser, DbSession, LaceMembership, MemberLace, OwnerLace
from backend.app.schemas.laces import InviteRequest, InviteResponse, PersonResponse, RoleUpdate
from backend.app.services import lace_members

router = APIRouter()


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


@router.delete("/{lace_id}/members/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_member(lace: AdminLace, me: LaceMembership, user_id: uuid.UUID, db: DbSession):
    """Take someone off the Lace, or withdraw their invite."""
    await lace_members.remove(db, lace, me, user_id)


@router.post("/{lace_id}/leave", status_code=status.HTTP_204_NO_CONTENT)
async def leave_lace(lace: MemberLace, me: LaceMembership, db: DbSession):
    await lace_members.leave(db, me)
