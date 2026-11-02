"""FastAPI application factory and default ASGI application."""

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from macromonitor.api.health import router as health_router
from macromonitor.core.config import Settings, get_settings
from macromonitor.core.logging import configure_logging
from macromonitor.db.session import Database, DatabaseLifecycle

logger = logging.getLogger(__name__)


def create_app(
    settings: Settings | None = None,
    database: DatabaseLifecycle | None = None,
) -> FastAPI:
    """Create a configured MacroMonitor application instance."""
    resolved_settings = settings or get_settings()
    configure_logging(resolved_settings.log_level)
    resolved_database = database or Database(resolved_settings.database_url)

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        yield
        await resolved_database.dispose()

    application = FastAPI(
        title="MacroMonitor API",
        summary="Monitor economic releases, revisions, and webhook notifications.",
        version=resolved_settings.app_version,
        lifespan=lifespan,
    )
    application.state.settings = resolved_settings
    application.state.database = resolved_database
    application.include_router(health_router)

    logger.info(
        "application configured",
        extra={"environment": resolved_settings.environment},
    )
    return application


app = create_app()
