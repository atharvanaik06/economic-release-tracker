"""Service health endpoints."""

from fastapi import APIRouter, Request
from pydantic import BaseModel

from macromonitor.core.config import Settings

router = APIRouter(tags=["health"])


class HealthResponse(BaseModel):
    """Public liveness response."""

    status: str
    service: str
    version: str
    environment: str


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
