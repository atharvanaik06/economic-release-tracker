"""FastAPI application factory and default ASGI application."""

import logging

from fastapi import FastAPI

from macromonitor.api.health import router as health_router
from macromonitor.core.config import Settings, get_settings
from macromonitor.core.logging import configure_logging

logger = logging.getLogger(__name__)


def create_app(settings: Settings | None = None) -> FastAPI:
    """Create a configured MacroMonitor application instance."""
    resolved_settings = settings or get_settings()
    configure_logging(resolved_settings.log_level)

    application = FastAPI(
        title="MacroMonitor API",
        summary="Monitor economic releases, revisions, and webhook notifications.",
        version=resolved_settings.app_version,
    )
    application.state.settings = resolved_settings
    application.include_router(health_router)

    logger.info(
        "application configured",
        extra={"environment": resolved_settings.environment},
    )
    return application


app = create_app()
