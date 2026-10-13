"""The public waitlist behind gtmx.co. No sign-in: anyone can join, rate
limited per IP. The optional details step is authorised by the private token
the join call returned to that browser."""

import secrets

from fastapi import APIRouter, BackgroundTasks, Request

from backend.app.api.deps import DbSession
from backend.app.schemas.waitlist import PilotSpots, WaitlistDetails, WaitlistJoin, WaitlistJoined, WaitlistSaved
from backend.app.services import waitlist as waitlist_service

router = APIRouter()


def _client_ip(request: Request) -> str | None:
    # Behind nginx the peer is the proxy; it sets X-Real-IP (deploy/nginx.conf)
    # and overwrites any value a client sends.
    return request.headers.get("x-real-ip") or (request.client.host if request.client else None)


@router.post("", response_model=WaitlistJoined, status_code=201)
async def join_waitlist(payload: WaitlistJoin, request: Request, background: BackgroundTasks, db: DbSession):
    spots = await waitlist_service.pilot_spots(db)
    if payload.nickname:
        # A bot filled the hidden field: answer like a success, save nothing.
        return WaitlistJoined(token=secrets.token_urlsafe(32), pilot_spots_left=spots.left)
    signup, token, _created = await waitlist_service.join(db, str(payload.email), payload.source, _client_ip(request))
    background.add_task(waitlist_service.send_joined_email, signup.id)
    return WaitlistJoined(token=token, pilot_spots_left=spots.left)


@router.patch("/{token}", response_model=WaitlistSaved)
async def save_waitlist_details(token: str, payload: WaitlistDetails, background: BackgroundTasks, db: DbSession):
    signup, joined_pilot = await waitlist_service.save_details(db, token, payload)
    if joined_pilot:
        background.add_task(waitlist_service.send_pilot_email, signup.id)
    spots = await waitlist_service.pilot_spots(db)
    return WaitlistSaved(wants_pilot=signup.wants_pilot, pilot_spots_left=spots.left)


@router.get("/pilot", response_model=PilotSpots)
async def pilot_spots(db: DbSession):
    return await waitlist_service.pilot_spots(db)
