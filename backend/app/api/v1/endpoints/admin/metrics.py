from fastapi import APIRouter, Query

from backend.app.api.deps import DbSession
from backend.app.schemas.admin import AdminMetrics
from backend.app.services import admin_metrics

router = APIRouter()


@router.get("/metrics", response_model=AdminMetrics)
async def metrics(db: DbSession, days: int = Query(default=30, ge=1, le=admin_metrics.MAX_DAYS)):
    """Users, runs and estimated spend over the last `days` days (UTC)."""
    return await admin_metrics.overview(db, days)
