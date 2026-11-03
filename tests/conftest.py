"""Shared test fixtures."""

import pytest
from fastapi import FastAPI

from research_data_builder.core.config import Settings
from research_data_builder.main import create_app
from research_data_builder.providers.registry import ProviderRegistry
from tests.fakes import FakeDatabase


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
def database() -> FakeDatabase:
    """Return an available fake database."""
    return FakeDatabase()


@pytest.fixture
def app(test_settings: Settings, database: FakeDatabase) -> FastAPI:
    """Return an isolated application instance."""
    return create_app(test_settings, database, ProviderRegistry([]))
