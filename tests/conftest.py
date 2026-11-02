"""Shared test fixtures."""

import pytest
from fastapi import FastAPI

from macromonitor.core.config import Settings
from macromonitor.main import create_app


@pytest.fixture
def test_settings() -> Settings:
    """Return deterministic settings without reading a developer's .env file."""
    return Settings(
        environment="test",
        log_level="ERROR",
        database_url="postgresql://test:test@localhost:5432/test",
        _env_file=None,  # type: ignore[call-arg]  # pydantic-settings runtime option
    )


@pytest.fixture
def app(test_settings: Settings) -> FastAPI:
    """Return an isolated application instance."""
    return create_app(test_settings)
