"""Service health endpoints."""

import logging

from fastapi import APIRouter, HTTPException, Request, status
from pydantic import BaseModel

from macromonitor.core.config import Settings
from macromonitor.db.session import DatabaseLifecycle

logger = logging.getLogger(__name__)

router = APIRouter(tags=["health"])


class HealthResponse(BaseModel):
    """Public liveness response."""

    status: str
    service: str
    version: str
    environment: str


class ReadinessResponse(BaseModel):
    """Dependency readiness response."""

    status: str
    database: str


@router.get("/health", response_model=HealthResponse)
async def health(request: Request) -> HealthResponse:
    """Report that the API process is running and configured."""
    settings: Settings = request.app.state.settings
    return HealthResponse(
        status="healthy",
        service=settings.app_name,
        version=settings.app_version,
        environment=settings.environment,
    )


@router.get(
    "/ready",
    response_model=ReadinessResponse,
    responses={status.HTTP_503_SERVICE_UNAVAILABLE: {"description": "Database unavailable"}},
)
async def readiness(request: Request) -> ReadinessResponse:
    """Report whether required dependencies can serve application traffic."""
    database: DatabaseLifecycle = request.app.state.database
    try:
        await database.check()
    except Exception as error:
        logger.warning(
            "database readiness check failed", extra={"error_type": type(error).__name__}
        )
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"code": "database_unavailable"},
        ) from None
    return ReadinessResponse(status="ready", database="healthy")
