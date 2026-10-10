from fastapi import FastAPI
from contextlib import asynccontextmanager
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text

from config import settings
from backend.app.api.v1.routes import api_router
from backend.app.database.connect import engine, AsyncSessionLocal
from backend.app.database.schema_check import ensure_schema_at_head
from backend.app.services.errors import ConflictError, InvalidInputError, NotFoundError, ServiceError
from backend.app import agents_runtime


@asynccontextmanager
async def lifespan(app: FastAPI):
    await ensure_schema_at_head(engine)
    await agents_runtime.start_agent_runtime(settings.database_url)
    try:
        yield
    finally:
        await agents_runtime.stop_agent_runtime()

_SERVICE_ERROR_STATUS = {
    NotFoundError: 404,
    ConflictError: 409,
    InvalidInputError: 422,
}


def add_service_error_handlers(application: FastAPI) -> None:
    """Map service-layer domain errors to HTTP responses ({"detail": ...},
    the same shape as HTTPException), so services never import FastAPI."""
    async def handle(_request, exc: ServiceError):
        return JSONResponse(status_code=_SERVICE_ERROR_STATUS[type(exc)], content={"detail": str(exc)})

    for error_type in _SERVICE_ERROR_STATUS:
        application.add_exception_handler(error_type, handle)


def create_application() -> FastAPI:
    # FastAPI instance
    application = FastAPI(
        title= settings.project_name,
        lifespan=lifespan
    )
    # CORS — only relevant when the API and frontend live on different origins.
    # Same-origin deployments (dev proxy / reverse proxy) do not require it.
    if settings.allowed_origins:
        application.add_middleware(
            CORSMiddleware,
            allow_origins=settings.allowed_origins,
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"]
        )
    # Include routers
    application.include_router(api_router, prefix=settings.api_v1_str)
    add_service_error_handlers(application)

    @application.get("/health", tags=["ops"])
    async def health():
        """Liveness/readiness for local tooling and the dev loop.

        Reports the two dependencies an agent run actually needs, so a failing
        run can be told apart from a failing environment.
        """
        checks = {"database": "ok", "agent_runtime": "ok"}
        status = 200
        try:
            async with AsyncSessionLocal() as db:
                await db.execute(text("SELECT 1"))
        except Exception as exc:
            checks["database"] = f"error: {exc}"
            status = 503
        try:
            agents_runtime.get_agent()
        except Exception as exc:
            checks["agent_runtime"] = f"error: {exc}"
            status = 503
        return JSONResponse(
            status_code=status,
            content={"status": "ok" if status == 200 else "degraded", **checks},
        )

    return application


app = create_application()
