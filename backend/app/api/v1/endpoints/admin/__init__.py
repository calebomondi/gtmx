"""/api/v1/admin/*: every route here is gated by require_admin at the router."""

from fastapi import APIRouter, Depends

from backend.app.api.deps import require_admin
from backend.app.api.v1.endpoints.admin import actions, entities, me, metrics

router = APIRouter(dependencies=[Depends(require_admin)])
router.include_router(me.router)
router.include_router(metrics.router)
router.include_router(entities.router)
router.include_router(actions.router)
