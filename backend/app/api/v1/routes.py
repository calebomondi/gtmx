from fastapi import APIRouter
from backend.app.api.v1.endpoints import accounts, admin, competitors, discovery, projects, users, workspaces

api_router = APIRouter()

api_router.include_router(discovery.router, prefix="/discover", tags=["discovery"])
api_router.include_router(users.router, prefix="/users", tags=["users"])
api_router.include_router(projects.router, prefix="/projects", tags=["projects"])
api_router.include_router(workspaces.router, prefix="/workspaces", tags=["workspaces"])
# Competitors are workspace-scoped, so this router carries the workspace id in
# its own paths and mounts under the same prefix rather than nesting inside
# workspaces.router. Separate because these rows accumulate across agent runs --
# the opposite of the replace-whole-blob lifecycle the insights endpoints serve.
api_router.include_router(competitors.router, prefix="/workspaces", tags=["competitors"])
api_router.include_router(accounts.router, prefix="/workspaces", tags=["accounts"])
api_router.include_router(admin.router, prefix="/admin", tags=["admin"])
