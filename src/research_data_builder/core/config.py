"""Validated environment-based application settings."""

from functools import lru_cache
from typing import Literal

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from research_data_builder import __version__

Environment = Literal["development", "test", "production"]


class Settings(BaseSettings):
    """Research Data Builder settings loaded from the environment or a local .env file."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_prefix="RESEARCH_DATA_",
        extra="ignore",
    )

    app_name: str = "research-data-builder"
    app_version: str = __version__
    environment: Environment = "development"
    log_level: str = "INFO"
    database_url: str = Field(
        default="postgresql+psycopg://research_data:research_data@localhost:5432/research_data",
        min_length=1,
    )
    fred_api_key: SecretStr | None = None

    @field_validator("log_level")
    @classmethod
    def validate_log_level(cls, value: str) -> str:
        """Normalize and validate Python logging levels."""
        normalized = value.upper()
        allowed = {"CRITICAL", "ERROR", "WARNING", "INFO", "DEBUG"}
        if normalized not in allowed:
            message = f"log_level must be one of: {', '.join(sorted(allowed))}"
            raise ValueError(message)
        return normalized


@lru_cache
def get_settings() -> Settings:
    """Return one validated settings instance per process."""
    return Settings()
