from fastapi import APIRouter
from backend.app.api.v1.endpoints import discovery, users, workspaces

api_router = APIRouter()

api_router.include_router(discovery.router, prefix="/discover", tags=["discovery"])
api_router.include_router(users.router, prefix="/users", tags=["users"])
api_router.include_router(workspaces.router, prefix="/workspaces", tags=["workspaces"])
