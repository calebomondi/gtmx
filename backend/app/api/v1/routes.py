from fastapi import APIRouter, Depends
from backend.app.api.deps import in_pilot, rate_limited
from backend.app.api.v1.endpoints import (
    activity, admin, connections, events, feedback, lace_finds, lace_members, lace_regulations, laces, pilot, runs,
    users, waitlist,
)

api_router = APIRouter()
# Every REST router is rate limited per user.
_LIMITED = [Depends(rate_limited)]
# The customer API is for people in the pilot (services.pilot); /users/me says
# whether you are, and admin routes have their own guard.
_PILOT = [*_LIMITED, Depends(in_pilot)]

# Public: the landing page's waitlist has no signed-in user, so it is limited
# per IP inside the service instead of per user.
api_router.include_router(waitlist.router, prefix="/waitlist", tags=["waitlist"])
api_router.include_router(pilot.router, prefix="/pilot", tags=["pilot"])
api_router.include_router(runs.router, prefix="/runs", tags=["runs"], dependencies=_PILOT)
api_router.include_router(activity.router, prefix="/activity", tags=["activity"], dependencies=_PILOT)
api_router.include_router(users.router, prefix="/users", tags=["users"], dependencies=_LIMITED)
api_router.include_router(feedback.router, prefix="/feedback", tags=["feedback"], dependencies=_PILOT)
api_router.include_router(events.router, prefix="/events", tags=["events"], dependencies=_PILOT)
api_router.include_router(connections.router, prefix="/connections", tags=["connections"], dependencies=_PILOT)
# Before the Lace routes: /laces/invites is not a Lace id.
api_router.include_router(lace_members.router, prefix="/laces", tags=["laces"], dependencies=_PILOT)
api_router.include_router(lace_finds.router, prefix="/laces", tags=["laces"], dependencies=_PILOT)
api_router.include_router(lace_regulations.router, prefix="/laces", tags=["laces"], dependencies=_PILOT)
api_router.include_router(laces.router, prefix="/laces", tags=["laces"], dependencies=_PILOT)
api_router.include_router(admin.router, prefix="/admin", tags=["admin"], dependencies=_LIMITED)
