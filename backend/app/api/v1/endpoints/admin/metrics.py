from fastapi import APIRouter, Query

from backend.app.api.deps import DbSession
from backend.app.schemas.admin import AdminMetrics, ConnectionMetrics, EngagementMetrics, FunnelMetrics
from backend.app.services import admin_connections, admin_engagement, admin_funnel, admin_metrics

router = APIRouter()

Days = Query(default=30, ge=1, le=admin_metrics.MAX_DAYS)


@router.get("/metrics", response_model=AdminMetrics)
async def metrics(db: DbSession, days: int = Days):
    """Users, runs and estimated spend over the last `days` days (UTC)."""
    return await admin_metrics.overview(db, days)


@router.get("/metrics/engagement", response_model=EngagementMetrics)
async def engagement(db: DbSession, days: int = Days):
    """Growth, time in app, what users create and which features they use."""
    return await admin_engagement.engagement(db, days)


@router.get("/metrics/funnel", response_model=FunnelMetrics)
async def funnel(db: DbSession, days: int = Days):
    """How far users get, where discovery interviews are abandoned, why runs fail."""
    return await admin_funnel.funnel(db, days)


@router.get("/metrics/connections", response_model=ConnectionMetrics)
async def connections(db: DbSession, days: int = Days):
    """Connected accounts per platform (live from Composio) and their use."""
    return await admin_connections.connection_metrics(db, days)
