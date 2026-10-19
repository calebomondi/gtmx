from fastapi import APIRouter, Depends
from backend.app.api.deps import rate_limited
from backend.app.api.v1.endpoints import activity, admin, connections, laces, runs, users, waitlist

api_router = APIRouter()
# Every REST router is rate limited per user.
_LIMITED = [Depends(rate_limited)]

# Public: the landing page's waitlist has no signed-in user, so it is limited
# per IP inside the service instead of per user.
api_router.include_router(waitlist.router, prefix="/waitlist", tags=["waitlist"])
api_router.include_router(runs.router, prefix="/runs", tags=["runs"], dependencies=_LIMITED)
api_router.include_router(activity.router, prefix="/activity", tags=["activity"], dependencies=_LIMITED)
api_router.include_router(users.router, prefix="/users", tags=["users"], dependencies=_LIMITED)
api_router.include_router(connections.router, prefix="/connections", tags=["connections"], dependencies=_LIMITED)
api_router.include_router(laces.router, prefix="/laces", tags=["laces"], dependencies=_LIMITED)
api_router.include_router(admin.router, prefix="/admin", tags=["admin"], dependencies=_LIMITED)
