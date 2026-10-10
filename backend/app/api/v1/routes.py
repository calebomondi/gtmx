from fastapi import APIRouter, Depends
from backend.app.api.deps import rate_limited
from backend.app.api.v1.endpoints import accounts, admin, chat, competitors, connections, discovery, projects, runs, signals, users, workspaces

api_router = APIRouter()
# Every REST router is rate limited per user; the discovery WebSocket is limited
# at run start instead (runs/manager.start_discovery).
_LIMITED = [Depends(rate_limited)]

api_router.include_router(discovery.router, prefix="/discover", tags=["discovery"])
api_router.include_router(runs.router, prefix="/runs", tags=["runs"], dependencies=_LIMITED)
api_router.include_router(users.router, prefix="/users", tags=["users"], dependencies=_LIMITED)
api_router.include_router(signals.router, prefix="/signals", tags=["signals"], dependencies=_LIMITED)
api_router.include_router(connections.router, prefix="/connections", tags=["connections"], dependencies=_LIMITED)
api_router.include_router(projects.router, prefix="/projects", tags=["projects"], dependencies=_LIMITED)
api_router.include_router(workspaces.router, prefix="/workspaces", tags=["workspaces"], dependencies=_LIMITED)
# Competitors are workspace-scoped, so this router carries the workspace id in
# its own paths and mounts under the same prefix rather than nesting inside
# workspaces.router. Separate because these rows accumulate across agent runs --
# the opposite of the replace-whole-blob lifecycle the insights endpoints serve.
api_router.include_router(competitors.router, prefix="/workspaces", tags=["competitors"], dependencies=_LIMITED)
api_router.include_router(accounts.router, prefix="/workspaces", tags=["accounts"], dependencies=_LIMITED)
api_router.include_router(chat.router, prefix="/workspaces", tags=["chat"], dependencies=_LIMITED)
api_router.include_router(admin.router, prefix="/admin", tags=["admin"], dependencies=_LIMITED)
